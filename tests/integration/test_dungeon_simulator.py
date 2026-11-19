"""Cenário real do simulador, regras locais e dados controlados; nenhuma rede."""

from dataclasses import replace
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pytest

from trama.actions import ActionError
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.conversation import Conversation
from trama.application.dungeon import DungeonSession
from trama.application.intents import (
    ActionPlan, DoorIntent, MovementIntent, NarrativeIntent, RuleIntent, ScenarioIntent,
)
from trama.application.modes import GameMode
from trama.characters import CharacterError
from trama.infrastructure.openai_intent_interpreter import parse_intent
from trama.spatial import Position
from conftest import sourced_plan

SCENARIO = Path(__file__).resolve().parents[2] / 'src/trama/scenarios/dungeon_escape.json'


def dungeon(roller=None):
    return DungeonSession.from_data(json.loads(SCENARIO.read_text()), roller=roller)


def move(s, target):
    return s.execute(MovementIntent((), False, '', target))


def interact(s, operation, target):
    return s.execute(ScenarioIntent(operation, target))


def reach_storage(s):
    interact(s, 'sneak', 'gate_4')
    s.execute(DoorIntent('open', 'gate_4'))
    move(s, 'cell_4')


def find_equipment(s):
    reach_storage(s)
    interact(s, 'investigate', 'cell_4')
    move(s, 'longsword')
    interact(s, 'take', 'longsword')
    move(s, 'cleaner_uniform')
    interact(s, 'take', 'cleaner_uniform')


def reach_guard_door(s):
    if s.perception.hidden_total is None:
        interact(s, 'sneak', 'guard_door')
    else:
        move(s, 'guard_door')


def wait_for_bathroom(s):
    s.execute(NarrativeIntent('Espero.', 'wait'))
    s.execute(NarrativeIntent('Continuo esperando.', 'wait'))


def test_layout_inventory_and_initial_context():
    s = dungeon()
    assert len([a for a in s.scene.areas if a.id.startswith('cell_')]) == 4
    corridor = next(a for a in s.scene.areas if a.id == 'corridor')
    assert corridor.width == 2
    assert len(s.creatures) == 1
    assert s.encounter.player_sheet.level == 3
    assert s.encounter.player_sheet.armor_class == 11
    assert s.encounter.player_sheet.weapons == ()
    assert s.encounter.states['player'].javelins_remaining == 0
    assert s.dungeon.inventory == set()
    assert s._passage('gate_1').is_open
    assert s._passage('gate_2').locked
    assert not s._passage('gate_4').locked
    context = Conversation(s).narration_context(initial=True)
    assert 'magicamente' in context['world']['scenario']['initial_event']
    assert context['perception']['visible_objects'] == []
    assert 'prisoner' not in s.encounter.sheets


def test_discovery_equipment_and_armor_remain_actual(dice):
    s = dungeon(dice(20, 20))  # Ruído perto do prisioneiro, Investigação.
    find_equipment(s)
    assert s.dungeon.inventory == {'longsword', 'cleaner_uniform'}
    assert s.encounter.player_sheet.weapons == ('longsword',)
    interact(s, 'wear', 'cleaner_uniform')
    interact(s, 'conceal', 'longsword')
    assert s.dungeon.sword_concealed
    assert s.character_context()['armor_class'] == 11
    interact(s, 'drop', 'longsword')
    assert s.encounter.player_sheet.weapons == ()
    assert not s.dungeon.sword_concealed
    assert s.item_positions['longsword'] == s.state.position


def test_investigation_failure_does_not_hide_obvious_sword(dice):
    s = dungeon(dice(20, 1))
    reach_storage(s)
    interact(s, 'investigate', 'cell_4')
    assert 'longsword' in s.known_objects()
    assert 'cleaner_uniform' not in s.known_objects()
    with pytest.raises(ActionError):
        interact(s, 'take', 'cleaner_uniform')


def test_items_and_locked_cells_require_reach_and_key(dice):
    s = dungeon(dice(20))
    with pytest.raises(ActionError):
        interact(s, 'investigate', 'cell_4')
    interact(s, 'sneak', 'gate_2')
    with pytest.raises(ActionError, match='trancada'):
        s.execute(DoorIntent('open', 'gate_2'))
    with pytest.raises(ActionError, match='chave'):
        interact(s, 'unlock', 'gate_2')
    assert not s.dungeon.prisoner_free


