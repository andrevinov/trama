"""Coordena fichas, recursos e turnos; não conhece mapa, Pygame ou IA."""

from dataclasses import dataclass, replace
from decimal import Decimal
import logging

from trama.actions import ActionBudget
from trama.characters import (
    CharacterError, FighterSheet, action_surge, new_fighter, second_wind,
)
from trama.combat import CombatState, Effect, start_combat, weapon_attack
from trama.dice import RandomRoller, Roller

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuleResult:
    event: dict
    stop_reason: str | None = None

    @property
    def status(self) -> str:
        return "blocked" if self.stop_reason else self.event.get("status", "completed")


class Encounter:
    def __init__(self, player: FighterSheet, enemies: tuple[FighterSheet, ...] = (), roller: Roller | None = None) -> None:
        self.player_id = player.id
        sheets = (player, *enemies)
        if len({s.id for s in sheets}) != len(sheets):
            raise CharacterError("As fichas precisam de identificadores únicos.")
        self.sheets = {s.id: s for s in sheets}
        self.states = {s.id: new_fighter(s) for s in sheets}
        self.budgets = {s.id: ActionBudget() for s in sheets}
        self.roller = roller or RandomRoller()
        self.combat: CombatState | None = None
        self.savage_used: set[str] = set()
        self.last_attacks: dict[str, dict] = {}

    @property
    def player_sheet(self) -> FighterSheet:
        return self.sheets[self.player_id]

    def require_turn(self, actor_id: str) -> None:
        if self.states[actor_id].hp == 0:
            raise CharacterError("Esta criatura está fora de combate (0 PV).")
        if self.combat is not None and self.combat.active_id != actor_id:
            name = self.sheets[self.combat.active_id].name
            raise CharacterError(f"Aguarde seu turno. Agora é a vez de {name}.")

    def start(self, enemy_ids: tuple[str, ...]) -> RuleResult:
        if self.combat is not None:
            raise CharacterError("O combate já foi iniciado.")
        ids = (self.player_id, *enemy_ids)
        if not enemy_ids or any(id not in self.sheets or self.states[id].hp == 0 for id in ids):
            raise CharacterError("Não há participantes válidos para iniciar o combate.")
        # Guardas idênticos rolam como grupo; fichas diferentes recebem grupos próprios.
        groups = {}
        profiles = {}
        for id in enemy_ids:
            s = self.sheets[id]
            key = (s.level, s.abilities, s.subclass, s.armor, s.fighting_style, s.masteries)
            profiles.setdefault(key, id)
            groups[id] = profiles[key]
        self.combat = start_combat(tuple(self.sheets[id] for id in ids), self.roller, groups=groups)
        self.budgets = {id: ActionBudget() for id in self.sheets}
        self.savage_used.clear()
        logger.info("encounter.started", extra={"data": {"player_id": self.player_id,
                    "combat": self.combat, "budgets": self.budgets.copy()}})
        return RuleResult({"operation": "start_combat", "changed": True,
                           "summary": "Combate iniciado; a iniciativa foi rolada pelo código.",
                           "round": 1, "active": self.sheets[self.combat.active_id].name,
                           "initiative": [{"name": e.name, "dice": list(e.roll.dice), "total": e.roll.total}
                                          for e in self.combat.order]})

    def advance(self) -> RuleResult:
        if self.combat is None:
            raise CharacterError("Não há combate em andamento.")
        old = self.combat.active_id
        if not any(self.states[e.id].hp > 0 for e in self.combat.order if e.id != self.player_id):
            self.combat = None
            logger.info("encounter.ended", extra={"data": {"reason": "all_enemies_at_zero_hp"}})
            return RuleResult({"operation": "end_combat", "changed": True,
                               "summary": "Todos os inimigos estão fora de combate."})
        for _ in self.combat.order:
            self.combat = self.combat.advance()
            if self.states[self.combat.active_id].hp > 0:
                break
        active = self.combat.active_id
        self.budgets[active] = ActionBudget()
        self.savage_used.clear()  # Savage Attacker é uma vez por turno, não por rodada.
        logger.info("encounter.turn_started", extra={"data": {"previous_actor": old, "active_actor": active,
                    "round": self.combat.round, "budget": self.budgets[active], "npc_turn": active != self.player_id}})
        return RuleResult({"operation": "end_turn", "changed": True,
                           "summary": f"Turno de {self.sheets[old].name} encerrado. Vez de {self.sheets[active].name}.",
                           "active": self.sheets[active].name, "round": self.combat.round,
                           "npc_turn_completed": old != self.player_id})

    def use_second_wind(self, actor_id: str) -> RuleResult:
        self.require_turn(actor_id)
        budget = self.budgets[actor_id].spend_bonus_action()
        state, healing = second_wind(self.sheets[actor_id], self.states[actor_id], self.roller)
        self.states[actor_id], self.budgets[actor_id] = state, budget
        logger.info("encounter.action_completed", extra={"data": {"actor_id": actor_id,
                    "operation": "second_wind", "state": state, "budget": budget}})
        return RuleResult({"operation": "second_wind", "changed": True, "healing": healing,
                           "hp": state.hp, "summary": f"Retomar o Fôlego recuperou {healing} PV."})

    def use_action_surge(self, actor_id: str) -> RuleResult:
        self.require_turn(actor_id)
        state = action_surge(self.sheets[actor_id], self.states[actor_id])
        self.states[actor_id] = state
        self.budgets[actor_id] = replace(self.budgets[actor_id], extra_actions=self.budgets[actor_id].extra_actions + 1)
        logger.info("encounter.action_completed", extra={"data": {"actor_id": actor_id,
                    "operation": "action_surge", "state": state, "budget": self.budgets[actor_id]}})
        return RuleResult({"operation": "action_surge", "changed": True,
                           "summary": "Surto de Ação concedeu uma ação adicional, exceto Magia."})

    def attack(self, actor_id: str, target_id: str, weapon: str, *, use_inspiration=False,
               opportunity=False) -> RuleResult:
        if not opportunity:
            self.require_turn(actor_id)
        if (self.combat is None or target_id == actor_id
                or not {actor_id, target_id} <= {e.id for e in self.combat.order}):
            raise CharacterError("Inicie um combate com esse alvo antes de atacar.")
        if use_inspiration and not self.states[actor_id].heroic_inspiration:
            raise CharacterError("Inspiração Heroica indisponível.")
        budget = (self.budgets[actor_id].spend_reaction() if opportunity else self.budgets[actor_id].spend_action())
        effects = self.combat.effects
        disadvantage = any(e.kind == "sap" and e.target == actor_id for e in effects)
        result = weapon_attack(self.sheets[actor_id], self.states[actor_id],
                               self.sheets[target_id], self.states[target_id], weapon, self.roller,
                               disadvantage=disadvantage, savage_available=actor_id not in self.savage_used,
                               use_inspiration=use_inspiration)
        self.states[actor_id], self.states[target_id] = result.attacker, result.target
        self.budgets[actor_id] = budget
        if result.savage_used:
            self.savage_used.add(actor_id)
        effects = tuple(e for e in effects if not (e.kind == "sap" and e.target == actor_id))
        if result.hit and (result.mastery == "sap" or result.mastery == "slow" and result.damage > 0):
            new = Effect(result.mastery, actor_id, target_id)
            effects = tuple(e for e in effects if e != new) + (new,)
        self.combat = replace(self.combat, effects=effects)
        logger.info("encounter.action_completed", extra={"data": {"actor_id": actor_id,
                    "operation": "opportunity_attack" if opportunity else "attack", "target_id": target_id, "effects": effects,
                    "budget": budget, "savage_attacker_used": result.savage_used}})
        target = self.sheets[target_id]
        self.last_attacks[actor_id] = {"target_id": target_id, "target_name": target.name,
                                      "weapon": weapon, "hit": result.hit,
                                      "operation": "opportunity_attack" if opportunity else "attack",
                                      "round": self.combat.round}
        return RuleResult({"operation": "opportunity_attack" if opportunity else "attack", "changed": True,
                           "actor_id": actor_id, "target_id": target_id, "target": target.name,
                           "hit": result.hit, "critical": result.critical, "damage": result.damage,
                           "dice": list(result.roll.dice), "natural": result.roll.natural, "total": result.roll.total,
                           "inspiration_used": result.original_roll is not None,
                           "original_attack_dice": list(result.original_roll.dice) if result.original_roll else [],
                           "damage_dice": list(result.damage_dice), "alternate_damage_dice": list(result.alternate_damage_dice),
                           "mastery": result.mastery, "target_hp": result.target.hp,
                           "critical_movement_meters": float(self.speed(actor_id) / 2) if result.critical_movement else 0,
                           "summary": f"Ataque contra {target.name}: {'acerto' if result.hit else 'erro'}, {result.damage} de dano; {result.target.hp} PV restantes."})

    def speed(self, actor_id: str) -> Decimal:
        slow = self.combat and any(e.kind == "slow" and e.target == actor_id for e in self.combat.effects)
        return max(Decimal("0"), self.sheets[actor_id].speed_meters - (Decimal("3") if slow else 0))
