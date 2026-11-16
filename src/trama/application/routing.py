"""Coordena o mapa e o custo dos passos sem inserir regras no modelo do mapa."""

from heapq import heappop, heappush
from itertools import count
import logging

from trama.movement import MovementError, step_cost
from trama.scene import Scene
from trama.spatial import Grid, Position

logger = logging.getLogger(__name__)


def path_to(
    scene: Scene, start: Position, target_id: str, grid: Grid | None = None,
    *, approach_blocked: bool = True,
) -> tuple[Position, ...]:
    logger.debug("routing.requested", extra={"data": {"start": start, "target_id": target_id,
                 "architectural_fallback": not approach_blocked}})
    try:
        goals = scene.destination_cells(target_id)
    except ValueError as error:
        raise MovementError(str(error)) from error
    grid = grid or scene.movement_grid
    goals -= grid.blocked
    try:
        result = path_to_cells(grid, start, goals)
    except MovementError:
        if approach_blocked:
            logger.debug("routing.architectural_fallback", extra={"data": {"target_id": target_id,
                         "reason": "no_free_path"}})
            # Planeja até o destino arquitetônico; a execução para na passagem/criatura.
            planned = scene.open_passages_grid
            return path_to(scene, start, target_id, planned, approach_blocked=False)
        logger.debug("routing.unreachable", extra={"data": {"target_id": target_id}})
        raise
    logger.debug("routing.path_found", extra={"data": {"target_id": target_id, "path": result,
                 "architectural_fallback": not approach_blocked}})
    return result


def path_to_cells(grid: Grid, start: Position, goals: frozenset[Position]) -> tuple[Position, ...]:
    """Menor custo até uma casa de destino, usando somente passos legais na grade."""
    if not grid.contains(start) or start in grid.blocked:
        raise MovementError("Posição inicial inválida.")
    requested = goals
    goals = frozenset(p for p in goals if grid.contains(p) and p not in grid.blocked)
    if not goals and len(requested) == 1:
        destination = next(iter(requested))
        code = "destination_blocked" if grid.contains(destination) else "out_of_bounds"
        raise MovementError("Não há caminho até esse destino.", code=code, position=destination)
    logger.debug("routing.cells_requested", extra={"data": {"start": start, "goals": goals}})
    sequence = count()
    queue = [(0, next(sequence), start)]
    costs = {start: 0}
    previous: dict[Position, Position] = {}
    while queue:
        cost, _, position = heappop(queue)
        if cost != costs[position]:
            continue
        if position in goals:
            path = []
            while position != start:
                path.append(position)
                position = previous[position]
            result = tuple(reversed(path))
            logger.debug("routing.cells_path_found", extra={"data": {"start": start, "path": result,
                         "cost_meters": cost}})
            return result
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)):
            destination = Position(position.x + dx, position.y + dy)
            try:
                new_cost = cost + step_cost(grid, position, destination)
            except MovementError:
                continue
            if new_cost < costs.get(destination, float("inf")):
                costs[destination] = new_cost
                previous[destination] = position
                heappush(queue, (new_cost, next(sequence), destination))
    logger.debug("routing.cells_unreachable", extra={"data": {"start": start, "goals": goals}})
    raise MovementError("Não há caminho até esse destino.", code="no_path",
                        position=next(iter(requested)) if len(requested) == 1 else None)
