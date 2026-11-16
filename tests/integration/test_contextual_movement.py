"""Movimento contextual pelo fluxo real, com estados e dados controlados."""

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
from trama.application.dungeon import DungeonSession
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, RuleIntent, ScenarioIntent
from trama.application.session import GameSession
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.creatures import Creature
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_intent
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector
from trama.movement import MovementState
from trama.spatial import Grid, Position

ROOT = Path(__file__).resolve().parents[2]


def at_storage(roller, *, opened=True):
    s = DungeonSession.from_data(json.loads((ROOT / 'pocs/simulador/dungeon.json').read_text()), roller=roller)
    s.state = replace(s.state, position=Position(7, 9))  # Coluna 8, linha 10, como no log.
    if opened:
        s.scene = s.scene.with_passage('gate_4', True)
        s.grid = s.scene.grid
    return s


def duel(roller, *, target=Position(6, 3), cls=GameSession):
    return cls(Grid(20, 8), MovementState(Position(1, 3)),
               creatures=(Creature('g1', 'Guarda 1', target),), roller=roller)


def investigate():
    return ScenarioIntent('investigate', 'cell_4')


def test_exact_logged_investigation_enters_cell_and_rolls(dice):
    s = at_storage(dice(20))
    c = Conversation(s)
    prompt = 'Eu checo a cela, procurando por algo útil.'
    speech = c.prepare(prompt)
    plan = sourced_plan(ActionPlan((investigate(),)), prompt)
    context = c.world_context(plan)
    assert context['player_plan'][0]['spatial_requirement']['kind'] == 'inside_area'
    assert context['player_plan'][0]['preparation'][0]['proposed_path'][-1] == [6, 10]
    report = c.execute(plan)
    assert report.status == 'completed'
    assert [e['operation'] for e in report.events] == ['move', 'investigate']
    assert report.events[0]['preparation_for']['operation'] == 'investigate'
    assert report.events[0]['traveled_meters'] == 3
    assert s.scene.area_at(s.state.position).id == 'cell_4'
    assert s.dungeon.discovered == {'longsword', 'cleaner_uniform'}
    assert not s.dungeon.inventory
    narration = c.narration_context(speech, report)
    assert narration['perception']['current_place'] == 'Cela 4'
    assert narration['execution']['player_movement']['occurred']


def test_closed_cell_stops_before_investigation_without_opening_or_rolling(dice):
    roller = dice()
    s = at_storage(roller, opened=False)
    report = Conversation(s).execute(ActionPlan((investigate(),)))
    assert report.status == 'blocked'
    assert not s._passage('gate_4').is_open
    assert s.state.position == Position(7, 9)
    assert not s.dungeon.discovered
    assert not roller.sides
    assert not any(e['operation'] == 'investigate' and e.get('status') == 'completed' for e in report.events)


def test_take_known_sword_approaches_and_updates_real_equipment(dice):
    s = at_storage(dice())
    s.dungeon.discovered.add('longsword')
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('take', 'longsword'),)))
    assert report.status == 'completed'
    assert [e['operation'] for e in report.events] == ['move', 'take']
    assert s._near(s.item_positions['longsword'])
    assert 'longsword' in s.dungeon.inventory
    assert s.encounter.player_sheet.weapons == ('longsword',)


def test_unknown_item_and_missing_key_do_not_trigger_approach(dice):
    for intent in (ScenarioIntent('take', 'cleaner_uniform'), ScenarioIntent('unlock', 'gate_2')):
        s = at_storage(dice())
        before = s.state
        report = Conversation(s).execute(ActionPlan((intent,)))
        assert report.status == 'blocked'
        assert not report.progress
        assert s.state == before
        assert s.budget == ActionBudget()
        assert not s.dungeon.inventory


def test_explicit_entry_is_not_duplicated(dice):
    s = at_storage(dice(20))
    report = Conversation(s).execute(ActionPlan((MovementIntent((), False, '', 'cell_4'), investigate())))
    assert report.status == 'completed'
    assert [e['operation'] for e in report.events] == ['move', 'investigate']
    assert 'preparation_for' not in report.events[0]


