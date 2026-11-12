"""Movimento terrestre em grade; PHB 2024, pp. 24–25 e verbete Dash.

O cenário representa uma criatura Média/Pequena, sem condições ou efeitos.
As distâncias são armazenadas e calculadas em metros, nunca em pixels.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from trama.spatial import Grid, Position
from trama.distances import CELL_METERS, format_meters, meters


class MovementError(ValueError):
    """O pedido não pode ser executado neste estado."""


@dataclass(frozen=True)
class MovementState:
    position: Position
    speed_meters: Decimal = Decimal("9")
    spent_meters: Decimal = Decimal("0")
    dash_used: bool = False
    turn: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "speed_meters", meters(self.speed_meters))
        object.__setattr__(self, "spent_meters", meters(self.spent_meters))
        if (type(self.dash_used) is not bool
                or type(self.turn) is not int or self.turn < 1):
            raise ValueError("Estado de movimento inválido.")
        if self.spent_meters > self.speed_meters * (2 if self.dash_used else 1):
            raise ValueError("Movimento gasto excede o orçamento do turno.")

    @property
    def remaining_meters(self) -> Decimal:
        return self.speed_meters * (2 if self.dash_used else 1) - self.spent_meters

    def next_turn(self) -> "MovementState":
        return replace(self, spent_meters=0, dash_used=False, turn=self.turn + 1)


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


def step_cost(grid: Grid, origin: Position, destination: Position) -> Decimal:
    """Custo de um passo legal, independente de turno e orçamento."""
    dx, dy = destination.x - origin.x, destination.y - origin.y
    if max(abs(dx), abs(dy)) != 1:
        raise MovementError("Cada passo deve entrar em uma casa adjacente.")
    if not grid.contains(destination):
        raise MovementError("O percurso sai dos limites do mapa.")
    if destination in grid.blocked:
        raise MovementError("O percurso atravessa uma casa bloqueada.")
    if dx and dy and (
        Position(origin.x + dx, origin.y) in grid.blocked
        or Position(origin.x, origin.y + dy) in grid.blocked
    ):
        raise MovementError("Uma diagonal não pode cortar a quina de um obstáculo.")
    return CELL_METERS * (2 if destination in grid.difficult else 1)


def apply_movement(
    grid: Grid, state: MovementState, request: MovementRequest,
) -> MovementResult:
    """Executa o prefixo legal e para no primeiro obstáculo ou saldo insuficiente."""
    if not grid.contains(state.position) or state.position in grid.blocked:
        raise MovementError("Posição inicial inválida.")
    if type(request.dash) is not bool:
        raise MovementError("Dash deve ser verdadeiro ou falso.")
    if not request.path and not request.dash:
        raise MovementError("O pedido não contém movimento.")
    if request.dash and state.dash_used:
        raise MovementError("A ação deste turno já foi usada para Dash.")
    available = state.remaining_meters + (state.speed_meters if request.dash else 0)
    previous = state.position
    cost = Decimal("0")
    accepted = [state.position]
    stop_reason = None
    blocked_position = None
    for destination in request.path:
        if max(abs(destination.x - previous.x), abs(destination.y - previous.y)) != 1:
            raise MovementError("Cada passo deve entrar em uma casa adjacente.")
        try:
            step = step_cost(grid, previous, destination)
        except MovementError as error:
            stop_reason, blocked_position = str(error), destination
            break
        if cost + step > available:
            stop_reason = (
                f"Movimento insuficiente: a próxima casa custa {format_meters(step)}, "
                f"mas restam {format_meters(available - cost)} neste turno."
            )
            blocked_position = destination
            break
        cost += step
        previous = destination
        accepted.append(destination)
    dash_activated = request.dash and (len(accepted) > 1 or not request.path)
    updated = replace(
        state, position=previous, spent_meters=state.spent_meters + cost,
        dash_used=state.dash_used or dash_activated,
    )
    return MovementResult(updated, tuple(accepted), cost, stop_reason, blocked_position)
