"""Sentidos gerais por NPC, geometria, passiva, Search e sono; sem rede."""

from copy import deepcopy
from decimal import Decimal

import pytest

from trama.actions import ActionError
from trama.application.conversation import Conversation
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, NarrativeIntent, RuleIntent, ScenarioIntent
from trama.application.scenarios import build_session
from trama.application.world import WorldAction
from trama.application.world_resolution import WorldExecutor
from trama.spatial import Position


def rooms(*, start=(8, 2), guard=(11, 2), senses=None, dark=(), opened=False, observers=()):
    return {'width': 24, 'height': 5, 'start': list(start), 'player': {'armor': 'none'}, 'areas': [
        {'id': 'west', 'name': 'Sala oeste', 'x': 1, 'y': 1, 'width': 9, 'height': 3},
        {'id': 'east', 'name': 'Sala leste', 'x': 11, 'y': 1, 'width': 12, 'height': 3}],
        'passages': [{'id': 'door', 'name': 'Porta', 'kind': 'door', 'position': [10, 2],
                      'is_open': opened, 'locked': False, 'connects': ['west', 'east']}],
        'creatures': [{'id': 'watcher', 'name': 'Vigia', 'position': list(guard), 'senses': senses or {}}],
        'observers': list(observers), 'dark': [list(p) for p in dark]}


def walk(direction, n):
    return MovementIntent((MovementSegment(direction, n),), False, '')


def notices(s, target='player'):
    return s.perception.awareness.get('watcher', {}).get(target)


def test_visual_range_stops_at_first_detection_without_random_checks(dice):
    s = build_session({'width': 20, 'height': 5, 'start': [2, 2], 'creatures': [
        {'id': 'watcher', 'name': 'Vigia', 'position': [10, 2], 'senses': {
            'sight_range_meters': 3, 'hearing_range_meters': 0, 'response': 'challenge'}}]}, roller=dice())
    result = s.execute(walk('east', 7))
    assert s.state.position == Position(8, 2) and result.cost_meters == 9
    assert result.stop_code == 'parley_pending' and s.parley_pending and s.encounter.combat is None
    assert s.creatures[0].position == Position(10, 2)
    assert not s.encounter.roller.sides


def test_closed_door_blocks_vision_but_not_audible_conversation(dice):
    s = build_session(rooms(), roller=dice())
    s.execute(NarrativeIntent('Quem está aí?', 'speak'))
    assert notices(s)['level'] == 'heard' and notices(s)['position'] is None
    assert not s.npc_sees_player('watcher') and not s.parley_pending
    assert not s.encounter.roller.sides


@pytest.mark.parametrize('volume,heard', [('quiet', False), ('normal', False), ('loud', True)])
def test_hearing_depends_on_noise_and_route_distance(dice, volume, heard):
    s = build_session(rooms(start=(2, 2), guard=(20, 2)), roller=dice())
    s.execute(NarrativeIntent('Alguém me escuta?', 'speak', volume=volume))
    assert bool(notices(s)) == heard
    assert not s.encounter.roller.sides


def test_solid_wall_with_no_passage_does_not_transmit_sound(dice):
    data = rooms()
    data['passages'] = []
    s = build_session(data, roller=dice())
    s.execute(NarrativeIntent('Grito!', 'speak', volume='loud'))
    assert notices(s) is None and not s.npc_sees_player('watcher')


@pytest.mark.parametrize('bonus,detected', [(3, False), (12, True)])
def test_hidden_total_is_compared_with_each_observer_passive_without_rolls(dice, bonus, detected):
    s = build_session(rooms(senses={'perception_bonus': bonus}), roller=dice(20))
    s.execute(RuleIntent('hide'))
    assert s.perception.hidden_total == 21
    s.execute(walk('north', 1))
    # Pela porta e caminho, esta posição pode sair do alcance quiet; a fala é a mesma emissão controlada.
    s.emit_noise('player', Position(8, 2), 'quiet', 'Passo discreto junto à porta.')
    assert bool(notices(s)) == detected
    if detected:
        assert notices(s)['level'] == 'located' and not notices(s)['visible']
    assert s.encounter.roller.sides == [20]


def test_repeated_steps_do_not_reroll_or_duplicate_same_hearing(dice):
    s = build_session(rooms(start=(7, 2)), roller=dice())
    s.execute(walk('east', 1))
    s.execute(walk('west', 1))
    s.execute(walk('east', 1))
    events = [e for e in s.drain_world_events() if e['operation'] == 'perception_detected']
    assert len(events) == 1 and events[0]['level'] == 'heard'
    assert not s.encounter.roller.sides


