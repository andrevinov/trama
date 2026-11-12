"""Coordena o mapa e o custo dos passos sem inserir regras no modelo do mapa."""

from heapq import heappop, heappush
from itertools import count

from trama.movement import MovementError, step_cost
from trama.scene import Scene
from trama.spatial import Grid, Position


def path_to(
    scene: Scene, start: Position, target_id: str, grid: Grid | None = None,
    *, approach_blocked: bool = True,
) -> tuple[Position, ...]:
    try:
        goals = scene.destination_cells(target_id)
    except ValueError as error:
        raise MovementError(str(error)) from error
    grid = grid or scene.grid
    goals -= grid.blocked
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
            return tuple(reversed(path))
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
    if approach_blocked:
        # Planeja até o destino arquitetônico; a execução para na passagem/criatura.
        planned = Grid(scene.grid.width, scene.grid.height,
                       scene.grid.blocked - frozenset(p.position for p in scene.passages),
                       scene.grid.difficult)
        return path_to(scene, start, target_id, planned, approach_blocked=False)
    raise MovementError("Não há caminho até esse destino.")
