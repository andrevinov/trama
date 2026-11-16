"""Iniciativa, ordem de turnos e resolução marcial básica, sem geometria ou IA."""

from dataclasses import dataclass, replace
import logging

from trama.characters import FighterSheet, FighterState, WEAPONS, Weapon, CharacterError, reroll_with_inspiration
from trama.dice import D20Roll, Roller, roll_d20, roll_die

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InitiativeEntry:
    id: str
    name: str
    roll: D20Roll


@dataclass(frozen=True)
class Effect:
    kind: str
    source: str
    target: str


@dataclass(frozen=True)
class CombatState:
    order: tuple[InitiativeEntry, ...]
    index: int = 0
    round: int = 1
    effects: tuple[Effect, ...] = ()

    def __post_init__(self) -> None:
        if (not self.order or len({entry.id for entry in self.order}) != len(self.order)
                or type(self.index) is not int or not 0 <= self.index < len(self.order)
                or type(self.round) is not int or self.round < 1):
            raise CharacterError("Ordem de combate inválida.")

    @property
    def active_id(self) -> str:
        return self.order[self.index].id

    def advance(self) -> "CombatState":
        index = (self.index + 1) % len(self.order)
        result = replace(self, index=index, round=self.round + int(index == 0))
        updated = replace(result, effects=tuple(e for e in result.effects if e.source != result.active_id))
        logger.debug("combat.turn_advanced", extra={"data": {"previous_actor": self.active_id,
                     "active_actor": updated.active_id, "round": updated.round,
                     "expired_effects": tuple(e for e in self.effects if e not in updated.effects)}})
        return updated


def start_combat(sheets: tuple[FighterSheet, ...], roller: Roller, *,
                 groups: dict[str, str] | None = None) -> CombatState:
    if len(sheets) < 2 or len({s.id for s in sheets}) != len(sheets):
        raise CharacterError("O combate precisa de participantes distintos.")
    groups = groups or {}
    rolls = {}
    entries = []
    for sheet in sheets:
        group = groups.get(sheet.id, sheet.id)
        if group not in rolls:
            rolls[group] = roll_d20(roller, sheet.abilities.modifier("dexterity"), advantage=sheet.champion)
        entries.append(InitiativeEntry(sheet.id, sheet.name, rolls[group]))
    # Decisão de desempate do cenário: jogador primeiro; demais seguem a ordem do JSON.
    entries.sort(key=lambda entry: -entry.roll.total)
    logger.info("combat.initiative_rolled", extra={"data": {"order": entries, "groups": groups}})
    return CombatState(tuple(entries))


@dataclass(frozen=True)
class AttackResult:
    attacker: FighterState
    target: FighterState
    roll: D20Roll
    hit: bool
    critical: bool
    damage: int
    damage_dice: tuple[int, ...]
    alternate_damage_dice: tuple[int, ...]
    savage_used: bool
    mastery: str | None
    critical_movement: bool
    original_roll: D20Roll | None = None


def weapon_attack(
    sheet: FighterSheet, state: FighterState, target_sheet: FighterSheet, target_state: FighterState,
    weapon_id: str, roller: Roller, *, advantage=False, disadvantage=False,
    savage_available=True, use_inspiration=False, thrown=False,
) -> AttackResult:
    """A aplicação valida turno, ação, alcance, visão e cobertura antes da rolagem."""
    if state.hp == 0 or target_state.hp == 0 or (weapon_id != "unarmed" and weapon_id not in sheet.weapons):
        raise CharacterError("Atacante, alvo ou arma indisponível.")
    unarmed = weapon_id == "unarmed"
    weapon = Weapon("unarmed", "Ataque desarmado", 0, 1, "contundente", "") if unarmed else WEAPONS[weapon_id]
    if weapon_id == "javelin" and state.javelins_remaining == 0:
        raise CharacterError("Não há azagaias disponíveis.")
    if thrown and weapon_id != "javelin":
        raise CharacterError("Esta arma não pode ser arremessada.")
    if use_inspiration and not state.heroic_inspiration:
        raise CharacterError("Inspiração Heroica indisponível.")
    ability = sheet.abilities.modifier("strength")
    disadvantage |= weapon.heavy and sheet.abilities.strength < 13
    roll = roll_d20(roller, ability + sheet.proficiency_bonus, advantage=advantage, disadvantage=disadvantage)
    original_roll = roll if use_inspiration else None
    if use_inspiration:
        state, roll = reroll_with_inspiration(state, roll, roller)
    if thrown:
        state = replace(state, javelins_remaining=state.javelins_remaining - 1)
    critical = roll.natural >= (19 if sheet.champion else 20)
    hit = roll.natural != 1 and (critical or roll.total >= target_sheet.armor_class)
    mastery = weapon.mastery if weapon_id in sheet.masteries else None
    dice, alternate = (), ()
    savage_used = False
    if hit:
        dice = tuple(roll_die(roller, weapon.sides) for _ in range(weapon.dice * (2 if critical else 1)))
        if savage_available and not unarmed:
            alternate = tuple(roll_die(roller, weapon.sides) for _ in dice)
            savage_used = True
        damage = max(0, max(sum(dice), sum(alternate)) + ability + int(unarmed))
    else:
        damage = max(0, ability) if mastery == "graze" else 0
    target_state = replace(target_state, hp=max(0, target_state.hp - damage))
    result = AttackResult(state, target_state, roll, hit, critical, damage, dice, alternate,
                        savage_used, mastery if (hit or mastery == "graze") else None,
                        critical and sheet.champion, original_roll)
    logger.info("combat.attack_resolved", extra={"data": {"actor_id": sheet.id, "target_id": target_sheet.id,
                "weapon": weapon_id, "target_ac": target_sheet.armor_class, "result": result}})
    return result
