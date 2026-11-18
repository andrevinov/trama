"""Inspeção geral, sem IA: efeitos, limites e preservação de furtividade."""

from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from conftest import sourced_plan, judged_world
from trama.actions import ActionBudget
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow
from trama.application.game_runner import GameRunner
from trama.application.intents import (
    ActionPlan, DoorIntent, InspectionIntent, MovementIntent, MovementSegment, RequestPart, RuleIntent,
)
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.infrastructure.openai_intent_interpreter import parse_intent
from trama.spatial import Position


def room(*, locked=False, checkable=True, start=(3, 2), enemy=False, roller=None):
    return build_session(dict(width=10, height=5, start=list(start), player=dict(armor='none', weapons=[]),
        areas=[dict(id='west', name='Oeste', x=1, y=1, width=3, height=3),
               dict(id='east', name='Leste', x=5, y=1, width=4, height=3)],
        passages=[dict(id='door', name='Porta', kind='door', position=[4, 2],
                       is_open=False, locked=locked, lock_checkable=checkable, connects=['west', 'east'])],
        creatures=[dict(id='sentinel', name='Sentinela', position=[7, 2],
                        senses=dict(can_hear=False))] if enemy else []), roller=roller)


def passage(context, world=False):
    return (context['world']['map'] if world else context['map'])['scene']['passages'][0]


@pytest.mark.parametrize('locked', [False, True])
def test_mechanism_inspection_learns_lock_without_operating_or_entering(locked, dice):
    s = room(locked=locked, roller=dice())
    c = Conversation(s)
    assert passage(s.interpreter_context())['locked'] is None
    assert passage(s.interpreter_context(), world=True)['locked'] is locked
    before = s.scene, s.state, s.budget, deepcopy(s.encounter.states)
    report = c.execute(ActionPlan((InspectionIntent('door', volume='quiet'),)))
    assert report.status == 'completed' and not report.failures
    assert [e['operation'] for e in report.events] == ['inspect_passage']
    assert report.events[0]['locked'] is locked
    assert report.events[0]['physical_change'] is False
    assert (s.scene, s.state, s.budget, s.encounter.states) == before
    assert passage(s.interpreter_context())['locked'] is locked
    assert s.map_view()['passage_lock_labels']['door'] == ('trancada' if locked else 'destrancada')
    assert any(m['claim'] == dict(subject_id='door', predicate='locked', value=str(locked).lower())
               for m in s.interpreter_context()['knowledge'])
    assert c.narration_context(report=report)['allow_on']


@pytest.mark.parametrize('locked', [True, False])
def test_visual_inspection_does_not_disclose_hidden_lock_even_up_close(locked):
    s = room(locked=locked)
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', 'visual', allow_approach=False),)))
    assert report.status == 'completed' and not report.failures
    assert report.events[0]['is_open'] is False and report.events[0]['locked'] is None
    assert passage(s.interpreter_context())['locked'] is None
    assert s.budget == ActionBudget() and not s._examined_locks


def test_inaccessible_mechanism_remains_unknown_without_inventing_a_check(dice):
    s = room(locked=True, checkable=False, roller=dice())
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', volume='quiet'),)))
    assert report.status == 'completed'
    assert report.events[0]['locked'] is None
    assert passage(s.interpreter_context())['locked'] is None
    assert s.scene.passages[0].locked and not s.scene.passages[0].is_open


def test_quiet_inspection_keeps_existing_stealth_and_does_not_teach_spectators(dice):
    s = room(enemy=True, roller=dice(16))
    c = Conversation(s)
    hidden = c.execute(ActionPlan((RuleIntent('hide'),)))
    assert not hidden.failures and s.perception.hidden_total == 17
    report = c.execute(ActionPlan((InspectionIntent('door', volume='quiet'),)))
    assert not report.failures and s.perception.hidden_total == 17
    assert not any(e['operation'] in {'hide', 'check', 'search'} for e in report.world_events)
    assert not any(m['claim']['predicate'] == 'locked' and m['owner_id'] == 'sentinel'
                   for m in s.knowledge.store.export()['memories'])