@pytest.mark.parametrize('roll,found', [(1, False), (20, True)])
def test_search_uses_stored_stealth_dc_and_does_not_see_through_door(dice, roll, found):
    s = build_session(rooms(), roller=dice(20, roll))
    s.execute(RuleIntent('hide'))
    event = WorldExecutor(s).execute(WorldAction('watcher', 'search', 'O vigia procura o fugitivo.', 'player'))
    assert event['dc'] == 21 and event['total'] == roll + 3 and event['found'] == found
    assert not s.npc_sees_player('watcher')
    if found:
        assert notices(s)['level'] == 'located' and s.perception.hidden_total is None
    else:
        assert s.perception.hidden_total == 21 and notices(s) is None
        with pytest.raises(ActionError, match='mesma busca'):
            WorldExecutor(s).execute(WorldAction('watcher', 'search', 'Repete a mesma busca.', 'player'))
    assert s.encounter.roller.sides == [20, 20]


def test_search_out_of_hearing_and_sight_has_no_free_roll(dice):
    s = build_session(rooms(start=(2, 2), guard=(20, 2)), roller=dice(20))
    s.execute(RuleIntent('hide'))
    with pytest.raises(ActionError, match='não alcança'):
        s.perception.search('watcher')
    assert s.encounter.roller.sides == [20]


def test_obvious_visual_contact_needs_no_check_and_hide_is_not_magic(dice):
    s = build_session(rooms(opened=True), roller=dice())
    s.execute(NarrativeIntent('Olho a sala.', 'look'))
    assert notices(s)['level'] == 'seen'
    with pytest.raises(ActionError, match='cobertura'):
        s.execute(RuleIntent('hide'))
    assert not s.encounter.roller.sides


@pytest.mark.parametrize('darkvision,seen', [(0, False), (6, True)])
def test_normal_sight_and_darkvision_obey_lighting_and_range(dice, darkvision, seen):
    s = build_session(rooms(opened=True, dark=((8, 2),), senses={'can_hear': False, 'darkvision_meters': darkvision}), roller=dice())
    s.execute(NarrativeIntent('Observo em silêncio.', 'look'))
    assert bool(notices(s)) == seen
    assert not s.encounter.roller.sides


@pytest.mark.parametrize('volume,awakened', [('quiet', False), ('normal', True), ('loud', True)])
def test_sleeping_noncombat_npc_wakes_by_its_own_senses_not_a_class_sheet(dice, volume, awakened):
    s = build_session({'width': 20, 'height': 5, 'start': [2, 2], 'observers': [
        {'id': 'sleeper', 'name': 'Dorminhoco', 'position': [6, 2],
         'senses': {'sleeping': True, 'wake_range_meters': 9, 'perception_bonus': 2}}]}, roller=dice())
    s.execute(NarrativeIntent('Falo no recinto.', 'speak', volume=volume))
    assert ('sleeper' in s.perception.awakened) == awakened
    assert 'sleeper' not in s.encounter.sheets and not s.encounter.roller.sides


def test_sleeping_npc_cannot_use_search_and_reset_restores_sleep(dice):
    s = build_session({'width': 20, 'height': 5, 'start': [2, 2], 'observers': [
        {'id': 'sleeper', 'name': 'Dorminhoco', 'position': [6, 2], 'senses': {'sleeping': True}}]}, roller=dice())
    with pytest.raises(ActionError, match='dormindo'):
        s.perception.search('sleeper')
    s.execute(NarrativeIntent('Acorde!', 'speak', volume='loud'))
    assert s.perception.awakened
    s.reset()
    assert s.perception.sleeping(s.observers[0]) and not s.perception.awareness


def test_failed_hide_does_not_create_a_successful_stealth_state(dice):
    s = build_session(rooms(), roller=dice(1))
    event = s.execute(RuleIntent('hide')).event
    assert not event['passed'] and event['total'] == 2 and s.perception.hidden_total is None
    s.execute(walk('north', 1))
    assert notices(s)['level'] == 'heard'


