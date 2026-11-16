from conftest import scripted_responses, sourced_output, sourced_plan
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.conversation import Conversation
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, RuleIntent
from trama.application.session import GameSession
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
from trama.movement import MovementError, MovementState
from trama.scene import Scene
from trama.spatial import Position


def prison(dice):
    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                       creatures_from_data(data["creatures"]), roller=dice())


def test_original_prompt_routes_to_numbered_guard_and_attacks(dice):
    session = prison(dice)
    session.execute(MovementIntent((), False, "", "guard_door"))
    session.execute(DoorIntent("open", "guard_door"))
    session.encounter.roller = dice(20, 19, 1)
    session.encounter.start(tuple(c.id for c in session.creatures))
    session.encounter.roller = dice(1)
    client = Mock()
    client.responses.create.side_effect = scripted_responses(SimpleNamespace(status="completed", output=[], output_text=json.dumps({"steps": [
        {"operation": "move", "segments": [], "dash": False, "clarification": "", "target_id": "guard_1"},
        {"operation": "attack", "target_id": "guard_1", "weapon": "greatsword", "use_inspiration": False},
    ]})))
    conversation = Conversation(session)
    speech = conversation.prepare("Eu vou até o guarda 1 e o ataco.")
    plan = OpenAIIntentInterpreter(client).interpret(speech.on, conversation.interpretation_context())
    context = json.loads(client.responses.create.call_args.kwargs["input"])
    assert context["visible_creatures"][0]["number"] == 1
    assert client.responses.create.call_count == 1
    report = conversation.execute(plan)
    assert report.stop_reason is None
    assert session.state.position == Position(14, 5)
    assert session.state.spent_meters == 3 and session.state.remaining_meters == 6
    assert session.budget.action_used and session.encounter.states["guard_1"].hp == 9


def test_hidden_creature_cannot_be_used_as_navigation_target(dice):
    session = prison(dice)
    with pytest.raises(MovementError, match="visível"):
        session.execute(MovementIntent((), False, "", "guard_1"))
    assert session.state == session.initial_state


def test_already_adjacent_is_noop_and_target_position_is_resolved_again(dice):
    session = prison(dice)
    session.execute(MovementIntent((), False, "", "guard_door"))
    session.execute(DoorIntent("open", "guard_door"))
    intent = MovementIntent((), False, "", "guard_1")
    session.execute(intent)
    first_position = session.state.position
    assert session.execute(intent).cost_meters == 0
    session.creatures = tuple(replace(c, position=Position(17, 2)) if c.id == "guard_1" else c for c in session.creatures)
    session.execute(intent)
    assert session.state.position != first_position
    target = session.creatures[0].position
    assert max(abs(session.state.position.x - target.x), abs(session.state.position.y - target.y)) == 1
    assert session.state.position not in {c.position for c in session.creatures}
