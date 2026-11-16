from conftest import scripted_responses, sourced_output, sourced_plan
"""Pedidos com destinos nomeados, usando o cenário real e respostas fixas da API."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.session import GameSession
from trama.application.intents import MovementIntent
from trama.infrastructure.openai_intent_interpreter import (
    InterpretationError, OpenAIIntentInterpreter, parse_intent,
)
from trama.movement import MovementError, MovementState, Position
from trama.scene import Scene


@pytest.fixture
def session():
    scenario = Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json"
    data = json.loads(scenario.read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"]), data["speed_meters"]), scene)


def named_response(target, dash=False):
    return SimpleNamespace(status="completed", output=[], output_text=json.dumps({"steps": [{
        "segments": [], "dash": dash, "clarification": "", "target_id": target, "operation": "move",
    }]}))


@pytest.mark.parametrize("prompt,target,dash,end,cost", [
    ("Caminhar até a grade", "cell_gate", False, (4, 5), 1.5),
    ("Correr até a porta da Sala dos Guardas", "guard_door", True, (12, 5), 13.5),
    ("Entrar no Corredor", "corridor", False, (6, 5), 4.5),
])
def test_named_prompt_uses_map_context_and_python_route(session, prompt, target, dash, end, cost):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(named_response(target, dash))
    interpreter = OpenAIIntentInterpreter(client)
    intent = interpreter.interpret(prompt, session.interpreter_context()).steps[0]
    result = session.execute(intent)
    assert result.state.position == Position(*end)
    assert result.cost_meters == cost
    assert not result.state.dash_used
    context = json.loads(client.responses.create.call_args.kwargs["input"])
    assert context["character"]["current_area"] == "cell"
    assert {a["name"] for a in context["map"]["scene"]["areas"]} == {
        "Cela", "Corredor", "Sala dos Guardas",
    }
    gate, door = context["map"]["scene"]["passages"]
    assert gate["is_open"] is True
    assert door["is_open"] is False
    assert door["locked"] is False
    assert gate["connects"] == ["cell", "corridor"]
    assert door["connects"] == ["corridor", "guard_room"]


def test_gate_then_running_to_door_without_turn_budget(session):
    session.execute(MovementIntent((), False, "", "cell_gate"))
    result = session.execute(MovementIntent((), True, "", "guard_door"))
    assert result.cost_meters == 12
    assert result.state.spent_meters == 0
    assert session.interpreter_context()["character"]["remaining_meters"] is None


def test_walking_to_door_does_not_stop_at_speed_in_narrated_mode(session):
    result = session.execute(MovementIntent((), False, "", "guard_door"))
    assert result.stop_reason is None
    assert session.state.position == Position(12, 5)
    assert session.state.spent_meters == 0


def test_closed_door_never_opens_implicitly(session):
    result = session.execute(MovementIntent((), True, "", "guard_room"))
    assert "Porta da Sala dos Guardas está fechada" in result.stop_reason
    assert session.state.position == Position(12, 5)
    assert not session.scene.passages[1].is_open
    assert not session.scene.passages[1].locked


def test_scene_dimensions_and_initial_state(session):
    corridor = next(a for a in session.scene.areas if a.id == "corridor")
    assert corridor.width == 7
    assert "10,5 m" in corridor.description
    assert session.scene.area_at(session.state.position).id == "cell"
    assert session.grid.width == 19
    assert session.grid.height == 11


@pytest.mark.parametrize("changes", [
    {"target_id": ""}, {"target_id": 1},
    {"target_id": "cell_gate", "clarification": "Qual grade?"},
    {"target_id": "cell_gate", "segments": [{"direction": "east", "distance": 1.5, "unit": "meters"}]},
])
def test_invalid_named_intents_are_rejected(changes):
    payload = {"segments": [], "dash": False, "clarification": "", "target_id": None, "operation": "move"}
    with pytest.raises(InterpretationError):
        parse_intent(json.dumps({**payload, **changes}))
