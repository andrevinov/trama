"""Entrada sem janela usando o coordenador real; decisões externas explícitas e locais."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.game_flow import FlowStage, FlowStatus, GameFlow, GameFlowError
from trama.application.game_runner import GameRunner, RunStatus
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, RequestPart, RuleIntent
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.spatial import Position


def session(*, guard=False, roller=None):
    data = {'width': 8, 'height': 6, 'start': [2, 3]}
    if guard:
        data['creatures'] = [{'id': 'guard', 'name': 'Guarda', 'position': [3, 3], 'hostile': True}]
    return build_session(data, roller=roller)


def walking():
    return ActionPlan((MovementIntent((MovementSegment('west', 1),), False, ''),))


def runner_for(game, plan=None, *, worlds=(WorldPlan(),), replies=(Speech(on='Os efeitos são descritos.'),)):
    interpreter, director, narrator = Mock(), Mock(), Mock()
    chosen = plan if plan is not None else walking()
    interpreter.interpret.side_effect = lambda prompt, context: chosen if chosen.request_parts else sourced_plan(chosen, prompt)
    director.decide.side_effect = worlds
    narrator.narrate.side_effect = replies
    return GameRunner(GameFlow(game, interpreter, narrator, director))


def npc(*actions):
    return WorldPlan((WorldReaction(0, 0, actions),))


def stages(result):
    return [r.stage for r in result.requests]


def test_opening_idle_and_rejected_input_do_not_execute_extra_requests():
    runner = runner_for(session())
    assert runner.run_until_input().status == RunStatus.IDLE
    result = runner.start()
    assert result.accepted is True and result.status == RunStatus.COMPLETED
    assert stages(result) == [FlowStage.NARRATE]
    assert result.requests[0].context.kind == 'narration_initial'
    assert not runner.flow.interpreter.interpret.called and not runner.flow.world_director.decide.called
    assert runner.start().status == runner.submit('   ').status == RunStatus.REJECTED
    assert runner.flow.narrator.narrate.call_count == 1


def test_mixed_message_executes_real_movement_and_returns_detached_observations():
    runner = runner_for(session(), replies=(Speech(on='Você recua.', off='Percorreu 1,5 m.'),))
    result = runner.submit('Recuo para oeste. [Quanto andei?]')
    assert result.accepted and result.status == RunStatus.COMPLETED
    assert stages(result) == [FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NARRATE]
    assert runner.flow.session.state.position == Position(1, 3)
    assert result.report.events[0]['traveled_meters'] == 1.5
    assert result.reply.on == 'Você recua.' and result.reply.off == 'Percorreu 1,5 m.'
    assert result.requests[0].prompt == 'Recuo para oeste.'
    assert result.requests[-1].context['player']['off'] == 'Quanto andei?'
    assert len({r.request_id for r in result.requests}) == 3
    assert all(r.applied for r in result.requests)
    result.report.events[0]['traveled_meters'] = 999
    result.requests[0].context['character']['column'] = 999
    assert runner.flow.report.events[0]['traveled_meters'] == 1.5
    assert runner.flow.interpreter.interpret.call_args.args[1]['character']['column'] == 3
    assert not runner.run_until_input().requests


def test_off_and_valid_question_plan_skip_world_without_advancing_npc(dice):
    game = session(guard=True, roller=dice(1, 2, 20))
    game.execute(RuleIntent('start_combat'))
    runner = runner_for(game, replies=(Speech(off='A vez é do guarda.'),))
    before = (game.state, game.encounter.combat, deepcopy(game.encounter.states))
    result = runner.submit('[De quem é a vez?]')
    assert stages(result) == [FlowStage.NARRATE]
    assert not runner.flow.interpreter.interpret.called and not runner.flow.world_director.decide.called
    assert (game.state, game.encounter.combat, game.encounter.states) == before
    prompt = 'Posso usar Retomar o Fôlego?'
    question = ActionPlan((), (RequestPart(prompt, 'question'),))
    runner = runner_for(session(), question, replies=(Speech(off='Sim.'),))
    result = runner.submit(prompt)
    assert stages(result) == [FlowStage.INTERPRET, FlowStage.NARRATE]
    assert not runner.flow.world_director.decide.called


def test_end_turn_runs_npc_and_returns_control_before_narrating(dice):
    game = session(guard=True, roller=dice(20, 19, 1, 1))
    game.execute(RuleIntent('start_combat'))
    runner = runner_for(game, ActionPlan((RuleIntent('end_turn'),)), worlds=(WorldPlan(),
        npc(WorldAction('guard', 'attack', 'O guarda golpeia.', 'player'))))
    result = runner.submit('Não faço mais nada.')
    assert stages(result) == [FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NPC_TURN, FlowStage.NARRATE]
    assert result.status == RunStatus.COMPLETED and game.encounter.combat.active_id == 'player'
    assert game.encounter.states['player'].hp == 25
    assert [call.args[0]['phase'] for call in runner.flow.world_director.decide.call_args_list] == ['player_action', 'npc_turn']
    assert any(e['operation'] == 'attack' for e in result.report.world_events)


def test_npc_active_before_message_is_handled_by_flow_before_interpreting(dice):
    game = session(guard=True, roller=dice(1, 2, 20, 1))
    game.execute(RuleIntent('start_combat'))
    runner = runner_for(game, worlds=(npc(WorldAction('guard', 'wait', 'O guarda espera.')), WorldPlan()))
    result = runner.submit('Recuo para oeste.')
    assert stages(result) == [FlowStage.NPC_TURN, FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NARRATE]
    assert game.state.position == Position(1, 3) and game.encounter.combat.active_id == 'player'
    assert result.requests[1].context['combat']['player_turn'] is True


@pytest.mark.parametrize('accept', [False, True])
def test_pending_opportunity_requires_explicit_choice_and_resumes_once(accept, dice):
    game = session(guard=True, roller=dice(20, 19, 1, *([1] if accept else [])))
    game.execute(RuleIntent('start_combat'))
    runner = runner_for(game, ActionPlan((RuleIntent('end_turn'),)), worlds=(WorldPlan(), npc(
        WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3)),
        WorldAction('guard', 'say', 'Afaste-se!'))), replies=(Speech(on='Ele começa a recuar.'), Speech(on='Ele termina de recuar.')))
    paused = runner.submit('Encerro meu turno.')
    assert paused.status == RunStatus.AWAITING_REACTION and paused.awaiting_reaction
    assert game.creatures[0].position == Position(3, 3)
    assert game.encounter.states['guard'].hp == 12
    assert not runner.run_until_input().requests
    with pytest.raises(GameFlowError, match='True ou False'):
        runner.choose_opportunity(None)
    assert game.pending_opportunity and not game.budget.reaction_used
    continued = runner.choose_opportunity(accept)
    assert continued.status == RunStatus.COMPLETED
    assert stages(continued) == [FlowStage.NARRATE]  # Não decide novamente o plano do guarda.
    assert game.creatures[0].position == Position(5, 3) and game.encounter.combat.active_id == 'player'
    assert game.encounter.states['guard'].hp == (9 if accept else 12)
    assert not game.budget.reaction_used  # A reação se renova ao começar a nova vez do jogador.
    assert any(e['operation'] == 'opportunity_attack' for e in continued.report.world_events) is accept
    assert len([e for e in continued.report.world_events if e['operation'] == 'say']) == 1
    assert runner.flow.world_director.decide.call_count == 2
    assert runner.choose_opportunity(accept).status == RunStatus.FAILED
    assert game.encounter.states['guard'].hp == (9 if accept else 12)


def test_narration_failure_keeps_pending_reaction_available_for_explicit_recovery(dice):
    game = session(guard=True, roller=dice(20, 19, 1))
    game.execute(RuleIntent('start_combat'))
    runner = runner_for(game, ActionPlan((RuleIntent('end_turn'),)), worlds=(WorldPlan(),
        npc(WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3)))),
        replies=(ValueError('Falha de narração.'), Speech(on='O guarda recua.')))
    failed = runner.submit('Encerro meu turno.')
    assert failed.status == RunStatus.FAILED and failed.awaiting_reaction
    assert runner.run_until_input().status == RunStatus.FAILED
    assert runner.choose_opportunity(False).status == RunStatus.COMPLETED
    assert game.creatures[0].position == Position(5, 3)


def test_dispatch_limit_keeps_pending_request_and_resumes_without_repeating_effects():
    runner = runner_for(session())
    first = runner.submit('Recuo para oeste.', max_requests=1)
    assert first.status == RunStatus.REQUEST_LIMIT and first.flow_status == FlowStatus.PENDING
    assert stages(first) == [FlowStage.INTERPRET]
    assert runner.flow.session.state.position == Position(2, 3)
    pending = runner.flow.pending_request
    assert runner.submit('Olho.').status == RunStatus.REJECTED
    limited = runner.run_until_input(max_requests=0)
    assert limited.pending_request_id == pending.id and not limited.requests
    second = runner.run_until_input(max_requests=1)
    assert stages(second) == [FlowStage.WORLD] and second.status == RunStatus.REQUEST_LIMIT
    assert runner.flow.session.state.position == Position(1, 3)
    last = runner.run_until_input()
    assert stages(last) == [FlowStage.NARRATE] and last.status == RunStatus.COMPLETED
    assert runner.flow.interpreter.interpret.call_count == runner.flow.world_director.decide.call_count == 1
    assert runner.flow.session.state.position == Position(1, 3)


@pytest.mark.parametrize('limit', [-1, True, '2'])
def test_invalid_limit_is_rejected_before_changing_history_or_dispatching(limit):
    runner = runner_for(session())
    with pytest.raises(ValueError, match='max_requests'):
        runner.submit('Recuo.', max_requests=limit)
    assert not runner.flow.conversation.messages and not runner.flow.pending
    assert not runner.flow.interpreter.interpret.called


@pytest.mark.parametrize('stage', [FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NARRATE])
def test_provider_failure_is_reported_once_and_preserves_prior_execution(stage):
    runner = runner_for(session())
    error = RuntimeError('Falha externa simulada.')
    method = {FlowStage.INTERPRET: runner.flow.interpreter.interpret,
              FlowStage.WORLD: runner.flow.world_director.decide, FlowStage.NARRATE: runner.flow.narrator.narrate}[stage]
    method.side_effect = error
    result = runner.submit('Recuo para oeste.')
    assert result.status == RunStatus.FAILED and result.error is error
    assert result.requests[-1].result is error and result.requests[-1].applied
    assert runner.flow.session.state.position == Position(1 if stage == FlowStage.NARRATE else 2, 3)
    assert not runner.run_until_input().requests and method.call_count == 1


def test_reset_invalidates_pending_result_and_narrates_new_opening():
    runner = runner_for(session())
    runner.submit('Recuo.', max_requests=1)
    old = runner.flow.pending_request
    reset = runner.reset(max_requests=0)
    assert reset.status == RunStatus.REQUEST_LIMIT and reset.pending_request_id != old.id
    assert runner.flow.session.state.position == runner.flow.session.initial_state.position
    assert not runner.flow.conversation.messages
    assert not runner.flow.receive(old.id, WorldPlan())
    result = runner.run_until_input()
    assert result.status == RunStatus.COMPLETED
    assert stages(result) == [FlowStage.NARRATE] and result.requests[0].context['phase'] == 'initial'
    assert len(runner.flow.conversation.messages) == 1


def test_cross_thread_drain_is_rejected_before_any_external_request():
    runner = runner_for(session())
    runner.submit('Recuo.', max_requests=0)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(GameFlowError, match='thread dona'):
            pool.submit(runner.run_until_input).result()
        with pytest.raises(GameFlowError, match='thread dona'):
            pool.submit(GameRunner, runner.flow).result()
    assert not runner.flow.interpreter.interpret.called
    assert runner.flow.pending_request.stage == FlowStage.INTERPRET


def test_stale_result_is_observable_and_does_not_dispatch_new_request_implicitly():
    runner = runner_for(session())

    def reset_during_response(context):
        runner.flow.reset()
        return Speech(on='Resposta antiga.')

    runner.flow.narrator.narrate.side_effect = reset_during_response
    stale = runner.start()
    assert stale.status == RunStatus.STALE_RESULT and not stale.requests[0].applied
    assert not runner.flow.conversation.messages and stale.pending_request_id != stale.requests[0].request_id
    assert runner.flow.narrator.narrate.call_count == 1
    runner.flow.narrator.narrate.side_effect = [Speech(on='Nova abertura.')]
    assert runner.run_until_input().reply.on == 'Nova abertura.'


def test_interrupted_dispatch_is_not_repeated_by_a_later_drain():
    runner = runner_for(session())
    runner.flow.narrator.narrate.side_effect = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        runner.start()
    with pytest.raises(GameFlowError, match='já foi despachado'):
        runner.run_until_input()
    assert runner.flow.narrator.narrate.call_count == 1


def test_runner_imports_without_sdk_graphics_or_cli():
    code = '''
import importlib.abc
import sys
class RejectIO(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pygame', 'openai', 'argparse'} or fullname.startswith(('trama.ui', 'trama.infrastructure')):
            raise AssertionError('Importação indevida: ' + fullname)
sys.meta_path.insert(0, RejectIO())
from trama.application.game_runner import GameRunner
from trama.application.game_flow import GameFlow
from trama.application.scenarios import build_session
runner = GameRunner(GameFlow(build_session(dict(width=4, height=4, start=[1, 1]))))
assert runner.run_until_input().status == 'idle'
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
