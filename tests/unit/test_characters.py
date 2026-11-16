from dataclasses import replace
from random import Random

import pytest

from trama.characters import (
    Abilities, CharacterError, FighterSheet, ability_check, action_surge,
    change_mastery_after_long_rest, finish_long_rest, finish_short_rest, inspire_die,
    new_fighter, reroll_with_inspiration, second_wind, sheet_from_data, tactical_mind,
)
from trama.dice import RandomRoller, roll_d20


@pytest.mark.parametrize("level,hp,surge,features", [
    (1, 12, 0, {"Second Wind", "Weapon Mastery"}),
    (2, 20, 1, {"Action Surge", "Tactical Mind"}),
    (3, 28, 1, {"Improved Critical", "Remarkable Athlete"}),
])
def test_human_fighter_level_progression(level, hp, surge, features):
    sheet = sheet_from_data({"level": level}, id="fighter", name="Humano")
    state = new_fighter(sheet)
    assert sheet.max_hp == hp == state.hp
    assert sheet.armor_class == 17
    assert sheet.speed_meters == 9
    assert sheet.proficiency_bonus == 2
    assert state.action_surge_uses == surge
    assert state.second_wind_uses == 2
    assert state.hit_dice_available == level
    assert state.heroic_inspiration
    assert features <= set(sheet.features)
    assert "Extra Attack" not in sheet.features
    assert "Tactical Shift" not in sheet.features
    assert sheet.champion == (level == 3)


def test_species_background_and_class_proficiencies_are_distinct():
    sheet = FighterSheet("player", "Jogador")
    assert len(sheet.skills) == 8
    assert sheet.skill_bonus("athletics") == 5
    assert sheet.skill_bonus("survival") == 3
    assert sheet.skill_bonus("investigation") == 2
    assert sheet.skill_bonus("arcana") == 0
    assert sheet.saving_throw_bonus("strength") == 5
    assert sheet.saving_throw_bonus("constitution") == 4
    assert sheet.saving_throw_bonus("dexterity") == 1
    assert {"Resourceful", "Skillful", "Versatile: Skilled", "Soldier: Savage Attacker"} <= set(sheet.features)
    with pytest.raises(CharacterError, match="distintas"):
        replace(sheet, human_skill="athletics")


def test_defense_requires_armor_and_chain_mail_requires_strength():
    sheet = FighterSheet("p", "Jogador")
    assert replace(sheet, armor="none").armor_class == 11
    weak = replace(sheet, abilities=replace(sheet.abilities, strength=12))
    assert weak.speed_meters == 6
    assert replace(weak, armor="none").speed_meters == 9


def test_second_wind_spends_use_caps_healing_and_requires_consciousness(dice):
    sheet = FighterSheet("p", "Jogador")
    state = replace(new_fighter(sheet), hp=20)
    state, healing = second_wind(sheet, state, dice(10))
    assert (state.hp, healing, state.second_wind_uses) == (28, 8, 1)
    state, healing = second_wind(sheet, state, dice(1))
    assert healing == 0 and state.second_wind_uses == 0
    with pytest.raises(CharacterError):
        second_wind(sheet, state, dice())
    with pytest.raises(CharacterError):
        second_wind(sheet, replace(new_fighter(sheet), hp=0), dice())


def test_short_rest_restores_one_wind_surge_and_spends_chosen_hit_dice(dice):
    sheet = FighterSheet("p", "Jogador")
    state = replace(new_fighter(sheet), hp=5, second_wind_uses=0,
                    action_surge_uses=0, heroic_inspiration=False)
    short = finish_short_rest(sheet, state, dice(4, 6), hit_dice=2)
    assert short.hp == 19  # (4+2)+(6+2)
    assert short.second_wind_uses == short.action_surge_uses == short.hit_dice_available == 1
    assert not short.heroic_inspiration
    assert finish_short_rest(sheet, short, dice()).second_wind_uses == 2
    with pytest.raises(CharacterError):
        finish_short_rest(sheet, short, dice(), hit_dice=2)


