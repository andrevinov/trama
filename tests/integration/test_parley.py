"""Regra geral de abordagem, independente da dungeon, e regressão da distância."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from conftest import sourced_plan
from trama.actions import ActionError
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow, FlowStage
from trama.application.game_runner import GameRunner, RunStatus
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, NarrativeIntent, RuleIntent
from trama.application.parley import InfluenceRequest
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction, WorldError
from trama.application.world_resolution import WorldExecutor
from trama.spatial import Position
from trama.social import DispositionAssessment, PersonaEffect


def judgment(willingness='hesitant', skill='persuasion', attitude='indifferent', game=None):
    interests = game.social.profiles[next(iter(game.social.profiles))].persona.interests if game else ()
    effects = tuple(PersonaEffect(i.id, {'willing': 1, 'unwilling': -1}.get(willingness, 0),
                                 'Concessão limitada à escuta.') for i in interests)
    if not effects:
        effects = (PersonaEffect('safety', {'willing': 1, 'unwilling': -1}.get(willingness, 0), 'Escuta.'),)
    return InfluenceRequest(skill=skill, attitude=attitude, assessment=DispositionAssessment(
        'listen', 'player', 'Ouvir mantendo custódia.', 0, 0, 'Pedido neutro.', effects, (),
        'Fique onde está. Vou ouvir.', 'Não. Volte à cela.', ('Manter posição e custódia.',)))


PROFILE = dict(alignment='neutral', persona=dict(name='Vigia',role='Guarda',background='Evita riscos.',
    interests=[dict(id='safety',description='Evitar riscos.',weight=4)]))


def session(dice, *rolls):
    return build_session({'width': 24, 'height': 3, 'start': [1, 1],
        'creatures': [{'id': 'watcher', 'name': 'Vigia', 'position': [20, 1], 'hostile': True, 'social': PROFILE}]},
        roller=dice(*rolls))


def approach(game):
    return WorldExecutor(game).execute(WorldAction('watcher', 'parley', 'Pare! Identifique-se.'))


def reply_runner(game, request):
    interpreter, director, narrator = Mock(), Mock(), Mock()
    interpreter.interpret.side_effect = lambda prompt, context: sourced_plan(
        ActionPlan((NarrativeIntent(prompt, 'speak', volume='loud'),)), prompt)
    director.decide.side_effect = [WorldPlan((WorldReaction(0, None, (
        WorldAction('watcher', 'influence', 'O vigia considera ouvir a explicação antes de lutar.', influence=request),)),)), WorldPlan()]
    narrator.narrate.return_value = Speech(on='O vigia responde ao que você disse.')
    return GameRunner(GameFlow(game, interpreter, narrator, director))


def test_general_approach_interrupts_plan_at_detection_without_initiative(dice):
    game = session(dice)
    plan = ActionPlan((MovementIntent((MovementSegment('east', 10),), False, ''), NarrativeIntent('Olho em volta.')))
    reaction = WorldReaction(0, 2, (WorldAction('watcher', 'parley', 'Pare! Identifique-se.'),
        WorldAction('watcher', 'move', 'O vigia tenta aproximar-se.', destination=Position(4, 1))))
    report = Conversation(game).execute(plan, WorldPlan((reaction,)))
    assert report.stop_reason and report.unperformed_steps == 1
    assert game.state.position == Position(3, 1)
    assert game.creatures[0].position == Position(20, 1)
    assert game.parley.context()['player_position'] == [4, 2]
    assert game.parley_pending and game.encounter.combat is None
    assert not game.encounter.roller.sides
    assert not any(e['operation'] == 'move' for e in report.world_events)


def test_npc_movement_already_seeing_player_does_not_approach_for_free(dice):
    game = session(dice)
    result = WorldExecutor(game).execute(WorldAction('watcher', 'move', 'O vigia vem interpelar.', destination=Position(2, 1)))
    assert result['stop_code'] == 'parley_pending' and result['cost_meters'] == 0
    assert game.creatures[0].position == Position(20, 1) and game.parley_pending
    assert game.encounter.combat is None


@pytest.mark.parametrize('skill', ['persuasion', 'deception', 'intimidation', 'performance'])
def test_success_uses_actual_skill_and_preserves_positions_and_resources(dice, skill):
    game = session(dice, 20)
    approach(game)
    before = (game.state, game.creatures, deepcopy(game.encounter.states), deepcopy(game.encounter.budgets))
    result = reply_runner(game, judgment(skill=skill)).submit('Não precisa lutar. Ouça minha explicação.')
    assert result.status == RunStatus.COMPLETED and not result.report.stop_reason
    event, = [e for e in result.report.world_events if e['operation'] == 'influence']
    assert event['accepted'] and event['passed'] and event['skill'] == skill and event['dc'] == 15
    assert event['total'] == 20 + game.encounter.player_sheet.skill_bonus(skill)
    assert game.parley_pending and game.parley.status == 'listening'
    assert game.encounter.combat is None and game.encounter.roller.sides == [20]
    assert (game.state, game.creatures, game.encounter.states, game.encounter.budgets) == before
    game.observe_npc('watcher')
    assert game.parley_pending


def test_failed_influence_preserves_detection_and_waits_without_initiative(dice):
    game = session(dice, 1)
    approach(game)
    runner = reply_runner(game, judgment())
    result = runner.submit('Não lute. Posso explicar por que estou aqui.')
    assert result.status == RunStatus.COMPLETED
    assert [r.stage for r in result.requests] == [FlowStage.INTERPRET, FlowStage.WORLD, FlowStage.NARRATE]
    assert game.state.position == Position(1, 1) and game.creatures[0].position == Position(20, 1)
    assert game.encounter.combat is None and game.encounter.states['player'].hp == 28
    assert not any(e['operation'] == 'attack' for e in result.report.world_events)
    assert not game.encounter.roller.values


@pytest.mark.parametrize('willingness,combat', [('willing', False), ('unwilling', False)])
def test_clear_acceptance_or_refusal_needs_no_social_roll(dice, willingness, combat):
    game = session(dice, *([20, 19, 1] if combat else []))
    approach(game)
    result = reply_runner(game, judgment(willingness)).submit('Baixo as mãos e peço que me escute.')
    assert result.status == RunStatus.COMPLETED
    assert bool(game.encounter.combat) == combat
    assert len(game.encounter.roller.sides) == (3 if combat else 0)
    event = next(e for e in result.report.world_events if e['operation'] == 'influence')
    assert 'dice' not in event


@pytest.mark.parametrize('attitude,rolls,passed', [('friendly', (1, 20), True), ('hostile', (20, 1), False)])
def test_influence_attitude_applies_advantage_or_disadvantage(dice, attitude, rolls, passed):
    game = session(dice, *rolls)
    approach(game)
    game.execute(NarrativeIntent('Me ouça.', 'speak', volume='loud'))
    event = WorldExecutor(game).execute(WorldAction('watcher', 'influence', 'O vigia avalia a explicação.',
        influence=judgment(attitude=attitude)))
    assert event['passed'] == passed and len(event['dice']) == 2
    assert event['advantage'] == (attitude == 'friendly')
    assert event['disadvantage'] == (attitude == 'hostile')


def test_attack_choice_starts_initiative_before_contextual_approach(dice):
    game = session(dice, 1, 2, 20)
    approach(game)
    interpreter, director, narrator = Mock(), Mock(), Mock()
    interpreter.interpret.side_effect = lambda prompt, context: sourced_plan(ActionPlan((RuleIntent('attack', 'watcher', 'unarmed'),)), prompt)
    director.decide.side_effect = [WorldPlan(), WorldPlan()]
    narrator.narrate.return_value = Speech(on='O confronto começa à distância.')
    result = GameRunner(GameFlow(game, interpreter, narrator, director)).submit('Ataco o vigia com um soco.')
    assert result.status == RunStatus.COMPLETED and game.encounter.combat.active_id == 'player'
    assert game.state.position == Position(1, 1) and game.creatures[0].position == Position(20, 1)
    assert not game.parley_pending and game.parley.status == 'combat'
    assert not any(e['operation'] == 'attack' and e.get('changed') for e in (*result.report.events, *result.report.world_events))


def test_pending_dialogue_blocks_physical_actions_and_off_does_not_resolve_it(dice):
    game = session(dice)
    approach(game)
    with pytest.raises(ActionError, match='Responda'):
        game.execute(MovementIntent((MovementSegment('east', 2),), False, ''))
    narrator = Mock()
    narrator.narrate.return_value = Speech(off='Você pode responder ao vigia.')
    runner = GameRunner(GameFlow(game, narrator=narrator))
    before = (game.state, game.creatures, game.parley)
    result = runner.submit('[Ainda posso conversar?]')
    assert result.status == RunStatus.COMPLETED and len(result.requests) == 1
    assert (game.state, game.creatures, game.parley) == before and not game.encounter.roller.sides
    game.reset()
    assert game.parley is None and not game.peaceful_npcs


def test_model_cannot_resolve_influence_before_player_speaks(dice):
    game = session(dice)
    approach(game)
    world = WorldPlan((WorldReaction(0, 0, (WorldAction('watcher', 'influence', 'O vigia avalia.',
        influence=judgment()),)),))
    report = Conversation(game).execute(ActionPlan((NarrativeIntent('Podemos conversar?', 'speak'),)), world)
    assert report.stop_reason and 'fala' in report.stop_reason
    assert game.parley_pending and not game.encounter.roller.sides


def test_opening_door_stops_generic_npc_before_following_approach(dice):
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/scenarios/legacy_cell_and_guards.json').read_text())
    data['start'] = [10, 5]
    data['creatures'] = data['creatures'][:1]
    game = build_session(data, roller=dice())
    executor = WorldExecutor(game)
    executor.execute(WorldAction('guard_1', 'move', 'O guarda vai à porta.', destination=Position(14, 4)))
    assert not game.parley_pending
    events, reason = executor.reaction(WorldReaction(0, 0, (
        WorldAction('guard_1', 'open', 'O guarda abre a porta.', 'guard_door'),
        WorldAction('guard_1', 'move', 'O guarda tenta chegar perto.', destination=Position(11, 5)),
    )))
    assert reason and game.parley_pending and game.encounter.combat is None
    assert game.creatures[0].position == Position(14, 4)
    assert game.parley.npc_position == Position(14, 4)
    assert any(e['operation'] == 'parley' for e in events)
    assert not any(e['operation'] == 'move' for e in events)
    assert not game.encounter.roller.sides


def test_influence_dc_uses_target_intelligence_when_higher_than_fifteen(dice):
    game = build_session({'width': 24, 'height': 3, 'start': [1, 1], 'creatures': [
        {'id': 'watcher', 'name': 'Vigia', 'position': [20, 1], 'sheet': {'abilities': {'intelligence': 18}}}]},
        roller=dice(20))
    approach(game)
    game.execute(NarrativeIntent('Me ouça.', 'speak', volume='loud'))
    event = WorldExecutor(game).execute(WorldAction('watcher', 'influence', 'O vigia pondera.',
        influence=judgment()))
    assert event['dc'] == 18 and event['accepted']


def test_refusal_alone_does_not_start_combat_with_nonhostile_interlocutor(dice):
    game = build_session({'width': 24, 'height': 3, 'start': [1, 1], 'creatures': [
        {'id': 'watcher', 'name': 'Vigia', 'position': [20, 1], 'hostile': False, 'social': PROFILE}]}, roller=dice())
    approach(game)
    game.execute(NarrativeIntent('Me ouça.', 'speak', volume='loud'))
    event = WorldExecutor(game).execute(WorldAction('watcher', 'influence', 'O vigia recusa e decide lutar.',
        influence=judgment('unwilling')))
    assert not event['accepted'] and game.encounter.combat is None
    assert game.parley.status == 'pending' and game.creatures[0].position == Position(20, 1)


def test_listening_guard_keeps_custody_and_does_not_allow_door_manipulation(dice):
    import json
    from pathlib import Path
    from trama.application.intents import DoorIntent

    data = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/scenarios/legacy_cell_and_guards.json').read_text())
    data['start'] = [12, 5]
    data['creatures'] = data['creatures'][:1]
    data['creatures'][0]['social'] = PROFILE
    next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
    game = build_session(data, roller=dice())
    executor = WorldExecutor(game)
    executor.execute(WorldAction('guard_1', 'parley', 'Pare! Identifique-se.'))
    game.execute(NarrativeIntent('Me ouça.', 'speak'))
    executor.execute(WorldAction('guard_1', 'influence', 'O guarda aceita ouvir.', influence=judgment('willing', game=game)))
    with pytest.raises(ActionError, match='Responda'):
        game.execute(DoorIntent('close', 'guard_door'))
    assert game.encounter.combat is None and game.parley.status == 'listening'
    assert not game.encounter.roller.sides