def test_a_spectator_sees_the_inspection_without_learning_its_tactile_result():
    s = room(enemy=True, locked=True)
    s.scene = replace(s.scene, passages=(replace(s.scene.passages[0], kind='gate'),))
    assert s.npc_sees_player('sentinel')
    s.execute(InspectionIntent('door', volume='quiet'))
    memories = s.knowledge.store.export()['memories']
    assert any(m['owner_id'] == 'player' and m['claim']['predicate'] == 'locked' for m in memories)
    assert not any(m['owner_id'] == 'sentinel' and m['claim']['predicate'] == 'locked' for m in memories)


def test_normal_mechanism_noise_ends_hiding_and_uses_the_real_perception_path(dice):
    s = room(enemy=True, roller=dice(16))
    s.execute(RuleIntent('hide'))
    assert s.perception.hidden_total == 17
    s.execute(InspectionIntent('door'))
    assert s.perception.hidden_total is None


@pytest.mark.parametrize('method', ['visual', 'mechanism'])
def test_inspection_without_approach_never_moves(method):
    s = room(start=(1, 2))
    before = s.state, s.scene, s.budget
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', method, allow_approach=False),)))
    assert (s.state, s.scene, s.budget) == before
    if method == 'mechanism':
        assert report.failures and report.status == 'blocked' and not report.events
    else:
        assert not report.failures and report.events[0]['locked'] is None


def test_contextual_approach_stops_in_reach_without_opening():
    s = room(start=(1, 2))
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', volume='quiet'),)))
    assert not report.failures
    assert [e['operation'] for e in report.events] == ['move', 'inspect_passage']
    assert s.state.position in {Position(3, 1), Position(3, 2), Position(3, 3)}
    assert not s.scene.passages[0].is_open


def test_visual_inspection_in_darkness_rejects_without_learning():
    s = room()
    s.scene = replace(s.scene, dark=frozenset({Position(4, 2)}))
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', 'visual', allow_approach=False),)))
    assert report.failures and not report.events and not s._examined_locks


def test_visual_inspection_keeps_immediate_movement_and_is_allowed_during_parley():
    s = room(enemy=True)
    s.scene = s.scene.with_passage('door', True)
    s.grid = s.scene.movement_grid
    s.offer_parley('sentinel', 'O que deseja?')
    s.state = replace(s.state, free_meters=Decimal('4.5'))
    before = s.state, s.scene, s.budget, deepcopy(s.agency.intents)
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', 'visual', allow_approach=False),)))
    assert not report.failures
    assert (s.state, s.scene, s.budget, s.agency.intents) == before


def test_mechanism_inspection_remains_blocked_during_parley():
    s = room(enemy=True)
    s.scene = s.scene.with_passage('door', True)
    s.grid = s.scene.movement_grid
    s.offer_parley('sentinel', 'O que deseja?')
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door', volume='quiet'),)))
    assert report.failures and not report.events and not s._examined_locks


def test_turn_based_inspection_pays_interaction_and_rejects_before_walking(dice):
    s = room(enemy=True, roller=dice(20, 20, 1))
    s.scene = s.scene.with_passage('door', True)
    s.grid = s.scene.movement_grid
    s.execute(RuleIntent('start_combat'))
    assert s.encounter.combat.active_id == 'player'
    s.execute(InspectionIntent('door', volume='quiet'))
    assert s.budget.free_interaction_used and s.budget.action_available
    s.execute(InspectionIntent('door', volume='quiet'))
    assert not s.budget.action_available
    before = s.state, s.scene, s.budget, deepcopy(s._examined_locks)
    report = Conversation(s).execute(ActionPlan((InspectionIntent('door'),)))
    assert report.failures and (s.state, s.scene, s.budget, s._examined_locks) == before