def test_long_rest_resourceful_restores_all_hit_dice_without_creating_ammunition():
    sheet = FighterSheet("p", "Jogador")
    used = replace(new_fighter(sheet), hp=1, second_wind_uses=0,
                   action_surge_uses=0, heroic_inspiration=False, hit_dice_available=0, javelins_remaining=3)
    assert finish_long_rest(sheet, used) == replace(new_fighter(sheet), javelins_remaining=3)
    with pytest.raises(CharacterError):
        finish_long_rest(sheet, replace(used, hp=0))


def test_fighter_one_has_no_surge_or_tactical_mind(dice):
    sheet = sheet_from_data({}, id="g", name="Guarda")
    state = new_fighter(sheet)
    with pytest.raises(CharacterError):
        action_surge(sheet, state)
    with pytest.raises(CharacterError):
        tactical_mind(sheet, state, 8, 12, dice())
    assert finish_short_rest(sheet, state, dice()).action_surge_uses == 0


@pytest.mark.parametrize("bonus,expected_uses,total", [(2, 2, 10), (4, 1, 12)])
def test_tactical_mind_only_spends_wind_if_failed_check_becomes_success(dice, bonus, expected_uses, total):
    sheet = FighterSheet("p", "Jogador")
    state, result, rolled = tactical_mind(sheet, new_fighter(sheet), 8, 12, dice(bonus))
    assert (result, rolled, state.second_wind_uses) == (total, bonus, expected_uses)
    with pytest.raises(CharacterError):
        tactical_mind(sheet, state, 12, 12, dice())


def test_champion_athletics_advantage_and_tactical_mind_use_injected_dice(dice):
    sheet = FighterSheet("p", "Jogador")
    roller = dice(2, 5, 3)
    state, check, total = ability_check(sheet, new_fighter(sheet), "athletics", 12,
                                       roller, use_tactical_mind=True)
    assert check.dice == (2, 5) and check.total == 10
    assert total == 13 and state.second_wind_uses == 1
    assert roller.sides == [20, 20, 10]
    _, other_check, _ = ability_check(sheet, state, "perception", 10, dice(8))
    assert other_check.dice == (8,) and not other_check.advantage


def test_inspiration_rerolls_any_die_and_keeps_worse_value(dice):
    state = new_fighter(FighterSheet("p", "Jogador"))
    updated, value = inspire_die(state, 6, 6, dice(1))
    assert value == 1 and not updated.heroic_inspiration
    with pytest.raises(CharacterError):
        inspire_die(updated, 1, 6, dice())


def test_inspiration_reselects_advantage_after_rerolling_one_die(dice):
    state = new_fighter(FighterSheet("p", "Jogador"))
    original = roll_d20(dice(4, 15), 5, advantage=True)
    updated, result = reroll_with_inspiration(state, original, dice(1))
    assert result.dice == (4, 1) and result.natural == 4 and result.total == 9
    assert not updated.heroic_inspiration
    assert original.dice == (4, 15)


def test_advantage_and_disadvantage_cancel_even_after_inspiration(dice):
    state = new_fighter(FighterSheet("p", "Jogador"))
    original = roll_d20(dice(16), advantage=True, disadvantage=True)
    _, result = reroll_with_inspiration(state, original, dice(2))
    assert result.dice == (2,) and result.natural == 2


def test_mastery_can_swap_one_selection_after_completed_long_rest():
    sheet = FighterSheet("p", "Jogador")
    swapped = change_mastery_after_long_rest(sheet, "flail", "longsword")
    assert swapped.masteries == ("greatsword", "longsword", "javelin")
    assert sheet.masteries == ("greatsword", "flail", "javelin")
    with pytest.raises(CharacterError):
        change_mastery_after_long_rest(sheet, "flail", "javelin")


def test_random_dice_can_be_seeded():
    a, b = RandomRoller(Random(123)), RandomRoller(Random(123))
    assert [a.roll(20) for _ in range(10)] == [b.roll(20) for _ in range(10)]


@pytest.mark.parametrize("changes", [
    {"level": 4}, {"subclass": "other"}, {"masteries": ("flail", "flail", "javelin")},
    {"weapons": ("unknown",)},
])
def test_invalid_sheet_choices(changes):
    with pytest.raises(CharacterError):
        replace(FighterSheet("p", "Jogador"), **changes)