def test_closed_storage_lock_is_not_metagame_information(dice):
    s = dungeon(dice(20))
    interact(s, 'sneak', 'gate_4')
    p = next(p for p in s.interpreter_context()['map']['scene']['passages'] if p['id'] == 'gate_4')
    assert p['locked'] is None
    world = next(p for p in s.interpreter_context()['world']['map']['scene']['passages'] if p['id'] == 'gate_4')
    assert world['locked'] is False
    s.execute(DoorIntent('open', 'gate_4'))
    assert s._passage('gate_4').is_open


def test_noise_wakes_prisoner_and_can_bring_guard(dice):
    s = dungeon(dice())  # Passos evidentes e grito alcançável; nenhum teste aleatório.
    result = move(s, 'gate_2')
    assert s.dungeon.prisoner_awake
    assert s.dungeon.guard_alert
    assert s.guard.position == Position(9, 5)
    assert s.mode == GameMode.NARRATED
    assert s.parley_pending and s.encounter.combat is None
    assert result.stop_code == 'parley_pending'
    assert s.encounter.roller.sides == []
    assert s._passage('guard_door').is_open
    assert result.cost_meters > 0
    assert any(e['operation'] == 'say' and e['actor_id'] == 'prisoner' for e in s.drain_world_events())


def test_wake_explicitly_requests_release_and_guard_can_be_outside_hearing(dice):
    data = json.loads(SCENARIO.read_text())
    data['creatures'][0]['senses']['hearing_range_meters'] = 0
    s = DungeonSession.from_data(data, roller=dice(20))
    interact(s, 'sneak', 'gate_2')
    interact(s, 'wake', 'prisoner')
    assert s.dungeon.prisoner_awake
    assert not s.dungeon.guard_alert
    assert 'cell_key' in s.known_objects()
    assert 'cell_key' not in s.dungeon.inventory


def test_bathroom_listening_and_key_theft_without_detection(dice):
    s = dungeon(dice(20, 20))
    reach_guard_door(s)
    interact(s, 'listen', 'guard_door')
    wait_for_bathroom(s)
    assert s.dungeon.guard_activity == 'bathroom'
    assert s.guard.position == Position(16, 2)
    assert not s._passage('bathroom_door').is_open
    s.execute(DoorIntent('open', 'guard_door'))
    move(s, 'cell_key')
    interact(s, 'take', 'cell_key')
    assert 'cell_key' in s.dungeon.inventory
    assert not s.dungeon.guard_alert


def test_guard_returns_after_bathroom_window(dice):
    s = dungeon(dice(20))
    reach_guard_door(s)
    wait_for_bathroom(s)
    for _ in range(4):
        s.execute(NarrativeIntent('Aguardo.', 'wait'))
    assert s.dungeon.guard_activity == 'on_duty'
    assert s.guard.position == Position(10, 3)


def test_uniform_without_weapon_can_convince_guard_and_escape(dice):
    s = dungeon(dice(20, 20, 20))
    find_equipment(s)
    interact(s, 'drop', 'longsword')
    interact(s, 'wear', 'cleaner_uniform')
    reach_guard_door(s)
    s.execute(DoorIntent('open', 'guard_door'))
    assert s.dungeon.disguise == 'accepted'
    assert s.mode == GameMode.NARRATED
    move(s, 'exit_door')
    s.execute(DoorIntent('open', 'exit_door'))
    interact(s, 'escape', 'outside')
    assert s.dungeon.escaped
    assert not s.dungeon.companion_escaped


def test_disguise_failure_starts_real_initiative_and_stops_plan(dice):
    s = dungeon(dice(20, 20, 1, 20, 19, 1))
    find_equipment(s)
    interact(s, 'wear', 'cleaner_uniform')
    reach_guard_door(s)
    report = Conversation(s).execute(ActionPlan((DoorIntent('open', 'guard_door'),
                                                MovementIntent((), False, '', 'guard_room'))))
    assert s.dungeon.disguise == 'failed'
    assert s.mode == GameMode.TURN_BASED
    assert s.encounter.combat.active_id == 'player'
    assert report.unperformed_steps == 1
    assert report.stop_reason
    assert any(e['operation'] == 'start_conflict' for e in report.world_events)