def test_no_movement_constraint_also_applies_to_investigation(dice):
    s = at_storage(dice())
    before = s.state
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('investigate', 'cell_4', False),)))
    assert report.status == 'blocked'
    assert s.state == before
    assert not s.dungeon.discovered


def test_no_action_prevents_investigation_walk(dice):
    s = at_storage(dice(20, 19, 1))
    s.encounter.start(('guard_1',))
    s.budget = ActionBudget(action_used=True)
    before = s.state
    report = Conversation(s).execute(ActionPlan((investigate(),)))
    assert report.status == 'blocked' and not report.progress
    assert s.state == before
    assert s.budget.action_used
    assert not s.dungeon.discovered


def test_attack_alone_starts_initiative_then_moves_and_attacks(dice, capture_logs):
    # Campeão/guarda: iniciativa; ataque e duas rolagens de dano de Savage Attacker.
    s = duel(dice(20, 19, 1, 15, 2, 3, 1, 1))
    c = Conversation(s)
    prompt = 'Eu vou atacar o Guarda 1.'
    c.prepare(prompt)
    plan = sourced_plan(ActionPlan((RuleIntent('attack', 'g1'),)), prompt)
    preview = c.world_context(plan)
    assert preview['player_plan'][0]['initiative_before_movement']
    assert s.encounter.combat is None  # A consulta não rola iniciativa.
    with capture_logs() as stream:
        report = c.execute(plan)
    assert report.status == 'completed'
    assert [e['operation'] for e in report.events] == ['start_combat', 'move', 'attack']
    assert s.state.spent_meters == 6
    assert s.budget.action_used
    assert not s.budget.free_interaction_used
    assert not s.state.dash_used
    assert s.encounter.states['g1'].hp == 4
    events = [json.loads(line)['event'] for line in stream.getvalue().splitlines()]
    assert events.index('encounter.started') < events.index('movement.resolved')


def test_enemy_winning_initiative_prevents_approach_and_attack(dice):
    roller = dice(1, 2, 20)
    s = duel(roller)
    before = s.state.position
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'g1'),)))
    assert report.status == 'blocked'
    assert s.encounter.combat.active_id == 'g1'
    assert s.state.position == before and s.state.spent_meters == 0
    assert not any(e['operation'] == 'move' for e in report.events)
    assert s.encounter.states['g1'].hp == s.encounter.sheets['g1'].max_hp
    assert roller.sides == [20, 20, 20]


def test_attack_does_not_get_unlimited_narrated_approach(dice):
    roller = dice(20, 19, 1)
    s = duel(roller, target=Position(12, 3))
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'g1'),)))
    assert report.status == 'blocked'
    assert s.state.spent_meters == 9
    assert any(e['operation'] == 'move' and e['cost_meters'] == 9 for e in report.events)
    assert not s.budget.action_used
    assert s.encounter.states['g1'].hp == s.encounter.sheets['g1'].max_hp
    assert not s.state.dash_used
    assert roller.sides == [20, 20, 20]


@pytest.mark.parametrize('change', ['missing_weapon', 'dead_target', 'no_action', 'no_inspiration'])
def test_invalid_attack_does_not_move_or_roll_initiative(dice, change):
    s = duel(dice())
    intent = RuleIntent('attack', 'g1')
    if change == 'missing_weapon':
        intent = RuleIntent('attack', 'g1', 'longsword')
    elif change == 'dead_target':
        s.encounter.states['g1'] = replace(s.encounter.states['g1'], hp=0)
    elif change == 'no_action':
        s.encounter.roller = dice(20, 19, 1)
        s.encounter.start(('g1',))
        s.encounter.roller = dice()
        s.budget = ActionBudget(action_used=True)
    else:
        s.encounter.states['player'] = replace(s.encounter.states['player'], heroic_inspiration=False)
        intent = RuleIntent('attack', 'g1', use_inspiration=True)
    before = s.state
    resources = s.encounter.states.copy()
    report = Conversation(s).execute(ActionPlan((intent,)))
    assert report.status == 'blocked'
    assert s.state == before
    assert s.encounter.states == resources
    assert not s.encounter.roller.sides


