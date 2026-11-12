"""Regressão dos exemplos documentados sobre o cenário usado pela janela."""

import json
from pathlib import Path

import pytest

from trama.application.session import GameSession
from trama.application.intents import MovementIntent, MovementSegment
from trama.movement import Grid, MovementError, MovementState, Position


@pytest.mark.parametrize("segments,dash,expected_position,remaining,error", [
    ([("north", 2)], False, (4, 2), 6, None),
    ([("northeast", 2)], False, (6, 2), 6, None),
    ([("east", 2)], False, (6, 4), 4.5, None),
    ([("north", 3), ("east", 4)], False, (7, 1), 0, "insuficiente"),
    ([("north", 3), ("east", 4)], True, (8, 1), 7.5, None),
    ([("northwest", 2)], False, (3, 3), 7.5, "bloqueada"),
    ([("north", 10)], False, (4, 0), 3, "limites"),
])
def test_documented_scenario(segments, dash, expected_position, remaining, error):
    scenario = Path(__file__).resolve().parents[2] / "pocs/movimento/scenario.json"
    data = json.loads(scenario.read_text())
    grid = Grid(data["width"], data["height"],
                frozenset(Position(*p) for p in data["blocked"]),
                frozenset(Position(*p) for p in data["difficult"]))
    session = GameSession(grid, MovementState(Position(*data["start"]), data["speed_meters"]))
    intent = MovementIntent(tuple(MovementSegment(*s) for s in segments), dash, "")
    result = session.execute(intent)
    if error:
        assert error in result.stop_reason
    else:
        assert result.stop_reason is None
    assert session.state.position == Position(*expected_position)
    assert session.state.remaining_meters == remaining
