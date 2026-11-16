from conftest import scripted_responses, sourced_output, sourced_plan
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.session import GameSession
from trama.infrastructure.openai_intent_interpreter import (
    InterpretationError, OpenAIIntentInterpreter, parse_intent,
)
from trama.movement import MovementError, MovementState
from trama.spatial import Grid, Position


def payload(distance, unit="meters"):
    return {"operation": "move", "target_id": None, "dash": False, "clarification": "",
            "segments": [{"direction": "north", "distance": distance, "unit": unit}]}


@pytest.mark.parametrize("prompt,distance,unit", [
    ("Ande 3 metros para cima", 3, "meters"),
    ("Ande 10 pés para cima", 10, "feet"),
    ("Ande duas casas para cima", 2, "squares"),
])
def test_input_units_have_identical_metric_result(prompt, distance, unit):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    client = Mock()
    client.responses.create.side_effect = scripted_responses(SimpleNamespace(
        status="completed", output=[], output_text=json.dumps({"steps": [payload(distance, unit)]}),
    ))
    intent = OpenAIIntentInterpreter(client).interpret(prompt, session.interpreter_context()).steps[0]
    result = session.execute(intent)
    assert result.state.position == Position(4, 2)
    assert result.cost_meters == Decimal("3")
    assert session.interpreter_context()["character"]["remaining_meters"] is None
    context = json.loads(client.responses.create.call_args.kwargs["input"])
    assert context["map"]["distance_unit"] == "meters"
    assert context["map"]["cell_size_meters"] == 1.5
    assert context["character"]["speed_meters"] == 9
    assert "feet" not in json.dumps(context["character"])


def test_budget_error_is_expressed_in_meters(enter_turn_mode):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 7), speed_meters=3))
    enter_turn_mode(session)
    intent = parse_intent(json.dumps(payload(4.5)))
    result = session.execute(intent)
    assert "próxima casa custa 1,5 m, mas restam 0 m" in result.stop_reason
    assert session.state.position == Position(4, 5)


@pytest.mark.parametrize("distance,unit", [(True, "meters"), (-1, "meters"), (3, "yards"),
                                          (float("nan"), "meters"), (10001, "meters")])

def test_unsupported_distances_are_rejected_without_rounding(distance, unit):
    with pytest.raises(InterpretationError):
        parse_intent(json.dumps(payload(distance, unit)))
