"""Pedidos reais, preparação e execução pelo mesmo fluxo do simulador."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.actions import ActionBudget
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.dungeon import DungeonSession
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, NarrativeIntent
from trama.application.session import GameSession
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_intent
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]


def dungeon():
    return DungeonSession.from_data(json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text()))


@pytest.fixture
def prison(dice):
    data = json.loads((ROOT / 'tests/fixtures/scenarios/legacy_cell_and_guards.json').read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data['start'])), scene,
                       creatures_from_data(data['creatures']), roller=dice())


def look():
    return NarrativeIntent('Olho ao redor.', 'look')


def move(target):
    return MovementIntent((), False, '', target)


def test_screenshot_open_move_look_executes_without_redundant_approach():
    s = dungeon()
    c = Conversation(s)
    prompt = 'Eu abro a grade da cela devagar e saio para olhar o corredor.'
    c.prepare(prompt)
    plan = sourced_plan(ActionPlan((DoorIntent('open', 'gate_1'), move('corridor'), look())), prompt)
    before = s.encounter.states.copy()
    report = c.execute(plan)
    assert report.status == 'completed'
    assert report.stop_reason is None
    assert report.unperformed_steps == 0
    assert s.scene.area_at(s.state.position).id == 'corridor'
    assert [e['operation'] for e in report.events] == ['open', 'move', 'look']
    assert report.events[0]['status'] == 'already_satisfied'
    assert report.events[0]['changed'] is False
    assert all('preparation_for' not in e for e in report.events)
    assert s.budget == ActionBudget()
    assert s.encounter.states == before
    assert not report.failures
    context = c.narration_context(report=report)
    assert context['execution']['player_movement']['occurred']
    assert context['execution']['status'] == 'completed'
    assert context['character']['column'] == s.state.position.x + 1


@pytest.mark.parametrize('operation,target', [('open', 'gate_1'), ('close', 'gate_4')])
def test_already_satisfied_has_no_time_inspection_or_state_side_effects(operation, target):
    s = dungeon()
    s.dungeon.waits = 1
    s.dungeon.guard_activity = 'bathroom'
    s.dungeon.bathroom_remaining = 3
    s.state = replace(s.state, free_meters=Decimal('4.5'))
    snapshot = (deepcopy(vars(s.dungeon)), s.state, s.budget, s.scene, s.encounter.states.copy(), s._examined_locks.copy())
    c = Conversation(s)
    report = c.execute(ActionPlan((DoorIntent(operation, target),)))
    assert report.status == 'already_satisfied'
    assert report.stop_reason is None
    assert not report.progress
    assert not report.world_events
    assert (vars(s.dungeon), s.state, s.budget, s.scene, s.encounter.states, s._examined_locks) == snapshot
    assert c.narration_context(report=report)['allow_on']
    reply = c.finish(Speech('A grade já está no estado pedido.'), c.narration_context(report=report))
    assert reply.on and not reply.off


def test_closed_door_gets_approach_before_interaction(prison):
    c = Conversation(prison)
    report = c.execute(ActionPlan((DoorIntent('open', 'guard_door'), look())))
    assert report.stop_reason is None
    assert prison.state.position == Position(12, 5)
    assert prison.scene.passages[1].is_open
    assert [e['operation'] for e in report.events] == ['move', 'open', 'look']
    assert report.events[0]['preparation_for'] == {'operation': 'open', 'target_id': 'guard_door', 'step_index': 0}
    assert report.events[0]['traveled_meters'] == 13.5
    assert report.events[1]['status'] == 'completed'
    assert prison.state.spent_meters == 0
    assert prison.budget == ActionBudget()


def test_explicit_approach_is_not_repeated(prison):
    c = Conversation(prison)
    plan = ActionPlan((move('guard_door'), DoorIntent('open', 'guard_door')))
    world = WorldPlan((WorldReaction(1, 1, (WorldAction('guard_1', 'say', 'Não deve ocorrer.'),)),))
    report = c.execute(plan, world)
    assert report.stop_reason is None
    assert [e['operation'] for e in report.events] == ['move', 'open']
    assert report.world_events == ()  # Nenhuma casa de aproximação na etapa 1.


def test_explicit_no_movement_is_respected(prison):
    before = prison.state
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door', False), look())))
    assert report.status == 'blocked'
    assert report.unperformed_steps == 1
    assert not report.progress
    assert prison.state == before
    assert not prison.scene.passages[1].is_open


def test_locked_door_keeps_completed_approach_and_does_not_unlock(prison):
    prison.scene = replace(prison.scene, passages=tuple(replace(p, locked=True) if p.id == 'guard_door' else p
                                                      for p in prison.scene.passages))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'), look())))
    assert report.status == 'blocked'
    assert report.progress and report.unperformed_steps == 1
    assert prison.state.position == Position(12, 5)
    assert 'trancada' in report.stop_reason
    assert prison.scene.passages[1].locked and not prison.scene.passages[1].is_open
    assert prison.budget == ActionBudget()
    assert report.failures[-1].origin == Position(12, 5)


def test_approach_stops_at_another_closed_gate_and_does_not_open_it(prison):
    prison.scene = prison.scene.with_passage('cell_gate', False)
    prison.grid = prison.scene.grid
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'), look())))
    assert report.status == 'blocked'
    assert report.progress and report.unperformed_steps == 1
    assert prison.state.position == Position(4, 5)
    assert all(not p.is_open for p in prison.scene.passages)
    assert report.events[-1]['preparation_incomplete']
    assert report.failures[-1].skipped_actions[0]['operation'] == 'open'
    assert prison.budget == ActionBudget()


def test_unreachable_door_does_not_teleport_or_spend_resources(prison):
    # Fecha definitivamente o corredor com uma parede (não é passagem que possa abrir).
    wall = frozenset(Position(8, y) for y in range(prison.grid.height))
    prison.grid = replace(prison.grid, blocked=prison.grid.blocked | wall)
    prison.scene = replace(prison.scene, grid=prison.grid)
    before = prison.state
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)))
    assert report.status == 'blocked'
    assert not report.progress
    assert prison.state == before
    assert prison.budget == ActionBudget()


def test_turn_movement_exhaustion_stops_before_opening_without_dash(prison, dice):
    prison.encounter.roller = dice(20, 19, 1)
    prison.encounter.start(('guard_1',))
    prison.state = replace(prison.state, spent_meters=Decimal('7.5'))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'), look())))
    assert report.status == 'blocked'
    assert report.progress and report.unperformed_steps == 1
    assert prison.state.position == Position(4, 5)
    assert prison.state.spent_meters == 9
    assert not prison.state.dash_used
    assert prison.budget == ActionBudget()
    assert not prison.scene.passages[1].is_open
    assert report.failures[-1].code == 'insufficient_movement'


def test_successful_turn_approach_pays_movement_and_free_interaction(prison, dice):
    prison.encounter.roller = dice(20, 19, 1)
    prison.encounter.start(('guard_1',))
    prison.state = replace(prison.state, position=Position(10, 5))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)))
    assert report.status == 'completed'
    assert prison.state.position == Position(12, 5)
    assert prison.state.spent_meters == 3
    assert prison.budget.free_interaction_used
    assert not prison.budget.action_used


def test_no_interaction_budget_blocks_before_approach(prison, dice):
    prison.encounter.roller = dice(20, 19, 1)
    prison.encounter.start(('guard_1',))
    prison.state = replace(prison.state, position=Position(10, 5))
    prison.budget = ActionBudget(free_interaction_used=True, action_used=True)
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)))
    assert report.status == 'blocked' and not report.progress
    assert prison.state.position == Position(10, 5)
    assert prison.state.spent_meters == 0
    assert not prison.scene.passages[1].is_open


def test_world_interrupts_implicit_approach_at_actual_checkpoint(prison):
    reaction = WorldReaction(0, 2, (WorldAction('guard_1', 'say', 'Alto!'),),
                             interrupt=True, reason='O guarda intercepta a aproximação.')
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'), look())), WorldPlan((reaction,)))
    assert report.status == 'blocked'
    assert report.progress and report.unperformed_steps == 1
    assert prison.state.position == Position(5, 5)
    assert len(prison.last_path) == 3
    assert not prison.scene.passages[1].is_open
    assert report.world_events[0]['after_squares'] == 2
    assert report.events[-1]['status'] == 'blocked'


def test_world_starts_conflict_during_approach_without_opening(prison, dice):
    prison.encounter.roller = dice(1, 2, 20)
    reaction = WorldReaction(0, 2, (WorldAction('guard_1', 'start_conflict', 'O guarda intercepta a fuga.'),))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)), WorldPlan((reaction,)))
    assert report.status == 'blocked'
    assert prison.encounter.combat.active_id == 'guard_1'
    assert prison.state.position == Position(5, 5)
    assert not prison.scene.passages[1].is_open


def test_unreached_world_checkpoint_during_approach_does_not_fire(prison):
    reaction = WorldReaction(0, 99, (WorldAction('guard_1', 'say', 'Não deve ocorrer.'),))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)), WorldPlan((reaction,)))
    assert report.status == 'completed'
    assert report.world_events == ()


def test_after_interaction_world_reply_fires_after_open_not_after_approach(prison):
    reaction = WorldReaction(0, None, (WorldAction('guard_1', 'say', 'A porta abriu.'),))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('open', 'guard_door'),)), WorldPlan((reaction,)))
    assert prison.scene.passages[1].is_open
    assert report.world_events[0]['after_squares'] is None
    assert report.world_events[0]['text'] == 'A porta abriu.'


def test_world_context_exposes_preparation_and_keeps_original_indices(prison):
    c = Conversation(prison)
    plan = ActionPlan((look(), DoorIntent('open', 'guard_door'), look()))
    context = c.world_context(plan)
    assert len(context['player_plan']) == 3
    prepared = context['player_plan'][1]['preparation'][0]
    assert prepared['operation'] == 'move'
    assert prepared['target_id'] == 'guard_door'
    assert prepared['proposed_path'][-1] == [13, 6]
    assert not prepared['dash']
    json.dumps(context)
    assert prison.state == prison.initial_state  # Consulta não executa movimento.


def test_scenario_guard_can_interrupt_preparation(dice):
    s = dungeon()
    s.encounter.roller = dice(1, 20, 20, 19, 1)
    report = Conversation(s).execute(ActionPlan((DoorIntent('open', 'gate_4'), look())))
    assert report.status == 'blocked'
    assert report.progress
    assert s.encounter.combat
    assert not s._passage('gate_4').is_open
    assert s.budget.free_interaction_used is False
    assert any(e['operation'] == 'start_conflict' for e in report.world_events)


def test_strict_door_contract_and_no_movement_flag():
    assert parse_intent('{"operation":"open","target_id":"guard_door","allow_approach":false}') == DoorIntent('open', 'guard_door', False)
    with pytest.raises(ValueError):
        DoorIntent('open', 'guard_door', 'false')


def test_production_adapters_receive_actual_case_and_narrate_real_movement():
    s = dungeon()
    c = Conversation(s)
    prompt = 'Eu abro a grade da cela devagar e saio para olhar o corredor.'
    speech = c.prepare(prompt)
    outputs = iter([
        {'request_parts': [{'text': prompt, 'kind': 'execute', 'operations': ['open', 'move', 'look'], 'step_indices': [0, 1, 2]}],
         'steps': [{'operation': 'open', 'target_id': 'gate_1', 'allow_approach': True},
                   {'operation': 'move', 'target_id': 'corridor', 'segments': [], 'dash': False, 'clarification': ''},
                   {'operation': 'look', 'text': 'Olho o corredor.'}]},
        {'reactions': []},
        {'on': 'A grade já está aberta. Você sai para o corredor iluminado por tochas.', 'off': ''},
    ])
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(status='completed', output_text=json.dumps(next(outputs)), output=[], usage=None)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    plan = OpenAIIntentInterpreter(client).interpret(speech.on, c.interpretation_context())
    world = OpenAIWorldDirector(client).decide(c.world_context(plan))
    report = c.execute(plan, world)
    context = c.narration_context(speech, report)
    final = c.finish(OpenAINarrator(client).narrate(context), context)
    assert report.status == 'completed'
    assert final.on and not final.off
    sent = json.loads(requests[-1]['input'])
    assert sent['execution']['player_movement']['occurred']
    assert sent['execution']['events'][0]['status'] == 'already_satisfied'
    assert sent['perception']['current_place'] == 'Corredor'


def test_closing_also_prepares_only_necessary_approach(prison):
    prison.scene = prison.scene.with_passage('guard_door', True)
    prison.grid = prison.scene.grid
    report = Conversation(prison).execute(ActionPlan((DoorIntent('close', 'guard_door'),)))
    assert report.status == 'completed'
    assert prison.state.position == Position(12, 5)
    assert not prison.scene.passages[1].is_open
    assert [e['operation'] for e in report.events] == ['move', 'close']
    assert report.events[0]['preparation_for']['operation'] == 'close'


def test_prepared_movement_uses_opportunity_attack_rules(prison, dice):
    # Só um guarda adjacente para isolar a reação durante a aproximação.
    prison.creatures = (replace(prison.creatures[0], position=Position(15, 5)),)
    prison.scene = prison.scene.with_passage('guard_door', True)
    prison.grid = prison.scene.grid
    prison.state = replace(prison.state, position=Position(14, 5))
    prison.encounter.roller = dice(20, 19, 1, 1)
    prison.encounter.start(('guard_1',))
    report = Conversation(prison).execute(ActionPlan((DoorIntent('close', 'cell_gate'),)))
    attacks = [e for e in report.world_events if e['operation'] == 'opportunity_attack']
    assert len(attacks) == 1
    assert prison.encounter.budgets['guard_1'].reaction_used
    assert not prison.encounter.budgets['guard_1'].action_used
    assert prison.encounter.states['player'].hp < prison.encounter.player_sheet.max_hp
    assert not prison.state.dash_used