def test_reset_forgets_inspected_lock_and_hidden_world_changes_do_not_update_it():
    s = room()
    s.execute(InspectionIntent('door', volume='quiet'))
    s.scene = replace(s.scene, passages=(replace(s.scene.passages[0], locked=True),))
    assert passage(s.interpreter_context())['locked'] is False
    assert passage(s.interpreter_context(), world=True)['locked'] is True
    s.reset()
    assert passage(s.interpreter_context())['locked'] is None


def test_inspection_roundtrip_and_invalid_external_parameters():
    intent = InspectionIntent('door', volume='quiet', allow_approach=False)
    assert parse_intent(json.dumps(asdict(intent))) == intent
    for values in [dict(method='visual'), dict(volume='loud'), dict(target_id=''), dict(allow_approach=1)]:
        with pytest.raises(ValueError):
            InspectionIntent(**(dict(target_id='door') | values))


def test_pure_clarification_skips_world_and_all_actions_even_during_parley():
    s = room(enemy=True)
    s.scene = s.scene.with_passage('door', True)
    s.grid = s.scene.movement_grid
    s.offer_parley('sentinel', 'O que deseja?')
    before = s.state, s.scene, s.budget, deepcopy(s.agency.intents)
    prompt = 'Checo uma fechadura, sem decidir qual.'
    plan = ActionPlan((MovementIntent((), False, 'Qual passagem deseja conferir?'),),
                      (RequestPart(prompt, 'unclear', ('clarify',), (0,)),))
    flow = GameFlow(s, SimpleNamespace(interpret=lambda *_: plan),
                    SimpleNamespace(narrate=lambda _: Speech(off='Indique a passagem.')),
                    SimpleNamespace(decide=lambda _: pytest.fail('Esclarecimento não consulta o Mundo.')))
    result = GameRunner(flow).submit(prompt)
    assert result.status == 'completed'
    assert [r.stage for r in result.requests] == ['interpret', 'narrate']
    assert not result.report.events and not result.report.world_events
    assert result.report.failures[0].code == 'clarification_required'
    assert (s.state, s.scene, s.budget, s.agency.intents) == before


def test_mixed_plan_keeps_real_action_and_does_not_execute_world_at_clarification():
    s = room(enemy=True, start=(1, 2))
    c = Conversation(s)
    steps = (MovementIntent((MovementSegment('south', 1),), False, ''),
             MovementIntent((), False, 'Qual fechadura?'))
    # Uma resposta indevida na etapa de esclarecimento não ganha efeitos.
    report = c.execute(ActionPlan(steps), WorldPlan((WorldReaction(1, 0, (
        WorldAction('sentinel', 'say', 'Não pode ser executado.'),)),)))
    assert s.state.position == Position(1, 3)
    assert [e['operation'] for e in report.events] == ['move']
    assert not any(e['operation'] == 'say' for e in report.world_events)
    assert report.failures[0].code == 'clarification_required'


def test_flow_uses_interpreter_world_narrator_with_actual_inspection():
    s = room()
    prompt = 'Eu confiro se a porta está trancada, com cuidado.'
    flow = GameFlow(s, SimpleNamespace(interpret=lambda p, _: sourced_plan(
        ActionPlan((InspectionIntent('door', volume='quiet'),)), p)),
        SimpleNamespace(narrate=lambda ctx: Speech(on=ctx['execution']['events'][0]['summary'])),
        SimpleNamespace(decide=lambda ctx: judged_world(WorldPlan(), ctx)))
    result = GameRunner(flow).submit(prompt)
    assert result.status == 'completed' and not result.report.failures
    assert [r.stage for r in result.requests] == ['interpret', 'world', 'narrate']
    assert result.requests[-1].context['execution']['events'][0]['locked'] is False
    assert result.reply.on and not s.scene.passages[0].is_open
