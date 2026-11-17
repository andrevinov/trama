"""Coordenação real com adaptadores locais explícitos; nenhuma rede ou SDK."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import scripted_responses, sourced_plan
from trama.application.conversation import ExecutionReport
from trama.application.dialogue import NarrationError, Speech
from trama.application.game_flow import GameFlow, GameFlowError, FlowStage, FlowStatus
from trama.application.intents import (
    ActionPlan, InterpretationError, MovementIntent, MovementSegment,
    RequestPart, RuleIntent, ScenarioIntent,
)
from trama.application.scenarios import build_session, load_session
from trama.application.world import WorldAction, WorldError, WorldPlan, WorldReaction
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
from trama.observability import log_context
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]


class Interpreter:
    def __init__(self, *plans):
        self.plans = deque(plans)
        self.calls = []

    def interpret(self, prompt, context):
        self.calls.append((prompt, deepcopy(context)))
        plan = self.plans.popleft()
        if isinstance(plan, Exception):
            raise plan
        return sourced_plan(plan, prompt) if isinstance(plan, ActionPlan) and not plan.request_parts else plan


class Director:
    def __init__(self, *plans):
        self.plans = deque(plans)
        self.calls = []

    def decide(self, context):
        self.calls.append(deepcopy(context))
        plan = self.plans.popleft()
        if isinstance(plan, Exception):
            raise plan
        return plan


class Narrator:
    def __init__(self, *replies):
        self.replies = deque(replies)
        self.calls = []

    def narrate(self, context):
        self.calls.append(deepcopy(context))
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply


def walking(direction='east', squares=1):
    return MovementIntent((MovementSegment(direction, squares),), False, '')


def grid_session(*, guard=False, roller=None):
    data = dict(width=8, height=6, start=[2, 3])
    if guard:
        data['creatures'] = [dict(id='guard', name='Guarda', position=[3, 3], hostile=True)]
    return build_session(data, roller=roller)


def respond(flow, stage):
    """Agenda uma única chamada; não decide transições de jogo pelo teste."""
    request = flow.pending_request
    assert request is not None and request.stage == stage
    assert flow.receive(request.id, request.run())
    return request


def npc_plan(*actions):
    return WorldPlan((WorldReaction(0, 0, actions),))


def test_opening_only_narrates_and_records_history_once():
    session = load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json')
    narrator = Narrator(Speech(on='Você ouve sua cela abrir.'))
    flow = GameFlow(session, narrator=narrator)
    assert flow.start()
    assert not flow.start()
    assert session.state == session.initial_state and not flow.conversation.messages
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.COMPLETED
    assert narrator.calls[0]['phase'] == 'initial'
    assert flow.conversation.messages[-1].speech == flow.reply
    assert not flow.start()


def test_mixed_message_executes_then_narrates_real_state():
    interpreter = Interpreter(ActionPlan((walking(squares=2),)))
    director = Director(WorldPlan())
    narrator = Narrator(Speech(on='Você avança.', off='A distância foi 3 m.'))
    flow = GameFlow(grid_session(), interpreter, narrator, director)
    assert flow.submit('Ando 3 m para leste. [Quanto andei?]')
    respond(flow, FlowStage.INTERPRET)
    assert flow.session.state.position == Position(2, 3)
    respond(flow, FlowStage.WORLD)
    assert flow.session.state.position == Position(4, 3)
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.COMPLETED
    assert interpreter.calls[0][0] == 'Ando 3 m para leste.'
    assert interpreter.calls[0][1]['recent_messages'][-1]['on'] == interpreter.calls[0][0]
    assert director.calls[0]['phase'] == 'player_action'
    assert narrator.calls[0]['execution']['player_movement']['traveled_meters'] == 3
    assert narrator.calls[0]['player']['off'] == 'Quanto andei?'
    assert len(flow.conversation.messages) == 2


def test_contextual_investigation_uses_real_dungeon_and_report(dice):
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [7, 9]
    next(p for p in data['passages'] if p['id'] == 'gate_4')['is_open'] = True
    session = build_session(data, roller=dice(20))
    flow = GameFlow(session, Interpreter(ActionPlan((ScenarioIntent('investigate', 'cell_4'),))),
                    Narrator(Speech(on='Você entra e investiga.')), Director(WorldPlan()))
    flow.submit('Checo a cela, procurando algo útil.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    assert session.scene.area_at(session.state.position).id == 'cell_4'
    assert session.dungeon.discovered == {'longsword', 'cleaner_uniform'}
    assert any(e.get('preparation_for') for e in flow.report.events if e['operation'] == 'move')
    respond(flow, FlowStage.NARRATE)
    assert flow.reply.on


def test_off_question_does_not_execute_or_advance_active_npc(dice):
    session = grid_session(guard=True, roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    before = (session.state, session.encounter.combat)
    flow = GameFlow(session, narrator=Narrator(Speech(off='Você aguarda sua vez.')),
                    world_director=Director())
    flow.submit('[De quem é a vez?]')
    respond(flow, FlowStage.NARRATE)
    assert (session.state, session.encounter.combat) == before
    assert not flow.world_director.calls
    assert flow.reply.on == ''


def test_question_plan_without_steps_skips_world():
    prompt = 'Posso usar Retomar o Fôlego?'
    plan = ActionPlan((), (RequestPart(prompt, 'question'),))
    flow = GameFlow(grid_session(), Interpreter(plan), Narrator(Speech(off='Sim.')), Director())
    flow.submit(prompt)
    respond(flow, FlowStage.INTERPRET)
    assert not flow.world_director.calls
    respond(flow, FlowStage.NARRATE)
    assert flow.reply.off == 'Sim.'
    assert flow.session.state == flow.session.initial_state


def test_action_surge_and_attack_remain_two_executed_steps(dice):
    session = grid_session(guard=True, roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    session.encounter.roller = dice(1)
    flow = GameFlow(session, Interpreter(ActionPlan((RuleIntent('action_surge'), RuleIntent('attack', 'guard')))),
                    Narrator(Speech(on='Você usa o ímpeto e golpeia.')), Director(WorldPlan()))
    flow.submit('Uso Surto de Ação e ataco o guarda.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    assert [e['operation'] for e in flow.report.events] == ['action_surge', 'attack']
    assert session.encounter.states['guard'].hp == 9
    respond(flow, FlowStage.NARRATE)


def test_end_turn_resolves_npc_before_narrating(dice):
    session = grid_session(guard=True, roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    session.encounter.roller = dice(1)
    director = Director(WorldPlan(), npc_plan(WorldAction('guard', 'attack', 'O guarda golpeia.', 'player')))
    narrator = Narrator(Speech(on='O guarda ataca e sua vez retorna.'))
    flow = GameFlow(session, Interpreter(ActionPlan((RuleIntent('end_turn'),))), narrator, director)
    flow.submit('Não faço mais nada.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    assert session.encounter.combat.active_id == 'guard' and not narrator.calls
    respond(flow, FlowStage.NPC_TURN)
    assert session.encounter.combat.active_id == 'player'
    assert session.encounter.states['player'].hp == 25
    respond(flow, FlowStage.NARRATE)
    assert [c['phase'] for c in director.calls] == ['player_action', 'npc_turn']
    assert any(e['operation'] == 'attack' for e in narrator.calls[0]['execution']['reactions'])


def test_npc_active_before_message_is_resolved_before_interpreting(dice):
    session = grid_session(guard=True, roller=dice(1, 2, 20, 1))
    session.execute(RuleIntent('start_combat'))
    interpreter = Interpreter(ActionPlan((walking('west'),)))
    director = Director(npc_plan(WorldAction('guard', 'wait', 'O guarda espera.')), WorldPlan())
    flow = GameFlow(session, interpreter, Narrator(Speech(on='Você recua.')), director)
    flow.submit('Recuo para oeste.')
    assert not interpreter.calls
    respond(flow, FlowStage.NPC_TURN)
    assert session.encounter.combat.active_id == 'player'
    respond(flow, FlowStage.INTERPRET)
    assert interpreter.calls[0][1]['combat']['player_turn']
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NARRATE)
    assert session.state.position == Position(1, 3)
    assert any(e['actor_id'] == 'guard' for e in flow.report.world_events)


@pytest.mark.parametrize('accept', [False, True])
def test_opportunity_pauses_and_resumes_remaining_npc_actions_once(accept, dice):
    session = grid_session(guard=True, roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    session.encounter.roller = dice(1) if accept else dice()
    director = Director(WorldPlan(), npc_plan(
        WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3)),
        WorldAction('guard', 'say', 'Não se aproxime!')))
    flow = GameFlow(session, Interpreter(ActionPlan((RuleIntent('end_turn'),))),
                    Narrator(Speech(on='O guarda começa a recuar.'), Speech(on='O guarda completa o recuo.')), director)
    flow.submit('Encerro meu turno.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NPC_TURN)
    assert session.creatures[0].position == Position(3, 3)
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.AWAITING_REACTION
    assert flow.awaiting_reaction
    assert flow.choose_opportunity(accept)
    assert session.creatures[0].position == Position(5, 3)
    assert session.encounter.combat.active_id == 'player'
    assert session.encounter.states['guard'].hp == (9 if accept else 12)
    assert len(director.calls) == 2  # A continuação não pede um novo plano de NPC.
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.COMPLETED and flow.report.stop_reason is None
    assert sum(e.get('cost_meters', 0) for e in flow.report.world_events if e['operation'] == 'move') == 3
    assert len([e for e in flow.report.world_events if e['operation'] == 'say']) == 1
    assert flow.choose_opportunity(accept)  # Erro explícito, sem executar de novo.
    assert flow.status == FlowStatus.FAILED
    assert session.encounter.states['guard'].hp == (9 if accept else 12)


def test_off_during_reaction_keeps_deferred_player_message_and_partial_effects(dice):
    session = grid_session(guard=True, roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    director = Director(npc_plan(
        WorldAction('guard', 'say', 'Afaste-se!'),
        WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3))), WorldPlan())
    interpreter = Interpreter(ActionPlan((walking('west'),)))
    flow = GameFlow(session, interpreter, Narrator(Speech(on='O guarda se afasta.'),
                    Speech(off='Você pode usar uma reação.'), Speech(on='Você recua.')), director)
    flow.submit('Recuo para oeste.')
    respond(flow, FlowStage.NPC_TURN)
    respond(flow, FlowStage.NARRATE)
    flow.submit('[O que posso fazer?]')
    respond(flow, FlowStage.NARRATE)
    assert flow.awaiting_reaction and not interpreter.calls
    flow.choose_opportunity(False)
    respond(flow, FlowStage.INTERPRET)
    assert interpreter.calls[0][0] == 'Recuo para oeste.'
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NARRATE)
    assert session.state.position == Position(1, 3)
    assert len([e for e in flow.report.world_events if e['operation'] == 'say']) == 1


@pytest.mark.parametrize('stage', [FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NARRATE])
def test_provider_failure_preserves_effects_and_does_not_retry(stage):
    interpreter = Interpreter(InterpretationError('Falha de interpretação.') if stage == FlowStage.INTERPRET
                              else ActionPlan((walking(),)))
    director = Director(WorldError('Falha do Mundo.') if stage == FlowStage.WORLD else WorldPlan())
    narrator = Narrator(NarrationError('Falha de narração.'))
    flow = GameFlow(grid_session(), interpreter, narrator, director)
    flow.submit('Ando para leste.')
    respond(flow, FlowStage.INTERPRET)
    if stage != FlowStage.INTERPRET:
        respond(flow, FlowStage.WORLD)
    if stage == FlowStage.NARRATE:
        respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.FAILED and not flow.pending
    assert flow.session.state.position == Position(3 if stage == FlowStage.NARRATE else 2, 3)
    assert len(interpreter.calls) == 1
    assert len(director.calls) == (0 if stage == FlowStage.INTERPRET else 1)
    assert len(narrator.calls) == (1 if stage == FlowStage.NARRATE else 0)
    assert flow.conversation.messages[-1].speech.off


def test_rejected_plan_does_not_reach_world_or_use_power():
    prompt = 'Ando para leste.'
    # Origem inconsistente: declara move mas propõe um poder.
    bad = ActionPlan((RuleIntent('second_wind'),), (RequestPart(prompt, 'execute', ('move',), (0,)),))
    flow = GameFlow(grid_session(), Interpreter(bad), world_director=Director())
    flow.submit(prompt)
    respond(flow, FlowStage.INTERPRET)
    assert flow.status == FlowStatus.FAILED
    assert not flow.world_director.calls
    assert flow.session.encounter.states['player'].second_wind_uses == 2


def test_worker_can_call_provider_but_cannot_apply_result_or_mutate_game():
    flow = GameFlow(grid_session(), Interpreter(ActionPlan((walking(),))),
                    Narrator(Speech(on='Você anda.')), Director(WorldPlan()))
    flow.submit('Ando para leste.')
    request = flow.pending_request
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = worker.submit(request.run).result(timeout=3)
        assert flow.session.state.position == Position(2, 3)
        with pytest.raises(GameFlowError, match='thread dona'):
            worker.submit(flow.receive, request.id, result).result(timeout=3)
    assert flow.pending_request is request
    assert flow.receive(request.id, result)
    world = respond(flow, FlowStage.WORLD)
    assert flow.session.state.position == Position(3, 3)
    current = flow.pending_request
    assert not flow.receive(world.id, WorldPlan())
    assert flow.pending_request is current
    assert flow.session.state.position == Position(3, 3)
    respond(flow, FlowStage.NARRATE)


def test_reset_invalidates_inflight_response_and_requests_new_opening():
    narrator = Narrator(Speech(on='Primeira abertura.'), Speech(on='Nova abertura.'))
    flow = GameFlow(grid_session(), narrator=narrator)
    flow.start()
    old = flow.pending_request
    result = old.run()
    previous_id = flow.interaction_id
    flow.reset()
    new = flow.pending_request
    assert new.id != old.id and flow.interaction_id != previous_id
    assert not flow.receive(old.id, result)
    assert flow.pending_request is new and not flow.conversation.messages
    respond(flow, FlowStage.NARRATE)
    assert len(flow.conversation.messages) == 1
    assert flow.reply.on == 'Nova abertura.'


def test_missing_adapters_and_offline_narration_are_explicit():
    missing = GameFlow(grid_session())
    missing.start()
    assert missing.status == FlowStatus.FAILED and missing.reply.off
    missing.submit('Ando.')
    assert missing.status == FlowStatus.FAILED
    assert missing.session.state == missing.session.initial_state
    local = GameFlow(grid_session(), Interpreter(ActionPlan((walking(),))))
    local.submit('Ando para leste.')
    respond(local, FlowStage.INTERPRET)
    assert local.status == FlowStatus.COMPLETED
    assert local.session.state.position == Position(3, 3)
    assert 'Narrador indisponível' in local.reply.off and '1,5 m' in local.reply.off


def test_invalid_input_and_busy_submission_do_not_replace_current_request():
    flow = GameFlow(grid_session(), narrator=Narrator(Speech(on='A cela abre.')))
    assert not flow.submit('  ')
    flow.submit('[Colchete aberto')
    assert flow.status == FlowStatus.FAILED and len(flow.conversation.messages) == 1
    flow.reset()
    request = flow.pending_request
    history = list(flow.conversation.messages)
    assert not flow.submit('Ando.')
    assert flow.pending_request is request and flow.conversation.messages == history


def test_wrong_response_type_is_a_failure_without_execution():
    flow = GameFlow(grid_session(), Interpreter(Speech(on='Resposta errada.')))
    flow.submit('Ando.')
    respond(flow, FlowStage.INTERPRET)
    assert flow.status == FlowStatus.FAILED
    assert 'Resposta incompatível' in flow.message
    assert flow.session.state == flow.session.initial_state


def test_adapter_correction_stays_inside_single_interpretation_request():
    client = Mock()
    wrong = dict(steps=[dict(operation='second_wind', target_id=None, weapon='greatsword', use_inspiration=False)])
    correct = dict(steps=[dict(operation='move', segments=[dict(direction='east', distance=1.5, unit='meters')],
                               dash=False, clarification='', target_id=None)])
    client.responses.create.side_effect = scripted_responses(*[
        SimpleNamespace(status='completed', output=[], output_text=json.dumps(value)) for value in (wrong, correct)
    ], operations=['move'])
    flow = GameFlow(grid_session(), OpenAIIntentInterpreter(client), Narrator(Speech(on='Você anda.')), Director(WorldPlan()))
    flow.submit('Ando para leste.')
    request = respond(flow, FlowStage.INTERPRET)
    assert client.responses.create.call_count == 2
    assert flow.pending_request.stage == FlowStage.WORLD
    assert flow.session.state == flow.session.initial_state
    assert flow.session.encounter.states['player'].second_wind_uses == 2
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NARRATE)
    assert flow.session.state.position == Position(3, 3)
    assert not flow.receive(request.id, ActionPlan((walking(),)))


def test_npc_failure_keeps_prior_npc_effects_and_pending_turn(dice):
    session = build_session(dict(width=8, height=6, start=[2, 3], creatures=[
        dict(id='g1', name='Guarda 1', position=[3, 3]), dict(id='g2', name='Guarda 2', position=[2, 4]),
    ]), roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    director = Director(WorldPlan(), npc_plan(WorldAction('g1', 'move', 'O guarda se desloca.', destination=Position(3, 2))),
                        WorldError('Falha ao decidir o segundo guarda.'))
    flow = GameFlow(session, Interpreter(ActionPlan((RuleIntent('end_turn'),))), Narrator(), director)
    flow.submit('Encerro meu turno.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NPC_TURN)
    assert session.encounter.combat.active_id == 'g2'
    respond(flow, FlowStage.NPC_TURN)
    assert flow.status == FlowStatus.FAILED and not flow.pending
    assert session.creatures[0].position == Position(3, 2)
    assert session.creatures[1].position == Position(2, 4)
    assert session.encounter.combat.active_id == 'g2'
    assert any(e['operation'] == 'move' and e['actor_id'] == 'g1' for e in flow.report.world_events)
    assert not flow.narrator.calls


def test_npc_domain_impediment_ends_turn_without_replanning(dice):
    session = grid_session(guard=True, roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    director = Director(WorldPlan(), npc_plan(WorldAction('guard', 'attack', 'O guarda tenta atacar outra criatura.', 'guard')))
    interpreter = Interpreter(ActionPlan((RuleIntent('end_turn'),)))
    flow = GameFlow(session, interpreter, Narrator(Speech(off='A ação do guarda foi impedida.')), director)
    flow.submit('Encerro meu turno.')
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NPC_TURN)
    assert flow.report.status == 'blocked'
    assert session.encounter.combat.active_id == 'player'
    assert flow.report.world_events[-1]['fallback'] == 'end_turn'
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.COMPLETED and len(director.calls) == 2
    assert len(interpreter.calls) == 1


def test_npc_sequence_has_a_bound_if_executor_fails_to_advance(monkeypatch, dice):
    session = grid_session(guard=True, roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    flow = GameFlow(session, Interpreter(), Narrator(), Director(WorldPlan()))
    # Falha controlada do executor: não muda a iniciativa ao concluir a etapa.
    monkeypatch.setattr(flow.conversation, 'execute_npc_turn', lambda world: ExecutionReport())
    flow.submit('Ando.')
    respond(flow, FlowStage.NPC_TURN)
    assert flow.status == FlowStatus.FAILED and not flow.pending
    assert 'excedeu a sequência' in flow.message
    assert len(flow.world_director.calls) == 1


def test_player_at_zero_hp_does_not_resume_deferred_action_or_request_more_npcs(dice):
    session = build_session(dict(width=8, height=6, start=[2, 3], creatures=[
        dict(id='g1', name='Guarda 1', position=[3, 3]), dict(id='g2', name='Guarda 2', position=[2, 4]),
    ]), roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    # Crítico: 4d6, com a segunda rolagem de Savage Attacker; depois Graze.
    session.encounter.roller = dice(20, *([6] * 8), 1)
    director = Director(npc_plan(WorldAction('g1', 'attack', 'O primeiro guarda golpeia.', 'player')),
                        npc_plan(WorldAction('g2', 'attack', 'O segundo guarda golpeia.', 'player')))
    flow = GameFlow(session, Interpreter(), Narrator(Speech(on='Você cai.')), director)
    flow.submit('Ando para leste.')
    respond(flow, FlowStage.NPC_TURN)
    respond(flow, FlowStage.NPC_TURN)
    assert session.encounter.states['player'].hp == 0
    assert not flow.interpreter.calls and len(director.calls) == 2
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.COMPLETED
    assert session.state.position == Position(2, 3)


def test_provider_context_is_a_snapshot_and_logs_keep_correlation_in_worker(capture_logs):
    class MutatingNarrator:
        def narrate(self, context):
            context['character']['column'] = 999
            logging.getLogger('trama.fake_provider').info('provider.observed')
            raise NarrationError('Falha controlada.')

    with capture_logs() as stream, log_context(session_id='flow-session'):
        flow = GameFlow(grid_session(), narrator=MutatingNarrator())
        flow.start()
        request = flow.pending_request
        with ThreadPoolExecutor(max_workers=1) as worker:
            result = worker.submit(request.run).result(timeout=3)
        assert request.context['character']['column'] == 3
        flow.receive(request.id, result)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    selected = [r for r in records if r['event'] in {'provider.observed', 'game_flow.provider_failed', 'game_flow.failed'}]
    assert len(selected) == 3
    assert {r['session_id'] for r in selected} == {'flow-session'}
    assert {r['interaction_id'] for r in selected} == {flow.interaction_id}
    assert flow.session.state.position == Position(2, 3)


def test_narration_failure_during_reaction_still_allows_resuming_once(dice):
    session = grid_session(guard=True, roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    flow = GameFlow(session, Interpreter(ActionPlan((walking('west'),))),
                    Narrator(NarrationError('Resposta inválida.'), Speech(on='Você recua.')),
                    Director(npc_plan(WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3))), WorldPlan()))
    flow.submit('Ando para oeste.')
    respond(flow, FlowStage.NPC_TURN)
    respond(flow, FlowStage.NARRATE)
    assert flow.status == FlowStatus.FAILED and flow.awaiting_reaction
    flow.choose_opportunity(False)
    respond(flow, FlowStage.INTERPRET)
    respond(flow, FlowStage.WORLD)
    respond(flow, FlowStage.NARRATE)
    assert flow.session.state.position == Position(1, 3)
    assert flow.session.creatures[0].position == Position(5, 3)
    assert flow.report.stop_reason is None


def test_flow_can_be_imported_and_constructed_without_graphics_or_provider():
    code = '''
import importlib.abc
import sys
class RejectIO(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pygame', 'openai', 'argparse'} or fullname.startswith(('trama.ui', 'trama.infrastructure', 'trama.simulator')):
            raise AssertionError('Importação indevida: ' + fullname)
sys.meta_path.insert(0, RejectIO())
from trama.application.game_flow import GameFlow, FlowStatus
from trama.application.scenarios import build_session
flow = GameFlow(build_session({'width': 3, 'height': 3, 'start': [1, 1]}))
assert flow.status == FlowStatus.IDLE
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