def test_attack_without_movement_permission_does_not_start_combat(dice):
    s = duel(dice())
    before = s.state
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'g1', allow_approach=False),)))
    assert report.status == 'blocked'
    assert s.state == before
    assert s.encounter.combat is None


def test_attack_revalidates_moved_target_without_chasing_or_spending_action(dice):
    class MovingTargetSession(GameSession):
        def _execute(self, intent, **options):
            result = super()._execute(intent, **options)
            if isinstance(intent, MovementIntent):
                # Simula mudança do estado do alvo entre o percurso e a validação final.
                self.creatures = (replace(self.creatures[0], position=Position(15, 3)),)
            return result
    s = duel(dice(20, 19, 1), cls=MovingTargetSession)
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'g1'),)))
    assert report.status == 'blocked'
    assert report.progress
    assert s.state.spent_meters == 6
    assert s.encounter.states['g1'].hp == s.encounter.sheets['g1'].max_hp
    assert not s.budget.action_used
    assert 'Aproxime-se' in report.stop_reason


def test_world_interrupts_investigation_approach_before_roll(dice):
    s = at_storage(dice(20, 19, 1))
    reaction = WorldReaction(0, 1, (WorldAction('guard_1', 'start_conflict', 'O guarda reage à fuga.'),))
    report = Conversation(s).execute(ActionPlan((investigate(),)), WorldPlan((reaction,)))
    assert report.status == 'blocked'
    assert s.state.position == Position(6, 9)
    assert not s.dungeon.discovered
    assert s.encounter.combat
    assert not s.budget.action_used
    assert report.failures == () or report.failures[-1].skipped_actions


def test_listen_and_wake_publish_reach_requirements_without_new_engine_cases(dice):
    s = at_storage(dice(20))
    c = Conversation(s)
    context = c.world_context(ActionPlan((ScenarioIntent('listen', 'guard_door'),)))
    assert context['player_plan'][0]['spatial_requirement']['kind'] == 'in_reach'
    report = c.execute(ActionPlan((ScenarioIntent('listen', 'guard_door'),)))
    assert report.status == 'completed'
    assert s._near(s._passage('guard_door').position)
    s = at_storage(dice(20, 1))  # Passos discretos; guarda não ouve o pedido de ajuda.
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('wake', 'prisoner'),)))
    assert report.status == 'completed'
    assert s.dungeon.prisoner_awake


def test_sdk_adapters_receive_logged_request_with_contextual_requirement(dice):
    s = at_storage(dice(20))
    c = Conversation(s)
    speech = c.prepare('Eu checo a cela, procurando por algo útil.')
    replies = iter([
        {'request_parts': [{'text': speech.on, 'kind': 'execute', 'operations': ['investigate'], 'step_indices': [0]}],
         'steps': [{'operation': 'investigate', 'target_id': 'cell_4', 'allow_approach': True}]},
        {'reactions': []},
        {'on': 'Você entra na cela e encontra uma espada sob os panos e um uniforme sob a cama.', 'off': ''},
    ])
    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(status='completed', output=[], output_text=json.dumps(next(replies)))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    plan = OpenAIIntentInterpreter(client).interpret(speech.on, c.interpretation_context())
    world = OpenAIWorldDirector(client).decide(c.world_context(plan))
    report = c.execute(plan, world)
    context = c.narration_context(speech, report)
    reply = c.finish(OpenAINarrator(client).narrate(context), context)
    assert report.status == 'completed'
    assert reply.on and not reply.off
    world_request = json.loads(requests[1]['input'])
    assert world_request['player_plan'][0]['spatial_requirement']['kind'] == 'inside_area'
    narrated = json.loads(requests[2]['input'])
    assert narrated['execution']['player_movement']['occurred']
    assert narrated['perception']['current_place'] == 'Cela 4'
    assert any(e['operation'] == 'item_found' for e in narrated['execution']['reactions'])