@pytest.mark.parametrize('concealed,notice_roll,expected', [(False, 20, 'failed'), (True, 1, 'accepted'), (True, 20, 'failed')])
def test_sword_detection_is_a_guard_check(dice, concealed, notice_roll, expected):
    s = dungeon(dice(20, 20, 20, notice_roll, 20, 19, 1))
    find_equipment(s)
    interact(s, 'wear', 'cleaner_uniform')
    if concealed:
        interact(s, 'conceal', 'longsword')
    reach_guard_door(s)
    s.execute(DoorIntent('open', 'guard_door'))
    assert s.dungeon.disguise == expected
    assert (s.mode == GameMode.TURN_BASED) == (expected == 'failed')


def test_stealth_movement_updates_map_but_not_invisibility_in_lit_room(dice):
    s = dungeon(dice(20, 20))
    interact(s, 'sneak', 'guard_door')
    assert s.state.position == Position(8, 7)
    assert not s.dungeon.prisoner_awake
    s.scene = s.scene.with_passage('guard_door', True)
    s.grid = s.scene.grid
    with pytest.raises(ActionError, match='iluminada'):
        interact(s, 'sneak', 'exit_door')


def test_unarmed_arrival_offers_conversation_and_no_equipment_is_invented(dice):
    s = dungeon(dice(20, 20, 19, 1))
    reach_guard_door(s)
    s.execute(DoorIntent('open', 'guard_door'))
    assert s.encounter.combat is None and s.parley_pending
    assert s.encounter.roller.sides == [20]
    assert s.encounter.player_sheet.weapons == ()
    assert not s.dungeon.inventory


def test_free_prisoner_illusion_companion_and_exit(dice):
    s = dungeon(dice(20, 1))  # Passos não acordam; guarda não reconhece ilusão.
    reach_guard_door(s)
    wait_for_bathroom(s)
    s.execute(DoorIntent('open', 'guard_door'))
    move(s, 'cell_key')
    interact(s, 'take', 'cell_key')  # Retorno já pode ocorrer: cenário avalia a visão.
    move(s, 'gate_2')
    interact(s, 'unlock', 'gate_2')
    assert not s._passage('gate_2').locked
    assert not s._passage('gate_2').is_open
    s.execute(DoorIntent('open', 'gate_2'))
    assert s.dungeon.prisoner_free
    assert s.dungeon.illusion_used
    assert s.dungeon.guard_activity == 'distracted'
    move(s, 'exit_door')
    s.execute(DoorIntent('open', 'exit_door'))
    move(s, 'outside')
    assert s.dungeon.escaped
    assert s.dungeon.companion_escaped
    assert s.scene.area_at(s.prisoner_position).id == 'outside'


def test_scenario_effects_reach_production_narration_and_reset(dice):
    s = dungeon(dice(20, 20))
    reach_storage(s)
    c = Conversation(s)
    prompt = 'Investigo a cama e os panos.'
    c.prepare(prompt)
    plan = sourced_plan(ActionPlan((ScenarioIntent('investigate', 'cell_4'),)), prompt)
    report = c.execute(plan)
    context = c.narration_context(report=report)
    assert context['allow_on']
    assert any(e['operation'] == 'item_found' for e in context['execution']['reactions'])
    assert {o['id'] for o in c.interpretation_context()['visible_objects']} == {'longsword', 'cleaner_uniform'}
    assert s.dungeon.discovered
    s.reset()
    assert not s.dungeon.discovered
    assert not s.dungeon.prisoner_awake
    assert s.encounter.player_sheet.weapons == ()
    assert s.encounter.states['player'].javelins_remaining == 0


def test_parse_new_interactions_and_validate_unknown_items():
    assert parse_intent('{"operation":"listen","target_id":"guard_door"}') == ScenarioIntent('listen', 'guard_door')
    s = dungeon()
    prompt = 'Pego a roupa.'
    plan = sourced_plan(ActionPlan((ScenarioIntent('take', 'cleaner_uniform'),)), prompt)
    with pytest.raises(PlanAuthorizationError):
        validate_player_plan(prompt, plan, Conversation(s).interpretation_context())


def test_named_prisoner_is_a_valid_movement_target_without_fighter_sheet(dice):
    s = dungeon(dice(20))
    interact(s, 'sneak', 'gate_2')
    context = Conversation(s).interpretation_context()
    assert any(c['id'] == 'prisoner' for c in context['visible_creatures'])
    prompt = 'Vou até o prisioneiro.'
    plan = sourced_plan(ActionPlan((MovementIntent((), False, '', 'prisoner'),)), prompt)
    validate_player_plan(prompt, plan, context)
    # A grade trancada impede aproximação através dela; não inventa uma ficha.
    assert 'prisoner' not in s.encounter.sheets