def test_search_spends_npc_action_and_can_be_repeated_in_a_new_turn(dice):
    s = build_session(rooms(), roller=dice(20, 20, 19, 1, 1, 20))
    s.execute(RuleIntent('hide'))
    WorldExecutor(s).execute(WorldAction('watcher', 'start_conflict', 'O vigia inicia o confronto e procura o fugitivo.'))
    s.execute(RuleIntent('end_turn'))
    assert s.encounter.combat.active_id == 'watcher'
    first = s.perception.search('watcher')
    assert not first['found'] and s.encounter.budgets['watcher'].action_used
    with pytest.raises(ActionError):
        s.perception.search('watcher')
    s.next_turn()
    s.execute(RuleIntent('end_turn'))
    second = s.perception.search('watcher')
    assert second['found'] and s.encounter.budgets['watcher'].action_used
    assert not s.encounter.roller.values


def test_a_real_new_noise_permits_new_deliberate_search_but_not_free_retries(dice):
    s = build_session(rooms(), roller=dice(20, 1, 20))
    s.execute(RuleIntent('hide'))
    assert not s.perception.search('watcher')['found']
    with pytest.raises(ActionError):
        s.perception.search('watcher')
    s.emit_noise('player', s.state.position, 'quiet', 'Um novo ruído discreto altera a situação.')
    assert s.perception.search('watcher')['found']
    assert not s.encounter.roller.values


def test_legacy_world_check_cannot_override_actual_stealth_dc(dice):
    from trama.application.world import PerceptionCheck, WorldReaction
    s = build_session(rooms(), roller=dice(20, 1))
    s.execute(RuleIntent('hide'))
    events, _ = WorldExecutor(s).reaction(WorldReaction(0, 0, (
        WorldAction('watcher', 'say', 'Encontrei você!'),), check=PerceptionCheck('watcher', 1, 'Busca deliberada.')))
    assert events[0]['dc'] == 21 and not events[0]['passed']
    assert not any(e['operation'] == 'say' for e in events)
    assert s.perception.hidden_total == 21


def test_chain_mail_imposes_disadvantage_on_hide_from_the_actual_sheet(dice):
    data = rooms()
    data['player']['armor'] = 'chain_mail'
    s = build_session(data, roller=dice(20, 1))
    event = s.execute(RuleIntent('hide')).event
    assert event['disadvantage'] and event['dice'] == [20, 1] and not event['passed']
    assert s.perception.hidden_total is None


def test_published_sensory_knowledge_cannot_mutate_the_engine(dice):
    s = build_session(rooms(), roller=dice())
    s.execute(NarrativeIntent('Falo em voz normal.', 'speak'))
    context = s.interpreter_context()
    context['world']['perception']['observers'][0]['awareness']['player']['level'] = 'seen'
    assert notices(s)['level'] == 'heard'


def test_looking_without_change_does_not_unlock_another_failed_npc_search(dice):
    s = build_session(rooms(), roller=dice(20, 1))
    s.execute(RuleIntent('hide'))
    assert not s.perception.search('watcher')['found']
    s.execute(NarrativeIntent('Olho em volta, sem sair do lugar.', 'look'))
    with pytest.raises(ActionError, match='mesma busca'):
        s.perception.search('watcher')
    assert s.encounter.roller.sides == [20, 20]


def test_starting_inside_visual_range_does_not_grant_a_free_first_step(dice):
    s = build_session({'width': 12, 'height': 5, 'start': [2, 2], 'creatures': [
        {'id': 'watcher', 'name': 'Vigia', 'position': [4, 2],
         'senses': {'sight_range_meters': 3, 'can_hear': False, 'response': 'challenge'}}]}, roller=dice())
    result = s.execute(walk('east', 1))
    assert s.state.position == Position(2, 2) and result.cost_meters == 0
    assert result.stop_code == 'parley_pending' and s.parley.player_position == Position(2, 2)
    assert not s.encounter.roller.sides


def test_noncombat_observer_is_a_real_navigation_target_and_has_auditable_errors(dice):
    from trama.application.world import WorldError
    s = build_session({'width': 12, 'height': 5, 'start': [2, 2], 'observers': [
        {'id': 'sleeper', 'name': 'Dorminhoco', 'position': [6, 2],
         'senses': {'sleeping': True, 'can_hear': False}}]}, roller=dice())
    s.execute(MovementIntent((), False, '', 'sleeper'))
    assert max(abs(s.state.position.x - 6), abs(s.state.position.y - 2)) == 1
    executor = WorldExecutor(s)
    with pytest.raises(WorldError, match='dormindo'):
        executor.execute(WorldAction('sleeper', 'say', 'Uma fala impossível durante o sono.'))
    assert executor.failure.actor_name == 'Dorminhoco'
    assert executor.failure.origin == executor.failure.position_after == Position(6, 2)
    assert 'sleeper' not in s.encounter.sheets and not s.encounter.roller.sides
