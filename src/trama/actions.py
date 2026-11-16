"""Interações simples com portas; PHB 2024, interação com objetos e Utilize."""

from dataclasses import dataclass, replace
import logging

logger = logging.getLogger(__name__)


class ActionError(ValueError):
    """A ação não é válida neste estado."""


@dataclass(frozen=True)
class ActionBudget:
    free_interaction_used: bool = False
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_used: bool = False
    extra_actions: int = 0

    def __post_init__(self) -> None:
        if (any(type(value) is not bool for value in (self.free_interaction_used, self.action_used,
                self.bonus_action_used, self.reaction_used))
                or type(self.extra_actions) is not int or self.extra_actions < 0):
            raise ActionError("Orçamento de ações inválido.")

    @property
    def action_available(self) -> bool:
        return not self.action_used or self.extra_actions > 0

    def spend_action(self, kind: str = "normal") -> "ActionBudget":
        if self.action_used:
            if self.extra_actions:
                if kind == "magic":
                    raise ActionError("A ação adicional de Surto de Ação não pode ser Magia.")
                updated = replace(self, extra_actions=self.extra_actions - 1)
                logger.debug("action.budget_calculated", extra={"data": {"kind": kind, "source": "action_surge", "before": self, "after": updated}})
                return updated
            raise ActionError("A ação deste turno já foi utilizada.")
        updated = replace(self, action_used=True)
        logger.debug("action.budget_calculated", extra={"data": {"kind": kind, "source": "normal", "before": self, "after": updated}})
        return updated

    def spend_bonus_action(self) -> "ActionBudget":
        if self.bonus_action_used:
            raise ActionError("A ação bônus deste turno já foi utilizada.")
        updated = replace(self, bonus_action_used=True)
        logger.debug("action.budget_calculated", extra={"data": {"kind": "bonus", "before": self, "after": updated}})
        return updated

    def spend_reaction(self) -> "ActionBudget":
        if self.reaction_used:
            raise ActionError("A reação já foi utilizada; ela retorna no início do próximo turno da criatura.")
        updated = replace(self, reaction_used=True)
        logger.debug("action.budget_calculated", extra={"data": {"kind": "reaction", "before": self, "after": updated}})
        return updated

    def spend_interaction(self) -> "ActionBudget":
        if not self.free_interaction_used:
            updated = replace(self, free_interaction_used=True)
            logger.debug("action.budget_calculated", extra={"data": {"kind": "free_interaction", "before": self, "after": updated}})
            return updated
        return self.spend_action()


@dataclass(frozen=True)
class DoorActionResult:
    is_open: bool
    budget: ActionBudget
    changed: bool

    @property
    def status(self) -> str:
        return "completed" if self.changed else "already_satisfied"


def operate_door(
    operation: str, *, is_open: bool, locked: bool, in_reach: bool,
    occupied: bool, budget: ActionBudget,
) -> DoorActionResult:
    """Regra pura: não conhece mapa, movimento, IA, criaturas ou Pygame.

    Alcance, ocupação e o estado do objeto são dados fornecidos pela aplicação.
    Portas já no estado pedido são um no-op, sem gasto de recursos.
    """
    if operation not in {"open", "close"}:
        raise ActionError("Operação de porta desconhecida.")
    desired = operation == "open"
    if is_open == desired:
        logger.debug("door.unchanged", extra={"data": {"operation": operation, "is_open": is_open, "status": "already_satisfied"}})
        return DoorActionResult(is_open, budget, False)
    if not in_reach:
        raise ActionError("Aproxime-se da passagem antes de abri-la ou fechá-la.")
    if desired and locked:
        raise ActionError("A passagem está trancada.")
    if not desired and occupied:
        raise ActionError("Não é possível fechar a passagem enquanto alguém ocupa seu espaço.")
    result = DoorActionResult(desired, budget.spend_interaction(), True)
    logger.info("door.resolved", extra={"data": {"operation": operation, "is_open": desired, "status": result.status,
                "budget_before": budget, "budget_after": result.budget}})
    return result
