"""Humano e Guerreiro/Campeão 1–3; PHB 2024 pp. 91–92, 96, 185, 194, 200–201.

Fichas e recursos não conhecem mapa, interface, combate ou provedor de IA.
As escolhas padrão são dados da POC, não escolhas obrigatórias da classe.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
import logging

from trama.dice import D20Roll, Roller, roll_die, roll_d20

logger = logging.getLogger(__name__)

ABILITY_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SKILLS = {
    "acrobatics": "dexterity", "animal_handling": "wisdom", "arcana": "intelligence",
    "athletics": "strength", "deception": "charisma", "history": "intelligence",
    "insight": "wisdom", "intimidation": "charisma", "investigation": "intelligence",
    "medicine": "wisdom", "nature": "intelligence", "perception": "wisdom",
    "performance": "charisma", "persuasion": "charisma", "religion": "intelligence",
    "sleight_of_hand": "dexterity", "stealth": "dexterity", "survival": "wisdom",
}
FIGHTER_SKILLS = {"acrobatics", "animal_handling", "athletics", "history", "insight",
                  "intimidation", "persuasion", "perception", "survival"}


class CharacterError(ValueError):
    pass


@dataclass(frozen=True)
class Abilities:
    strength: int = 17
    dexterity: int = 12
    constitution: int = 15
    intelligence: int = 10
    wisdom: int = 13
    charisma: int = 8

    def __post_init__(self) -> None:
        if any(type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= 20
               for name in ABILITY_NAMES):
            raise CharacterError("Atributos devem ser inteiros entre 1 e 20.")

    def modifier(self, ability: str) -> int:
        if ability not in ABILITY_NAMES:
            raise CharacterError("Atributo desconhecido.")
        return (getattr(self, ability) - 10) // 2


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    dice: int
    sides: int
    damage_type: str
    mastery: str
    heavy: bool = False
    normal_range_meters: Decimal = Decimal("1.5")
    long_range_meters: Decimal = Decimal("1.5")


WEAPONS = {
    "greatsword": Weapon("greatsword", "Espada grande", 2, 6, "cortante", "graze", True),
    "flail": Weapon("flail", "Mangual", 1, 8, "contundente", "sap"),
    "javelin": Weapon("javelin", "Azagaia", 1, 6, "perfurante", "slow", False, Decimal("9"), Decimal("36")),
    "longsword": Weapon("longsword", "Espada longa", 1, 8, "cortante", "sap"),
}


@dataclass(frozen=True)
class FighterSheet:
    id: str
    name: str
    level: int = 3
    abilities: Abilities = Abilities()
    subclass: str | None = "champion"
    fighting_style: str = "defense"
    armor: str = "chain_mail"
    fighter_skills: tuple[str, ...] = ("perception", "insight")
    human_skill: str = "survival"
    skilled_choices: tuple[str, ...] = ("acrobatics", "history", "investigation")
    masteries: tuple[str, ...] = ("greatsword", "flail", "javelin")
    weapons: tuple[str, ...] = ("greatsword", "flail", "javelin")
    background: str = "soldier"
    human_origin_feat: str = "skilled"
    gaming_set: str = "dice"

    def __post_init__(self) -> None:
        if (not self.id or not self.name or type(self.level) is not int or not 1 <= self.level <= 3
                or self.subclass != ("champion" if self.level == 3 else None)
                or self.fighting_style != "defense" or self.armor not in {"chain_mail", "none"}
                or self.background != "soldier" or self.human_origin_feat != "skilled"
                or self.gaming_set != "dice"):
            raise CharacterError("Esta POC suporta Guerreiro Humano 1–3, Campeão no nível 3 e Defesa.")
        if (len(self.fighter_skills) != 2 or not set(self.fighter_skills) <= FIGHTER_SKILLS
                or self.human_skill not in SKILLS or len(self.skilled_choices) != 3
                or not set(self.skilled_choices) <= SKILLS.keys()
                or len(self.skills) != 8):
            raise CharacterError("As oito perícias escolhidas devem ser válidas e distintas.")
        if len(self.masteries) != 3 or len(set(self.masteries)) != 3 or not set(self.masteries) <= WEAPONS.keys():
            raise CharacterError("Escolha três maestrias distintas disponíveis.")
        if len(set(self.weapons)) != len(self.weapons) or not set(self.weapons) <= WEAPONS.keys():
            raise CharacterError("Equipamento de armas inválido.")

    @property
    def skills(self) -> frozenset[str]:
        return frozenset(("athletics", "intimidation", *self.fighter_skills,
                          self.human_skill, *self.skilled_choices))

    @property
    def proficiency_bonus(self) -> int:
        return 2

    def skill_bonus(self, skill: str) -> int:
        if skill not in SKILLS:
            raise CharacterError("Perícia desconhecida.")
        return self.abilities.modifier(SKILLS[skill]) + (self.proficiency_bonus if skill in self.skills else 0)

    def saving_throw_bonus(self, ability: str) -> int:
        return self.abilities.modifier(ability) + (self.proficiency_bonus if ability in {"strength", "constitution"} else 0)

    @property
    def max_hp(self) -> int:
        return 10 + self.abilities.modifier("constitution") + (self.level - 1) * (6 + self.abilities.modifier("constitution"))

    @property
    def armor_class(self) -> int:
        return 17 if self.armor == "chain_mail" else 10 + self.abilities.modifier("dexterity")

    @property
    def speed_meters(self) -> Decimal:
        return Decimal("6") if self.armor == "chain_mail" and self.abilities.strength < 13 else Decimal("9")

    @property
    def champion(self) -> bool:
        return self.level == 3 and self.subclass == "champion"

    @property
    def features(self) -> tuple[str, ...]:
        result = ("Resourceful", "Skillful", "Versatile: Skilled", "Soldier: Savage Attacker",
                  "Fighting Style: Defense", "Second Wind", "Weapon Mastery")
        if self.level >= 2:
            result += ("Action Surge", "Tactical Mind")
        if self.champion:
            result += ("Improved Critical", "Remarkable Athlete")
        return result


@dataclass(frozen=True)
class FighterState:
    hp: int
    second_wind_uses: int = 2
    action_surge_uses: int = 1
    heroic_inspiration: bool = True
    hit_dice_available: int = 3
    javelins_remaining: int = 8

    def __post_init__(self) -> None:
        if (any(type(n) is not int or n < 0 for n in (self.hp, self.second_wind_uses,
                self.action_surge_uses, self.hit_dice_available, self.javelins_remaining))
                or self.second_wind_uses > 2 or self.action_surge_uses > 1
                or type(self.heroic_inspiration) is not bool):
            raise CharacterError("Recursos de personagem inválidos.")


def new_fighter(sheet: FighterSheet) -> FighterState:
    # A POC começa após um descanso longo concluído.
    return FighterState(sheet.max_hp, action_surge_uses=int(sheet.level >= 2), hit_dice_available=sheet.level,
                        javelins_remaining=8 if "javelin" in sheet.weapons else 0)


def second_wind(sheet: FighterSheet, state: FighterState, roller: Roller) -> tuple[FighterState, int]:
    if state.hp == 0 or not state.second_wind_uses:
        raise CharacterError("Retomar o Fôlego indisponível.")
    healing = roll_die(roller, 10) + sheet.level
    updated = replace(state, hp=min(sheet.max_hp, state.hp + healing), second_wind_uses=state.second_wind_uses - 1)
    logger.info("character.power_used", extra={"data": {"actor_id": sheet.id, "power": "second_wind",
                "before": state, "after": updated, "healing": updated.hp - state.hp, "rolled_healing": healing}})
    return updated, updated.hp - state.hp


def action_surge(sheet: FighterSheet, state: FighterState) -> FighterState:
    if sheet.level < 2 or not state.action_surge_uses or state.hp == 0:
        raise CharacterError("Surto de Ação indisponível.")
    updated = replace(state, action_surge_uses=state.action_surge_uses - 1)
    logger.info("character.power_used", extra={"data": {"actor_id": sheet.id, "power": "action_surge",
                "before": state, "after": updated}})
    return updated


def reroll_with_inspiration(state: FighterState, roll: D20Roll, roller: Roller,
                            index: int | None = None) -> tuple[FighterState, D20Roll]:
    if not state.heroic_inspiration:
        raise CharacterError("Inspiração Heroica indisponível.")
    index = roll.selected if index is None else index
    if not 0 <= index < len(roll.dice):
        raise CharacterError("Dado a rerrolar inválido.")
    dice = list(roll.dice)
    dice[index] = roll_die(roller, 20)
    selected = dice.index(max(dice) if roll.advantage else min(dice)) if len(dice) == 2 else 0
    updated = replace(roll, dice=tuple(dice), selected=selected)
    logger.info("character.inspiration_used", extra={"data": {"original_roll": roll, "new_roll": updated,
                "rerolled_index": index}})
    return replace(state, heroic_inspiration=False), updated


def inspire_die(state: FighterState, value: int, sides: int, roller: Roller) -> tuple[FighterState, int]:
    """Qualquer dado pode ser rerrolado; o novo valor é obrigatório, mesmo pior."""
    if not state.heroic_inspiration or type(value) is not int or not 1 <= value <= sides:
        raise CharacterError("Inspiração ou dado inválido.")
    result = roll_die(roller, sides)
    logger.info("character.inspiration_used", extra={"data": {"sides": sides, "original_value": value, "new_value": result}})
    return replace(state, heroic_inspiration=False), result


def tactical_mind(sheet: FighterSheet, state: FighterState, total: int, dc: int,
                  roller: Roller) -> tuple[FighterState, int, int]:
    if sheet.level < 2 or not state.second_wind_uses or total >= dc or state.hp == 0:
        raise CharacterError("Mente Tática requer um teste de atributo falho e um uso de Retomar o Fôlego.")
    bonus = roll_die(roller, 10)
    updated = replace(state, second_wind_uses=state.second_wind_uses - int(total + bonus >= dc))
    logger.info("character.power_used", extra={"data": {"actor_id": sheet.id, "power": "tactical_mind",
                "before": state, "after": updated, "original_total": total, "bonus": bonus, "dc": dc,
                "total": total + bonus, "passed": total + bonus >= dc}})
    return updated, total + bonus, bonus


def ability_check(sheet: FighterSheet, state: FighterState, skill: str, dc: int, roller: Roller,
                  *, use_tactical_mind=False, use_inspiration=False, advantage=False, disadvantage=False) -> tuple[FighterState, D20Roll, int]:
    if state.hp == 0 or type(dc) is not int or dc < 1:
        raise CharacterError("Teste de atributo inválido.")
    roll = roll_d20(roller, sheet.skill_bonus(skill),
                    advantage=advantage or (sheet.champion and skill == "athletics"), disadvantage=disadvantage)
    if use_inspiration:
        state, roll = reroll_with_inspiration(state, roll, roller)
    total = roll.total
    if use_tactical_mind and total < dc:
        state, total, _ = tactical_mind(sheet, state, total, dc, roller)
    logger.info("character.ability_check_resolved", extra={"data": {"actor_id": sheet.id, "skill": skill,
                "roll": roll, "total": total, "dc": dc, "passed": total >= dc}})
    return state, roll, total


def finish_short_rest(sheet: FighterSheet, state: FighterState, roller: Roller,
                      hit_dice: int = 0) -> FighterState:
    """Benefícios após 1 h concluída sem interrupção; a aplicação valida o tempo."""
    if state.hp == 0 or type(hit_dice) is not int or not 0 <= hit_dice <= state.hit_dice_available:
        raise CharacterError("Descanso curto ou Dados de Vida indisponíveis.")
    healing = sum(max(1, roll_die(roller, 10) + sheet.abilities.modifier("constitution")) for _ in range(hit_dice))
    updated = replace(state, hp=min(sheet.max_hp, state.hp + healing),
                   hit_dice_available=state.hit_dice_available - hit_dice,
                   second_wind_uses=min(2, state.second_wind_uses + 1), action_surge_uses=int(sheet.level >= 2))
    logger.info("character.rest_finished", extra={"data": {"actor_id": sheet.id, "rest": "short",
                "hit_dice_spent": hit_dice, "before": state, "after": updated}})
    return updated


def finish_long_rest(sheet: FighterSheet, state: FighterState) -> FighterState:
    """Benefícios após descanso longo válido: inclui Resourceful e todos os Dados de Vida."""
    if state.hp == 0:
        raise CharacterError("É preciso pelo menos 1 PV para iniciar um descanso.")
    updated = replace(new_fighter(sheet), javelins_remaining=state.javelins_remaining)
    logger.info("character.rest_finished", extra={"data": {"actor_id": sheet.id, "rest": "long",
                "before": state, "after": updated}})
    return updated


def change_mastery_after_long_rest(sheet: FighterSheet, old: str, new: str) -> FighterSheet:
    if old not in sheet.masteries or new not in WEAPONS or new in sheet.masteries:
        raise CharacterError("Troca de maestria inválida.")
    updated = replace(sheet, masteries=tuple(new if weapon == old else weapon for weapon in sheet.masteries))
    logger.info("character.mastery_changed", extra={"data": {"actor_id": sheet.id, "old": old, "new": new}})
    return updated


def sheet_from_data(data: dict, *, id: str, name: str, default_level: int = 1) -> FighterSheet:
    level = data.get("level", default_level)
    return FighterSheet(id, name, level, Abilities(**data.get("abilities", {})),
                        data.get("subclass", "champion" if level == 3 else None),
                        data.get("fighting_style", "defense"), data.get("armor", "chain_mail"),
                        tuple(data.get("fighter_skills", ("perception", "insight"))),
                        data.get("human_skill", "survival"),
                        tuple(data.get("skilled_choices", ("acrobatics", "history", "investigation"))),
                        tuple(data.get("masteries", ("greatsword", "flail", "javelin"))),
                        tuple(data.get("weapons", ("greatsword", "flail", "javelin"))),
                        data.get("background", "soldier"), data.get("human_origin_feat", "skilled"),
                        data.get("gaming_set", "dice"))
