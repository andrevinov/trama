from decimal import Decimal

import pytest

from trama.application.session import GameSession
from trama.application.intents import MovementIntent, MovementSegment
from trama.movement import (
    Grid, MovementError, MovementRequest, MovementState, Position, apply_movement,
)


def move(grid, state, *coordinates, dash=False):
    return apply_movement(grid, state, MovementRequest(tuple(Position(*p) for p in coordinates), dash))


@pytest.mark.parametrize("dx,dy", [(0, -1), (0, 1), (1, 0), (-1, 0),
                                  (1, 1), (1, -1), (-1, 1), (-1, -1)])
def test_adjacent_square_costs_one_and_half_meters(dx, dy):
    result = move(Grid(10, 10), MovementState(Position(4, 4)), (4 + dx, 4 + dy))
    assert result.cost_meters == 1.5
    assert result.state.remaining_meters == 7.5
    assert result.state.position == Position(4 + dx, 4 + dy)


def test_diagonals_do_not_alternate_cost():
    result = move(Grid(10, 10), MovementState(Position(4, 4)), (5, 5), (6, 6), (7, 7))
    assert result.cost_meters == 4.5


def test_cost_depends_on_entering_difficult_square():
    grid = Grid(10, 10, difficult=frozenset({Position(5, 4), Position(6, 4)}))
    result = move(grid, MovementState(Position(4, 4)), (5, 4), (6, 4), (7, 4))
    assert result.cost_meters == 7.5
    assert result.state.remaining_meters == 1.5


def test_leaving_difficult_terrain_has_normal_cost():
    grid = Grid(10, 10, difficult=frozenset({Position(4, 4)}))
    assert move(grid, MovementState(Position(4, 4)), (5, 5)).cost_meters == 1.5


@pytest.mark.parametrize("coordinates,blocked,match", [
    ([(4, 4)], [], "adjacente"),
    ([(6, 4)], [], "adjacente"),
    ([(5, 4)], [(5, 4)], "bloqueada"),
    ([(5, 5)], [(5, 4)], "quina"),
    ([(5, 5)], [(4, 5)], "quina"),
    ([(5, 5)], [(5, 4), (4, 5)], "quina"),
])
def test_illegal_path(coordinates, blocked, match):
    grid = Grid(10, 10, blocked=frozenset(Position(*p) for p in blocked))
    if match == "adjacente":
        with pytest.raises(MovementError, match=match):
            move(grid, MovementState(Position(4, 4)), *coordinates)
    else:
        result = move(grid, MovementState(Position(4, 4)), *coordinates)
        assert match in result.stop_reason
        assert result.state.position == Position(4, 4)


@pytest.mark.parametrize("start,end", [((0, 0), (-1, 0)), ((0, 0), (0, -1)),
                                      ((9, 9), (10, 9)), ((9, 9), (9, 10))])
def test_all_map_boundaries(start, end):
    result = move(Grid(10, 10), MovementState(Position(*start)), end)
    assert "limites" in result.stop_reason
    assert result.state.position == Position(*start)


def test_exact_budget_and_exhaustion_across_prompts():
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    session.execute(MovementIntent((MovementSegment("north", 3),), False, ""))
    session.execute(MovementIntent((MovementSegment("east", 3),), False, ""))
    assert session.state.remaining_meters == 0
    previous = session.state
    result = session.execute(MovementIntent((MovementSegment("south", 1),), False, ""))
    assert "insuficiente" in result.stop_reason
    assert session.state == previous
    assert session.state.turn == 1


def test_dash_adds_speed_after_movement_and_consumes_action():
    state = MovementState(Position(4, 4), speed_meters=6, spent_meters=4.5)
    result = move(Grid(10, 10), state, (5, 4), (6, 4), dash=True)
    assert result.state.remaining_meters == 4.5
    assert result.state.dash_used
    with pytest.raises(MovementError, match="já foi usada"):
        move(Grid(10, 10), result.state, dash=True)


def test_dash_alone_and_new_turn():
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    result = session.execute(MovementIntent((), True, ""))
    assert result.state.remaining_meters == 18
    session.execute(MovementIntent((MovementSegment("north", 2),), False, ""))
    position = session.state.position
    session.next_turn()
    assert session.state.position == position
    assert session.state.remaining_meters == 9
    assert not session.state.dash_used
    assert session.state.turn == 2
    session.reset()
    assert session.state == session.initial_state
    assert session.last_path == ()


def test_request_preserves_progress_before_obstacle_including_dash():
    grid = Grid(10, 10, blocked=frozenset({Position(7, 4)}))
    session = GameSession(grid, MovementState(Position(4, 4)))
    result = session.execute(MovementIntent((MovementSegment("east", 3),), True, ""))
    assert "bloqueada" in result.stop_reason
    assert session.state.position == Position(6, 4)
    assert session.state.dash_used
    assert session.state.spent_meters == 3
    assert session.last_path == (Position(4, 4), Position(5, 4), Position(6, 4))


def test_clarification_does_not_change_state():
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    with pytest.raises(MovementError, match="Qual distância"):
        session.execute(MovementIntent((), False, "Qual distância?"))
    assert session.state == session.initial_state


def test_insufficient_budget_executes_maximum_affordable_prefix():
    state = MovementState(Position(4, 4), speed_meters=3)
    result = move(Grid(10, 10), state, (5, 4), (6, 4), (7, 4), dash=False)
    assert result.state.position == Position(6, 4)
    assert result.state.remaining_meters == 0
    assert "insuficiente" in result.stop_reason
    assert state.position == Position(4, 4)
    assert state.spent_meters == 0


def test_speed_zero_cannot_move_even_with_dash():
    state = MovementState(Position(4, 4), speed_meters=0)
    result = move(Grid(10, 10), state, (5, 4), dash=True)
    assert result.state == state
    assert "restam 0 m" in result.stop_reason


def test_fractional_square_budget_does_not_round_up():
    state = MovementState(Position(4, 4), speed_meters=2.1)
    result = move(Grid(10, 10), state, (5, 4))
    assert result.state.remaining_meters == Decimal("0.6")
    stopped = move(Grid(10, 10), result.state, (6, 4))
    assert stopped.state == result.state
    assert "restam 0,6 m" in stopped.stop_reason


def test_empty_request_does_not_spend_movement():
    with pytest.raises(MovementError, match="não contém"):
        move(Grid(10, 10), MovementState(Position(4, 4)))


@pytest.mark.parametrize("factory", [
    lambda: Position(True, 1),
    lambda: Grid(0, 10),
    lambda: Grid(10, 10, blocked=frozenset({Position(10, 0)})),
    lambda: Grid(10, 10, frozenset({Position(0, 0)}), frozenset({Position(0, 0)})),
    lambda: MovementState(Position(0, 0), speed_meters=-0.3),
    lambda: MovementState(Position(0, 0), spent_meters=9.3),
    lambda: MovementSegment("up", 1),
    lambda: MovementSegment("north", True),
    lambda: MovementIntent((), "true", ""),
    lambda: MovementIntent((MovementSegment("north", 1),), False, "Pergunta"),
])
def test_invalid_domain_values(factory):
    with pytest.raises(ValueError):
        factory()