def test_closed_door_stops_partial_movement_and_narration_receives_actual_position(dice):
    s = dungeon(dice(20))
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('sneak', 'guard_room'),)))
    assert report.progress and report.stop_reason
    assert not s._passage('guard_door').is_open
    assert s.state.position == Position(8, 7)
    assert report.events[0]['to'] == [9, 8]
    assert s.mode == GameMode.NARRATED


def test_long_sword_combat_uses_found_weapon_and_actual_armor(dice):
    # Passos, Investigação, iniciativa do Campeão (2) e guarda, ataque, dano+Savage.
    s = dungeon(dice(20, 20, 20, 19, 1, 18, 8, 8))
    find_equipment(s)
    reach_guard_door(s)
    s.execute(DoorIntent('open', 'guard_door'))
    assert s.parley_pending and s.mode == GameMode.NARRATED
    s.execute(RuleIntent('start_combat'))  # Escolha explícita de lutar após a abordagem.
    move(s, 'guard_1')
    before = s.encounter.states['guard_1'].hp
    result = s.execute(RuleIntent('attack', 'guard_1', 'longsword'))
    assert result.event['damage'] == 11
    assert s.encounter.states['guard_1'].hp == before - 11
    assert s.budget.action_used
    assert s.encounter.player_sheet.armor_class == 11


def test_stealth_route_while_guard_is_in_bathroom(dice):
    s = dungeon(dice(20, 20))
    reach_guard_door(s)
    wait_for_bathroom(s)
    s.execute(DoorIntent('open', 'guard_door'))
    interact(s, 'sneak', 'exit_door')
    assert s.state.position != Position(8, 7)
    s.execute(DoorIntent('open', 'exit_door'))
    move(s, 'outside')
    assert s.dungeon.escaped


def test_guard_can_recognize_minor_illusion_without_being_charmed(dice):
    s = dungeon(dice(20, 20))
    interact(s, 'sneak', 'gate_2')
    # Congela uma situação intermediária real: jogador obteve a chave.
    s.dungeon.inventory.add('cell_key')
    interact(s, 'unlock', 'gate_2')
    s.execute(DoorIntent('open', 'gate_2'))
    assert s.dungeon.illusion_used
    assert not s.dungeon.distraction_remaining
    assert s.guard.position == Position(10, 3)
    events = s.drain_world_events()
    spell = next(e for e in events if e['operation'] == 'spell_cast')
    assert spell['spell'] == 'minor_illusion'
    assert 'trapos' in spell['component']
    assert any(e['operation'] == 'illusion_recognized' for e in events)


def test_fallen_guard_does_not_seal_only_doorway(dice):
    from trama.application.intents import MovementSegment
    s = dungeon(dice(20))
    reach_guard_door(s)
    s.scene = s.scene.with_passage('guard_door', True)
    s.grid = s.scene.grid
    s.creatures = (replace(s.guard, position=Position(8, 6)),)
    s.encounter.states['guard_1'] = replace(s.encounter.states['guard_1'], hp=0)
    result = s.execute(MovementIntent((MovementSegment('north', 2),), False, ''))
    assert s.state.position == Position(8, 5)
    assert result.cost_meters == Decimal('4.5')


def test_fallen_guard_cannot_be_destination(dice):
    from trama.application.intents import MovementSegment
    s = dungeon(dice(20))
    reach_guard_door(s)
    s.scene = s.scene.with_passage('guard_door', True)
    s.grid = s.scene.grid
    s.creatures = (replace(s.guard, position=Position(8, 6)),)
    s.encounter.states['guard_1'] = replace(s.encounter.states['guard_1'], hp=0)
    result = s.execute(MovementIntent((MovementSegment('north', 1),), False, ''))
    assert s.state.position == Position(8, 7)
    assert result.stop_code == 'occupied_destination'


def test_unarmed_opportunity_is_available_when_no_inventory(dice):
    from trama.application.travel import TravelExecutor
    s = dungeon(dice(20, 19, 1))
    s.scene = s.scene.with_passage('guard_door', True)
    s.grid = s.scene.grid
    s.state = replace(s.state, position=Position(8, 5))
    s.creatures = (replace(s.guard, position=Position(9, 5)),)
    s.encounter.start(('guard_1',))
    opportunities = TravelExecutor(s)._opportunities('guard_1', Position(9, 5), Position(10, 5))
    assert opportunities and opportunities[0].weapon == 'unarmed'


