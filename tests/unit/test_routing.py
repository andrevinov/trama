"""Busca de caminho compartilhada por Jogador e NPCs, sem IA ou cenário."""

from decimal import Decimal

import pytest

from trama.application.routing import path_to_cells
from trama.movement import MovementError, step_cost
from trama.spatial import Grid, Position


def test_route_avoids_occupied_cells_and_wall_corners():
    start, goal = Position(2, 0), Position(1, 1)
    grid = Grid(4, 3, blocked=frozenset({Position(1, 0), Position(3, 1)}))
    path = path_to_cells(grid, start, frozenset({goal}))
    assert path == (Position(2, 1), goal)
    assert sum(step_cost(grid, a, b) for a, b in zip((start, *path), path)) == 3


def test_route_chooses_lower_cost_over_difficult_terrain():
    start, goal = Position(0, 1), Position(6, 1)
    difficult = frozenset(Position(x, 1) for x in range(1, 6))
    grid = Grid(7, 3, difficult=difficult)
    path = path_to_cells(grid, start, frozenset({goal}))
    assert path[-1] == goal
    assert not difficult.intersection(path)
    assert sum(step_cost(grid, a, b) for a, b in zip((start, *path), path)) == Decimal("9")


def test_no_route_through_solid_wall():
    grid = Grid(3, 3, blocked=frozenset(Position(1, y) for y in range(3)))
    with pytest.raises(MovementError, match="Não há caminho"):
        path_to_cells(grid, Position(0, 1), frozenset({Position(2, 1)}))
