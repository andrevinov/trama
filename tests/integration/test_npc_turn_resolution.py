"""Conclusão de turnos com progresso parcial, sem IA e sem renovar recursos."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan, world_actions

from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.game_flow import FlowStage, GameFlow
from trama.application.game_runner import GameRunner, RunStatus
from trama.application.intents import ActionPlan, RuleIntent
from trama.application.scenarios import build_session
from trama.application.travel import TravelExecutor
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.application.world_resolution import WorldExecutor
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]


def moving(destination):
    return WorldAction('watcher', 'move', 'O vigia se aproxima.', destination=Position(*destination))


def plan(*actions):
    return WorldPlan((WorldReaction(0, 0, actions),))


def npc_session(dice, *, player=None):
    data = json.loads((ROOT / 'src/trama/scenarios/npc_turn_corridor.json').read_text())
    if player is not None:
        # Variante de cenário validada pelo mesmo construtor da aplicação.
        data['start'] = player
    session = build_session(data, roller=dice(20, 19, 1))
    session.execute(RuleIntent('start_combat'))
    session.execute(RuleIntent('end_turn'))
    session.encounter.roller = dice()
    return session


def test_destination_beyond_budget_finishes_turn_after_nine_meters(dice):
    session = npc_session(dice)
    report = Conversation(session).execute_npc_turn(plan(moving((3, 2))))
    assert not report.stop_reason and not report.failures
    assert session.creatures[0].position == Position(15, 2)
    move, end = world_actions(report.world_events)
    assert move['cost_meters'] == 9 and move['traveled_meters'] == 9
    assert move['status'] == 'movement_limited' and move['stop_code'] == 'insufficient_movement'
    assert move['stop_reason'] is None and '0 m' in move['movement_limit_reason']
    assert end['operation'] == 'end_turn' and 'fallback' not in end
    assert session.encounter.combat.active_id == 'player' and session.encounter.combat.round == 2
    assert session.encounter.states['player'].hp == 28


def test_exhausted_movement_does_not_skip_a_legal_attack(dice):
    session = npc_session(dice, player=[14, 2])
    session.encounter.roller = dice(1)  # Graze: 3 de dano, ação única.
    report = Conversation(session).execute_npc_turn(plan(moving((13, 2)),
        WorldAction('watcher', 'attack', 'O vigia golpeia.', 'player', weapon='greatsword')))
    assert not report.stop_reason and not report.failures
    assert [e['operation'] for e in world_actions(report.world_events)] == ['move', 'attack', 'end_turn']
    assert report.world_events[0]['cost_meters'] == 9
    assert session.creatures[0].position == Position(15, 1)
    assert session.encounter.states['player'].hp == 25
    assert session.encounter.budgets['watcher'].action_used
    assert session.encounter.combat.active_id == 'player'


def test_unreachable_attack_after_limited_move_ends_turn_without_free_damage(dice):
    session = npc_session(dice)
    conversation = Conversation(session)
    report = conversation.execute_npc_turn(plan(moving((3, 2)),
        WorldAction('watcher', 'attack', 'Tenta golpear à distância.', 'player'),
        WorldAction('watcher', 'say', 'Esta fala deve ser descartada.')))
    assert len(report.failures) == 1 and report.failures[0].operation == 'attack'
    assert 'fora de alcance' in report.stop_reason
    assert [e['operation'] for e in world_actions(report.world_events)] == ['move', 'end_turn']
    assert report.world_events[-1]['fallback'] == 'end_turn'
    assert [a['operation'] for a in report.failures[0].skipped_actions] == ['say']
    assert session.encounter.combat.active_id == 'player'
    assert not conversation.narration_context()['previous_execution']['situation']['turn_pending']
    assert session.encounter.states['player'].hp == 28
    assert not session.encounter.budgets['watcher'].action_used
    assert not session.encounter.roller.sides


def test_multiple_moves_and_prior_progress_share_the_same_budget(dice):
    session = npc_session(dice)
    first = WorldExecutor(session).execute(moving((18, 2)))
    assert first['cost_meters'] == 4.5
    report = Conversation(session).execute_npc_turn(plan(moving((3, 2)), moving((4, 2)),
        WorldAction('watcher', 'say', 'Ainda posso falar.')))
    assert not report.stop_reason and not report.failures
    assert [e['cost_meters'] for e in report.world_events if e['operation'] == 'move'] == [4.5, 0]
    assert session.creatures[0].position == Position(15, 2)
    assert [e['operation'] for e in world_actions(report.world_events)] == ['move', 'move', 'say', 'end_turn']
    assert session.encounter.combat.active_id == 'player'


@pytest.mark.parametrize('accept', [False, True])
def test_opportunity_still_pauses_then_resumes_up_to_the_movement_limit(dice, accept):
    session = npc_session(dice, player=[20, 2])
    conversation = Conversation(session)
    report = conversation.execute_npc_turn(plan(moving((1, 2))))
    assert report.stop_reason and session.pending_opportunity
    assert session.encounter.combat.active_id == 'watcher'
    assert not any(e['operation'] == 'end_turn' for e in report.world_events)
    assert conversation.pending_npc_turn is not None
    session.encounter.roller = dice(1) if accept else dice()
    TravelExecutor(session).resolve(accept)
    report = conversation.execute_npc_turn(conversation.pending_npc_turn)
    assert not session.pending_opportunity and not conversation.pending_npc_turn
    assert not report.stop_reason and not report.failures
    assert session.encounter.combat.active_id == 'player'
    assert sum(e.get('cost_meters', 0) for e in report.world_events) <= 9


def test_failed_npc_action_does_not_block_the_next_npc_or_repeat_decisions(dice):
    session = build_session(dict(width=12, height=6, start=[1, 2], creatures=[
        dict(id='g1', name='Primeiro', position=[9, 2]),
        dict(id='g2', name='Segundo', position=[9, 4]),
    ]), roller=dice(20, 19, 10, 1))
    session.execute(RuleIntent('start_combat'))
    decisions = []

    def decide(context):
        if context['phase'] != 'npc_turn':
            return WorldPlan()
        actor = context['combat']['active_id']
        decisions.append(actor)
        action = (WorldAction(actor, 'attack', 'Tenta golpear longe demais.', 'player') if actor == 'g1' else
                  WorldAction(actor, 'move', 'O segundo avança.', destination=Position(8, 4)))
        return WorldPlan((WorldReaction(0, 0, (action,)),))

    flow = GameFlow(session,
        interpreter=SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((RuleIntent('end_turn'),)), prompt)),
        world_director=SimpleNamespace(decide=decide),
        narrator=SimpleNamespace(narrate=lambda context: Speech(on='Agora é seu turno.')))
    result = GameRunner(flow).submit('Encerro meu turno.')
    assert result.status == RunStatus.COMPLETED and not result.awaiting_reaction
    assert decisions == ['g1', 'g2']
    assert sum(r.stage == FlowStage.NPC_TURN for r in result.requests) == 2
    assert session.encounter.combat.active_id == 'player' and session.encounter.combat.round == 2
    assert session.creatures[1].position == Position(8, 4)
    assert session.encounter.states['player'].hp == 28
    assert len(result.report.failures) == 1 and result.report.failures[0].actor_id == 'g1'
    assert [e['actor_id'] for e in result.report.world_events if e.get('fallback')] == ['g1']

