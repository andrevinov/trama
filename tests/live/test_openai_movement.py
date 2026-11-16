"""Chamada paga opcional; execução e critérios em pocs/movimento/README.md."""

import os
from pathlib import Path

import pytest

from trama.application.scenarios import build_session, load_session
from trama.application.intents import DoorIntent, MovementIntent
from trama.infrastructure.openai_services import open_services
from trama.spatial import Position

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("RUN_OPENAI_LIVE_TESTS") != "1",
                       reason="Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas."),
]


def test_real_prompt_moves_two_squares_north():
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    session = build_session({'width': 10, 'height': 10, 'start': [4, 4]})
    with open_services() as services:
        interpreter = services.interpreter
        intent = interpreter.interpret("Ande exatamente duas casas para o norte, sem correr.",
                                       session.interpreter_context()).steps[0]
    result = session.execute(intent)
    assert result.state.position == Position(4, 2)
    assert result.cost_meters == 3
    assert session.interpreter_context()["character"]["remaining_meters"] is None
    assert not result.state.dash_used


@pytest.mark.parametrize("prompt,target,dash,end,cost", [
    ("Caminhar até a grade", "cell_gate", False, (4, 5), 1.5),
    ("Correr até a porta da Sala dos Guardas", "guard_door", True, (12, 5), 13.5),
])
def test_real_named_destination(prompt, target, dash, end, cost):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    scenario = Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json"
    session = load_session(scenario)
    with open_services() as services:
        interpreter = services.interpreter
        intent = interpreter.interpret(prompt, session.interpreter_context()).steps[0]
    assert intent.target_id == target
    assert intent.dash == dash
    result = session.execute(intent)
    assert result.state.position == Position(*end)
    assert result.cost_meters == cost


@pytest.mark.parametrize("operation", ["open", "close"])
def test_real_door_operation(operation):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    scenario = Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json"
    session = load_session(scenario)
    session.execute(MovementIntent((), True, "", "guard_door"))
    if operation == "close":
        session.execute(DoorIntent("open", "guard_door"))
        session.next_turn()
    prompt = "Abra a porta da Sala dos Guardas" if operation == "open" else "Feche a porta da Sala dos Guardas"
    with open_services() as services:
        interpreter = services.interpreter
        intent = interpreter.interpret(prompt, session.interpreter_context()).steps[0]
    assert intent == DoorIntent(operation, "guard_door")
    session.execute(intent)
    assert session.scene.passages[1].is_open == (operation == "open")
    assert len(session.interpreter_context()["visible_creatures"]) == (3 if operation == "open" else 0)


def test_real_initial_narration():
    from trama.application.conversation import Conversation

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    session = build_session({'width': 10, 'height': 10, 'start': [4, 4]})
    conversation = Conversation(session)
    request = conversation.narration_context(initial=True)
    with open_services() as services:
        reply = services.narrator.narrate(request)
    assert reply.on
    assert session.state == session.initial_state


def test_real_mixed_message_with_partial_movement():
    from trama.application.conversation import Conversation

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    session = build_session({'width': 10, 'height': 10, 'start': [4, 4]})
    conversation = Conversation(session)
    speech = conversation.prepare("Ande 5 m para o norte. [Quanto movimento me resta?]")
    with open_services() as services:
        plan = services.interpreter.interpret(speech.on, conversation.interpretation_context())
        report = conversation.execute(plan)
        request = conversation.narration_context(speech, report)
        reply = services.narrator.narrate(request)
    final = conversation.finish(reply, request)
    assert session.state.position == Position(4, 1)
    assert session.state.spent_meters == 0
    assert final.on
    assert "0,5 m" in final.off
