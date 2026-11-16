from conftest import scripted_responses, sourced_output, sourced_plan
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.actions import ActionBudget, ActionError
from trama.application.intents import DoorIntent, MovementIntent, MovementSegment
from trama.application.session import GameSession
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import (
    InterpretationError, OpenAIIntentInterpreter, parse_intent,
)
from trama.movement import MovementError, MovementState
from trama.scene import Scene
from trama.spatial import Position


@pytest.fixture
def session():
    path = Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json"
    data = json.loads(path.read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                       creatures_from_data(data["creatures"]))


def to_door(session):
    session.execute(MovementIntent((), True, "", "guard_door"))


def test_opening_reveals_guards_and_closing_hides_them_in_ui_context(session):
    assert len(session.creatures) == 3
    assert session.interpreter_context()["visible_creatures"] == []
    assert all(c.position not in session.visibility.visible for c in session.creatures)
    to_door(session)
    assert session.interpreter_context()["visible_creatures"] == []
    closed_grid = session.grid
    session.execute(DoorIntent("open", "guard_door"))
    assert Position(13, 5) not in session.grid.blocked
    assert len(session.interpreter_context()["visible_creatures"]) == 3
    assert all(c.position in session.visibility.visible for c in session.creatures)
    # Depois do Dash e da interação gratuita, é preciso outro turno para fechar.
    session.next_turn()
    session.execute(DoorIntent("close", "guard_door"))
    assert session.grid == closed_grid
    assert session.interpreter_context()["visible_creatures"] == []


def test_reach_is_checked_without_automatic_movement(session):
    with pytest.raises(ActionError, match="Aproxime-se"):
        session.execute(DoorIntent("open", "guard_door"))
    assert session.state == session.initial_state
    assert session.budget == ActionBudget()
    assert session.scene == session.initial_scene


def test_dash_and_utilize_compete_for_the_same_action(session, enter_turn_mode):
    enter_turn_mode(session)
    to_door(session)
    session.execute(DoorIntent("open", "guard_door"))
    with pytest.raises(ActionError, match="já foi utilizada"):
        session.execute(DoorIntent("close", "guard_door"))
    assert session.scene.passages[1].is_open
    for _ in range(4):
        session.next_turn()
    session.execute(DoorIntent("close", "guard_door"))
    session.execute(DoorIntent("open", "guard_door"))
    result = session.execute(MovementIntent((MovementSegment("west", 1),), True, ""))
    assert "Dash indisponível" in result.stop_reason
    assert not session.state.dash_used
    # A ação gasta não impede o movimento normal.
    session.execute(MovementIntent((MovementSegment("west", 1),), False, ""))
    assert session.state.position == Position(10, 5)


def test_opening_allows_entering_guard_room_and_closing_blocks_it(session):
    to_door(session)
    session.execute(DoorIntent("open", "guard_door"))
    result = session.execute(MovementIntent((), False, "", "guard_room"))
    assert result.state.position == Position(14, 5)
    assert Position(13, 5) in result.path


def test_guard_occupancy_is_enforced_without_combat(session):
    to_door(session)
    session.execute(DoorIntent("open", "guard_door"))
    session.next_turn()
    original_creatures = session.creatures
    result = session.execute(MovementIntent((MovementSegment("east", 3),), False, ""))
    assert "Guarda 2" in result.stop_reason
    assert session.state.position == Position(14, 5)
    assert session.creatures == original_creatures
    session.next_turn()
    assert session.creatures == original_creatures


def test_cannot_close_on_player_in_doorway(session):
    to_door(session)
    session.execute(DoorIntent("open", "guard_door"))
    session.next_turn()
    session.execute(MovementIntent((MovementSegment("east", 1),), False, ""))
    with pytest.raises(ActionError, match="alguém ocupa"):
        session.execute(DoorIntent("close", "guard_door"))
    assert session.scene.passages[1].is_open
    assert session.budget == ActionBudget()


def test_closed_bars_block_movement_but_not_vision(session):
    session.execute(MovementIntent((), False, "", "cell_gate"))
    session.execute(DoorIntent("close", "cell_gate"))
    assert Position(5, 5) in session.grid.blocked
    assert Position(5, 5) not in session.scene.opaque
    assert Position(10, 5) in session.visibility.visible
    result = session.execute(MovementIntent((), False, "", "corridor"))
    assert "Grade da Cela está fechada" in result.stop_reason


def test_reset_restores_map_budget_player_and_visibility(session):
    original_creatures = session.creatures
    to_door(session)
    session.execute(DoorIntent("open", "guard_door"))
    assert len(session.interpreter_context()["visible_creatures"]) == 3
    session.reset()
    assert session.state == session.initial_state
    assert session.scene == session.initial_scene
    assert session.budget == ActionBudget()
    assert session.creatures == original_creatures
    assert session.interpreter_context()["visible_creatures"] == []


def test_locked_door_keeps_map_and_budget_unchanged(session):
    to_door(session)
    door = replace(session.scene.passages[1], locked=True)
    session.scene = replace(session.scene, passages=(session.scene.passages[0], door))
    original = session.scene
    budget = session.budget
    with pytest.raises(ActionError, match="trancada"):
        session.execute(DoorIntent("open", "guard_door"))
    assert session.scene == original
    assert session.budget == budget


def test_open_intent_from_mock_api_is_validated_and_executed(session):
    to_door(session)
    client = Mock()
    payload = {"operation": "open", "target_id": "guard_door", "segments": [],
               "dash": False, "clarification": ""}
    client.responses.create.side_effect = scripted_responses(SimpleNamespace(
        status="completed", output=[], output_text=json.dumps({"steps": [payload]}),
    ))
    intent = OpenAIIntentInterpreter(client).interpret("Abra a porta", session.interpreter_context()).steps[0]
    context = json.loads(client.responses.create.call_args.kwargs["input"])
    assert context["visible_creatures"] == []
    assert context["visible_creatures"] == []
    assert "world" not in context and "player_sheet" not in context
    session.execute(intent)
    assert len(session.interpreter_context()["visible_creatures"]) == 3


@pytest.mark.parametrize("changes", [
    {"target_id": None}, {"target_id": ""}, {"target_id": []},
    {"operation": "attack"}, {"operation": []},
    {"segments": [{"direction": "east", "distance": 1.5, "unit": "meters"}]},
    {"dash": True}, {"dash": 0}, {"clarification": "Qual porta?"},
])
def test_malformed_actions_are_rejected(changes):
    payload = {"operation": "open", "target_id": "guard_door", "segments": [],
               "dash": False, "clarification": ""}
    with pytest.raises(InterpretationError):
        parse_intent(json.dumps({**payload, **changes}))


def test_unknown_passage_cannot_modify_world(session):
    with pytest.raises(ActionError, match="não existe"):
        session.execute(DoorIntent("open", "invented_door"))
    assert session.scene == session.initial_scene
