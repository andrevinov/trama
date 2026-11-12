"""Interações simples com portas; PHB 2024, interação com objetos e Utilize."""

from dataclasses import dataclass, replace


class ActionError(ValueError):
    """A ação não é válida neste estado."""


@dataclass(frozen=True)
class ActionBudget:
    free_interaction_used: bool = False
    action_used: bool = False

    def spend_action(self) -> "ActionBudget":
        if self.action_used:
            raise ActionError("A ação deste turno já foi utilizada.")
        return replace(self, action_used=True)

    def spend_interaction(self) -> "ActionBudget":
        if not self.free_interaction_used:
            return replace(self, free_interaction_used=True)
        return self.spend_action()


@dataclass(frozen=True)
class DoorActionResult:
    is_open: bool
    budget: ActionBudget
    changed: bool


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
    if not in_reach:
        raise ActionError("Aproxime-se da passagem antes de abri-la ou fechá-la.")
    desired = operation == "open"
    if is_open == desired:
        return DoorActionResult(is_open, budget, False)
    if desired and locked:
        raise ActionError("A passagem está trancada.")
    if not desired and occupied:
        raise ActionError("Não é possível fechar a passagem enquanto alguém ocupa seu espaço.")
    return DoorActionResult(desired, budget.spend_interaction(), True)
