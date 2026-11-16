from dataclasses import replace

import pytest

from trama.actions import ActionBudget, ActionError
from trama.characters import FighterSheet, CharacterError, new_fighter, sheet_from_data
from trama.combat import start_combat, weapon_attack
from trama.application.encounter import Encounter


@pytest.fixture
def fighters():
    return FighterSheet("player", "Jogador"), sheet_from_data({}, id="g1", name="Guarda 1")


def test_champion_critical_on_nineteen_doubles_weapon_dice_and_allows_movement(dice, fighters):
    p, g = fighters
    result = weapon_attack(p, new_fighter(p), g, new_fighter(g), "greatsword",
                           dice(19, 1, 2, 3, 4, 2, 2, 2, 2))
    assert result.hit and result.critical and result.critical_movement
    assert result.damage_dice == (1, 2, 3, 4)
    assert result.alternate_damage_dice == (2, 2, 2, 2)
    assert result.damage == 13 and result.target.hp == 0


def test_guard_nineteen_is_not_critical_and_savage_attacker_can_be_spent(dice, fighters):
    p, g = fighters
    result = weapon_attack(g, new_fighter(g), p, new_fighter(p), "flail", dice(19, 3), savage_available=False)
    assert result.hit and not result.critical and not result.critical_movement
    assert result.damage == 6 and not result.alternate_damage_dice


def test_unarmed_critical_has_no_damage_dice_but_triggers_champion_movement(dice, fighters):
    p, g = fighters
    result = weapon_attack(p, new_fighter(p), g, new_fighter(g), "unarmed", dice(19))
    assert result.damage == 4 and result.critical_movement
    assert result.damage_dice == result.alternate_damage_dice == ()
    assert not result.savage_used


def test_graze_on_natural_one_is_only_ability_modifier_without_damage_roll(dice, fighters):
    p, g = fighters
    roller = dice(1)
    result = weapon_attack(p, new_fighter(p), g, new_fighter(g), "greatsword", roller)
    assert not result.hit and result.damage == 3 and result.mastery == "graze"
    assert not result.savage_used and roller.sides == [20]


def test_heavy_weapon_strength_requirement_imposes_disadvantage(dice, fighters):
    p, g = fighters
    weak = replace(p, abilities=replace(p.abilities, strength=12))
    result = weapon_attack(weak, new_fighter(weak), g, new_fighter(g), "greatsword", dice(20, 2))
    assert result.roll.disadvantage and result.roll.natural == 2 and not result.hit
    assert result.damage == 1


def test_invalid_attacks_do_not_roll_or_consume_inspiration(dice, fighters):
    p, g = fighters
    roller = dice()
    for weapon, kwargs in (("longsword", {}), ("flail", {"thrown": True}),
                           ("flail", {"use_inspiration": True})):
        state = replace(new_fighter(p), heroic_inspiration=False)
        with pytest.raises(CharacterError):
            weapon_attack(p, state, g, new_fighter(g), weapon, roller, **kwargs)
    assert roller.sides == []


def test_inspiration_attack_rerolls_then_uses_mandatory_new_result(dice, fighters):
    p, g = fighters
    result = weapon_attack(p, new_fighter(p), g, new_fighter(g), "flail", dice(20, 1), use_inspiration=True)
    assert not result.hit and result.damage == 0
    assert result.original_roll.dice == (20,) and result.roll.dice == (1,)
    assert not result.attacker.heroic_inspiration


def test_initiative_groups_identical_guards_and_tie_policy_is_stable(dice, fighters):
    p, g = fighters
    g2 = replace(g, id="g2", name="Guarda 2")
    encounter = Encounter(p, (g, g2), dice(3, 12, 12))
    event = encounter.start((g.id, g2.id)).event
    assert [e.id for e in encounter.combat.order] == ["player", "g1", "g2"]
    assert event["initiative"][0]["dice"] == [3, 12]
    assert event["initiative"][1]["dice"] == event["initiative"][2]["dice"] == [12]
    assert all(e["total"] == 13 for e in event["initiative"])


def test_surge_allows_second_attack_but_not_second_savage_attacker(dice, fighters):
    p, g = fighters
    encounter = Encounter(p, (g,), dice(15, 16, 10, 15, 1, 2, 15, 1))
    encounter.start((g.id,))
    first = encounter.attack(p.id, g.id, "flail").event
    encounter.use_action_surge(p.id)
    second = encounter.attack(p.id, g.id, "flail").event
    assert first["alternate_damage_dice"] == [2]
    assert second["alternate_damage_dice"] == []
    assert encounter.states[g.id].hp == 3
    with pytest.raises(ActionError):
        encounter.attack(p.id, g.id, "flail")
    assert encounter.states[p.id].action_surge_uses == 0


def test_sap_next_attack_disadvantage_consumed_then_expires_on_source_turn(dice, fighters):
    p, g = fighters
    encounter = Encounter(p, (g,), dice(15, 16, 10, 15, 1, 1, 18, 2))
    encounter.start((g.id,))
    encounter.attack(p.id, g.id, "flail")
    assert encounter.combat.effects[0].kind == "sap"
    encounter.advance()
    event = encounter.attack(g.id, p.id, "flail").event
    assert event["dice"] == [18, 2] and not event["hit"]
    assert encounter.combat.effects == ()
    encounter.advance()
    assert encounter.combat.round == 2


def test_slow_does_not_stack_and_expires_at_source_next_turn(dice, fighters):
    p, g = fighters
    encounter = Encounter(p, (g,), dice(15, 16, 10, 15, 1, 1, 15, 1))
    encounter.start((g.id,))
    encounter.attack(p.id, g.id, "javelin")
    encounter.use_action_surge(p.id)
    encounter.attack(p.id, g.id, "javelin")
    assert encounter.speed(g.id) == 6
    assert len(encounter.combat.effects) == 1
    encounter.advance()
    assert encounter.speed(g.id) == 6
    encounter.advance()
    assert encounter.speed(g.id) == 9
    assert encounter.states[p.id].javelins_remaining == 8  # Corpo a corpo.


def test_turn_resources_recover_on_owners_turn_but_surge_does_not(dice, fighters):
    p, g = fighters
    encounter = Encounter(p, (g,), dice(15, 16, 10, 1))
    encounter.start((g.id,))
    encounter.use_action_surge(p.id)
    encounter.use_second_wind(p.id)
    encounter.budgets[p.id] = encounter.budgets[p.id].spend_reaction()
    with pytest.raises(ActionError):
        encounter.use_second_wind(p.id)
    encounter.advance()
    assert encounter.budgets[p.id].reaction_used
    with pytest.raises(CharacterError, match="Aguarde"):
        encounter.use_second_wind(p.id)
    encounter.advance()
    assert encounter.budgets[p.id] == ActionBudget()
    assert encounter.states[p.id].action_surge_uses == 0
    assert encounter.states[p.id].second_wind_uses == 1


def test_extra_action_excludes_magic_without_blocking_normal_magic_action():
    budget = ActionBudget(extra_actions=1)
    used = budget.spend_action("magic")
    with pytest.raises(ActionError, match="Magia"):
        used.spend_action("magic")
    assert not used.spend_action().action_available
    with pytest.raises(ActionError):
        ActionBudget(extra_actions=-1)