@pytest.mark.parametrize('payload,expected', [
    ('{"operation":"investigate","target_id":"cell_4","allow_approach":false}', ScenarioIntent('investigate', 'cell_4', False)),
    ('{"operation":"attack","target_id":"g1","weapon":"unarmed","use_inspiration":false,"allow_approach":false}', RuleIntent('attack', 'g1', 'unarmed', allow_approach=False)),
])
def test_external_contract_preserves_no_movement_constraint(payload, expected):
    assert parse_intent(payload) == expected


def test_contextual_attack_resolves_opportunity_from_other_guard(dice):
    s = GameSession(Grid(20, 8), MovementState(Position(1, 3)), creatures=(
        Creature('g1', 'Guarda 1', Position(2, 3)), Creature('g2', 'Guarda 2', Position(6, 3))),
        roller=dice(20, 19, 1, 1, 15, 2, 3, 1, 1))
    s.encounter.start(('g1', 'g2'))
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'g2'),)))
    assert report.status == 'completed'
    assert s.encounter.budgets['g1'].reaction_used
    assert not s.encounter.budgets['g1'].action_used
    assert s.encounter.states['player'].hp < s.encounter.player_sheet.max_hp
    assert s.encounter.states['g2'].hp == 4
    assert any(e['operation'] == 'opportunity_attack' for e in report.world_events)
    assert s.budget.action_used


def test_attack_visible_through_bars_does_not_open_them(dice):
    s = at_storage(dice(20, 19, 1), opened=False)
    s.creatures = (replace(s.guard, position=Position(3, 9)),)
    report = Conversation(s).execute(ActionPlan((RuleIntent('attack', 'guard_1', 'unarmed'),)))
    assert report.status == 'blocked'
    assert s.encounter.combat
    assert not s._passage('gate_4').is_open
    assert s.state.position == Position(7, 9)
    assert not s.budget.action_used
    assert s.encounter.states['guard_1'].hp == 12


def test_already_unlocked_or_awake_does_not_require_movement(dice):
    s = at_storage(dice())
    before = (s.state, s.scene, s.budget, deepcopy(vars(s.dungeon)))
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('unlock', 'gate_1'),)))
    assert report.status == 'already_satisfied'
    assert (s.state, s.scene, s.budget, vars(s.dungeon)) == before
    s.dungeon.prisoner_awake = True
    before = s.state
    report = Conversation(s).execute(ActionPlan((ScenarioIntent('wake', 'prisoner'),)))
    assert report.status == 'already_satisfied'
    assert s.state == before


@pytest.mark.parametrize('operation', ['listen', 'unlock'])
def test_wrong_target_kind_does_not_crash_world_context_or_move(dice, operation):
    s = at_storage(dice())
    c = Conversation(s)
    # O id existe, mas uma área não é uma porta. Consulta permanece sem efeitos;
    # a execução rejeita o tipo do alvo antes de qualquer aproximação.
    plan = ActionPlan((ScenarioIntent(operation, 'cell_4'),))
    context = c.world_context(plan)
    json.dumps(context)
    before = s.state
    report = c.execute(plan)
    assert report.status == 'blocked'
    assert not report.progress
    assert s.state == before


def test_dungeon_attack_alone_crosses_open_guard_door_and_uses_longsword(dice):
    s = at_storage(dice(20, 20, 19, 1, 15, 8, 8))
    c = Conversation(s)
    # Preparação física pelo motor: encontra a arma, pega e revela o guarda.
    setup = c.execute(ActionPlan((investigate(), ScenarioIntent('take', 'longsword'),
        MovementIntent((), False, '', 'guard_door'))))
    assert setup.status == 'completed'
    opened = c.execute(ActionPlan((DoorIntent('open', 'guard_door'),)))
    assert opened.status == 'blocked'  # Reconhecido como fugitivo: começa o conflito.
    assert s.encounter.combat.active_id == 'player'
    assert s.scene.area_at(s.state.position).id == 'corridor'
    report = c.execute(ActionPlan((RuleIntent('attack', 'guard_1', 'longsword'),)))
    assert report.status == 'completed'
    assert [e['operation'] for e in report.events] == ['move', 'attack']
    assert s.scene.area_at(s.state.position).id == 'guard_room'
    assert s.state.spent_meters == Decimal('4.5')
    assert s.budget.action_used
    assert s.encounter.states['guard_1'].hp == 1