def test_real_adapters_receive_json_serializable_scenario_and_execute_sdk_plan(dice):
    """Mesmo transporte/esquema/instruções da aplicação; só a rede é substituída."""
    from types import SimpleNamespace
    from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
    from trama.infrastructure.openai_narrator import OpenAINarrator
    from trama.infrastructure.openai_world_director import OpenAIWorldDirector
    s = dungeon(dice(20, 20))
    reach_storage(s)
    s.drain_world_events()
    c = Conversation(s)
    prompt = 'Investigo o interior da cela.'
    speech = c.prepare(prompt)
    outputs = iter([
        {'request_parts': [{'text': prompt, 'kind': 'execute', 'operations': ['investigate'], 'step_indices': [0]}],
         'steps': [{'operation': 'investigate', 'target_id': 'cell_4'}]},
        {'reactions': []},
        {'on': 'Você encontra uma espada sob os panos e um uniforme sob a cama.', 'off': ''},
    ])
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        json.loads(kwargs['input'])  # Não permite sets, posições ou dataclasses no contrato.
        return SimpleNamespace(status='completed', output_text=json.dumps(next(outputs)), output=[], usage=None)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    plan = OpenAIIntentInterpreter(client).interpret(prompt, c.interpretation_context())
    world = OpenAIWorldDirector(client).decide(c.world_context(plan))
    report = c.execute(plan, world)
    context = c.narration_context(speech, report)
    reply = c.finish(OpenAINarrator(client).narrate(context), context)
    assert reply.on
    assert len(requests) == 3
    assert 'scenario' in json.loads(requests[0]['input'])
    assert json.loads(requests[1]['input'])['world']['scenario']['state']['inventory'] == []
    facts = json.loads(requests[2]['input'])['execution']['reactions']
    assert any(e.get('item_id') == 'cleaner_uniform' for e in facts)
    assert s.dungeon.discovered == {'longsword', 'cleaner_uniform'}


def test_all_production_contexts_support_json_before_and_after_changes(dice):
    s = dungeon(dice(20, 20))
    for stage in range(2):
        if stage:
            find_equipment(s)
            interact(s, 'wear', 'cleaner_uniform')
        c = Conversation(s)
        for context in (c.interpretation_context(), c.world_context(), c.narration_context(initial=True)):
            json.dumps(context, ensure_ascii=False)


def test_simulator_map_markers_and_sheet_render_headless(monkeypatch):
    import pygame
    from trama.ui.movement_window import MovementWindow, WINDOW_SIZE, GRID_ORIGIN
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    pygame.display.init()
    pygame.font.init()
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        s = dungeon()
        window = MovementWindow(s, None, 'offline')
        window.draw(screen)
        assert GRID_ORIGIN[1] + window.cell_size * s.grid.height < 500
        assert s.map_view()['compact']
        assert s.map_view()['markers']
        for tab in ('Ficha', 'NPCs'):
            window.active_tab = tab
            window.draw(screen)
        assert s.character_context()['inventory'] == []
    finally:
        pygame.quit()


def test_guard_can_catch_key_theft_without_granting_item(dice):
    s = dungeon(dice(20, 20, 20, 1, 20, 19, 1))
    find_equipment(s)
    interact(s, 'drop', 'longsword')
    interact(s, 'wear', 'cleaner_uniform')
    reach_guard_door(s)
    s.execute(DoorIntent('open', 'guard_door'))
    move(s, 'cell_key')
    result = interact(s, 'take', 'cell_key')
    assert result.stop_reason
    assert 'cell_key' not in s.dungeon.inventory
    assert s.dungeon.guard_alert
    assert s.mode == GameMode.TURN_BASED


def test_dropping_key_does_not_draw_concealed_sword(dice):
    s = dungeon(dice(20, 20))
    find_equipment(s)
    interact(s, 'wear', 'cleaner_uniform')
    interact(s, 'conceal', 'longsword')
    s.dungeon.inventory.add('cell_key')
    interact(s, 'drop', 'cell_key')
    assert s.dungeon.sword_concealed
    assert s.encounter.player_sheet.weapons == ('longsword',)


def test_off_questions_do_not_advance_scenario_routine(dice):
    s = dungeon(dice(20))
    reach_guard_door(s)
    wait_for_bathroom(s)
    before = deepcopy(vars(s.dungeon))
    c = Conversation(s)
    speech = c.prepare('[O que posso ouvir pela porta?]')
    context = c.narration_context(speech)
    assert context['world']['scenario']['state']['guard_activity'] == 'bathroom'
    assert vars(s.dungeon) == before
