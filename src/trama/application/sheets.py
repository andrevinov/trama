"""Projeções de fichas para interface e IA, sem depender de Pygame."""

from trama.actions import ActionBudget
from trama.characters import ABILITY_NAMES, SKILLS, WEAPONS, FighterSheet, FighterState


def enemy_summary(sheet: FighterSheet, state: FighterState) -> dict:
    return {"id": sheet.id, "name": sheet.name, "species": "Humano", "class": "Guerreiro",
            "level": sheet.level, "hp": state.hp, "max_hp": sheet.max_hp,
            "armor_class": sheet.armor_class, "at_zero_hp": state.hp == 0,
            "weapon": WEAPONS[sheet.weapons[0]].name if sheet.weapons else "Desarmado"}


def sheet_context(sheet: FighterSheet, state: FighterState, budget: ActionBudget) -> dict:
    return {**enemy_summary(sheet, state), "subclass": "Campeão" if sheet.champion else None,
            "background": "Soldado", "size": "Médio", "speed_meters": float(sheet.speed_meters),
            "human_skill": sheet.human_skill, "skilled_choices": list(sheet.skilled_choices),
            "armor": sheet.armor,
            "proficiency_bonus": sheet.proficiency_bonus,
            "abilities": {name: {"score": getattr(sheet.abilities, name), "modifier": sheet.abilities.modifier(name)}
                          for name in ABILITY_NAMES},
            "saving_throws": {name: sheet.saving_throw_bonus(name) for name in ABILITY_NAMES},
            "skills": {name: {"bonus": sheet.skill_bonus(name), "proficient": name in sheet.skills}
                       for name in SKILLS},
            "features": list(sheet.features), "second_wind_uses": state.second_wind_uses,
            "action_surge_uses": state.action_surge_uses, "heroic_inspiration": state.heroic_inspiration,
            "hit_dice": f"{state.hit_dice_available}/{sheet.level} d10", "javelins": state.javelins_remaining,
            "armor_training": ["Leves", "Médias", "Pesadas", "Escudos"],
            "weapon_proficiencies": ["Simples", "Marciais"],
            "tool_proficiencies": ["Jogos de dados"],  # Escolha de Soldado nesta POC.
            "weapons": [{"name": WEAPONS[w].name,
                         "attack_bonus": sheet.abilities.modifier("strength") + sheet.proficiency_bonus,
                         "damage": f"{WEAPONS[w].dice}d{WEAPONS[w].sides}{sheet.abilities.modifier('strength'):+d}",
                         "damage_type": WEAPONS[w].damage_type} for w in sheet.weapons],
            "masteries": [{"weapon": WEAPONS[w].name, "property": WEAPONS[w].mastery} for w in sheet.masteries],
            "action_available": budget.action_available, "bonus_action_available": not budget.bonus_action_used,
            "reaction_available": not budget.reaction_used, "extra_actions": budget.extra_actions}
