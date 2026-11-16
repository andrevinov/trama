"""Movimento terrestre em grade; PHB 2024, pp. 24–25 e verbete Dash.

O cenário representa uma criatura Média/Pequena, sem condições ou efeitos.
As distâncias são armazenadas e calculadas em metros, nunca em pixels.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal
import logging

from trama.spatial import Grid, Position
from trama.distances import CELL_METERS, format_meters, meters

logger = logging.getLogger(__name__)


class MovementError(ValueError):
    """O pedido não pode ser executado neste estado."""

    def __init__(self, message: str, *, code: str = "invalid_movement", position: Position | None = None):
        super().__init__(message)
        self.code = code
        self.position = position


@dataclass(frozen=True)
class MovementState:
    position: Position
    speed_meters: Decimal = Decimal("9")
    spent_meters: Decimal = Decimal("0")
    dash_used: bool = False
    turn: int = 1
    additional_dash_uses: int = 0
    free_meters: Decimal = Decimal("0")
    speed_reduction_meters: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "speed_meters", meters(self.speed_meters))
        object.__setattr__(self, "spent_meters", meters(self.spent_meters))
        object.__setattr__(self, "free_meters", meters(self.free_meters))
        object.__setattr__(self, "speed_reduction_meters", meters(self.speed_reduction_meters))
        if (type(self.dash_used) is not bool
                or type(self.turn) is not int or self.turn < 1
                or type(self.additional_dash_uses) is not int or self.additional_dash_uses < 0
                or (self.additional_dash_uses and not self.dash_used)):
            raise ValueError("Estado de movimento inválido.")
        if self.spent_meters > self.speed_meters * (1 + self.dash_uses):
            raise ValueError("Movimento gasto excede o orçamento do turno.")

    @property
    def remaining_meters(self) -> Decimal:
        return max(Decimal("0"), self.effective_speed_meters * (1 + self.dash_uses) - self.spent_meters) + self.free_meters

    @property
    def effective_speed_meters(self) -> Decimal:
        return max(Decimal("0"), self.speed_meters - self.speed_reduction_meters)

    @property
    def dash_uses(self) -> int:
        return int(self.dash_used) + self.additional_dash_uses

    def next_turn(self) -> "MovementState":
        return replace(self, spent_meters=0, dash_used=False, additional_dash_uses=0,
                       free_meters=Decimal("0"), turn=self.turn + 1)


@dataclass(frozen=True)
class MovementRequest:
    path: tuple[Position, ...]
    dash: bool = False


@dataclass(frozen=True)
class MovementResult:
    state: MovementState
    path: tuple[Position, ...]
    cost_meters: Decimal
    stop_reason: str | None = None
    blocked_position: Position | None = None
    protected_meters: Decimal = Decimal("0")
    stop_code: str | None = field(default=None, kw_only=True)


def step_cost(grid: Grid, origin: Position, destination: Position) -> Decimal:
    """Custo de um passo legal, independente de turno e orçamento."""
    dx, dy = destination.x - origin.x, destination.y - origin.y
    if max(abs(dx), abs(dy)) != 1:
        raise MovementError("Cada passo deve entrar em uma casa adjacente.", code="invalid_step", position=destination)
    if not grid.contains(destination):
        raise MovementError("O percurso sai dos limites do mapa.", code="out_of_bounds", position=destination)
    if destination in grid.blocked:
        raise MovementError("O percurso atravessa uma casa bloqueada.", code="blocked_cell", position=destination)
    if dx and dy and (
        Position(origin.x + dx, origin.y) in grid.blocked
        or Position(origin.x, origin.y + dy) in grid.blocked
    ):
        raise MovementError("Uma diagonal não pode cortar a quina de um obstáculo.", code="corner_blocked", position=destination)
    return CELL_METERS * (2 if destination in grid.difficult else 1)


def apply_movement(
    grid: Grid, state: MovementState, request: MovementRequest,
    *, turn_based: bool = True,
) -> MovementResult:
    """Executa o prefixo legal; turn_based=False ignora apenas o orçamento de turno."""
    if not grid.contains(state.position) or state.position in grid.blocked:
        raise MovementError("Posição inicial inválida.")
    if type(request.dash) is not bool:
        raise MovementError("Dash deve ser verdadeiro ou falso.")
    if not request.path and not request.dash:
        raise MovementError("O pedido não contém movimento.")
    logger.debug("movement.requested", extra={"data": {"state": state, "request": request}})
    available = state.remaining_meters + (state.effective_speed_meters if request.dash else 0)
    previous = state.position
    cost = Decimal("0")
    accepted = [state.position]
    stop_reason = None
    stop_code = None
    blocked_position = None
    for destination in request.path:
        if max(abs(destination.x - previous.x), abs(destination.y - previous.y)) != 1:
            raise MovementError("Cada passo deve entrar em uma casa adjacente.")
        try:
            step = step_cost(grid, previous, destination)
        except MovementError as error:
            stop_reason, blocked_position = str(error), destination
            stop_code = error.code
            break
        if turn_based and cost + step > available:
            stop_reason = (
                f"Movimento insuficiente: a próxima casa custa {format_meters(step)}, "
                f"mas restam {format_meters(available - cost)} neste turno."
            )
            blocked_position = destination
            stop_code = "insufficient_movement"
            break
        cost += step
        previous = destination
        accepted.append(destination)
    dash_activated = turn_based and request.dash and (len(accepted) > 1 or not request.path)
    protected = min(cost, state.free_meters) if turn_based else Decimal("0")
    updated = replace(
        state, position=previous, spent_meters=state.spent_meters + cost - protected if turn_based else state.spent_meters,
        dash_used=state.dash_used or dash_activated,
        additional_dash_uses=state.additional_dash_uses + int(dash_activated and state.dash_used),
        free_meters=state.free_meters - protected,
    )
    result = MovementResult(updated, tuple(accepted), cost, stop_reason, blocked_position, protected, stop_code=stop_code)
    logger.info("movement.resolved", extra={"data": {"before": state, "after": updated,
                "path": result.path, "cost_meters": cost, "protected_meters": protected, "turn_based": turn_based,
                "stop_reason": stop_reason, "stop_code": stop_code, "blocked_position": blocked_position}})
    return result
