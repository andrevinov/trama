from conftest import scripted_responses, sourced_output, sourced_plan
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import (
    APIConnectionError, APIStatusError, AuthenticationError, NotFoundError,
    RateLimitError,
)

from trama.application.session import GameSession
from trama.application.context import build_context
from trama.infrastructure.openai_intent_interpreter import (
    DEFAULT_MODEL, InterpretationError, OpenAIIntentInterpreter, parse_intent,
)
from trama.movement import Grid, MovementError, MovementState, Position


def response(payload, status="completed", output=None):
    return SimpleNamespace(status=status, output=output or [], output_text=json.dumps({"steps": [payload]}))


def payload(direction="north", squares=2, dash=False):
    return {"segments": [{"direction": direction, "distance": squares, "unit": "squares"}],
            "dash": dash, "clarification": "", "target_id": None, "operation": "move"}


def test_prompt_to_structured_intent_to_validated_position():
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(payload()))
    interpreter = OpenAIIntentInterpreter(client)
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    intent = interpreter.interpret("Ande duas casas para cima", session.interpreter_context()).steps[0]
    result = session.execute(intent)
    assert result.state.position == Position(4, 2)
    assert result.cost_meters == 3
    call = client.responses.create.call_args.kwargs
    assert call["model"] == DEFAULT_MODEL
    assert call["reasoning"] == {"effort": "low"}
    assert call["max_output_tokens"] == 1000
    assert call["text"]["format"]["strict"] is True
    assert call["store"] is False
    context = json.loads(call["input"])
    assert context["character"]["column"] == 5
    assert context["character"]["row"] == 5
    assert context["player_prompt"] == "Ande duas casas para cima"


def test_model_cannot_override_budget(enter_turn_mode):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(payload("east", 5)))
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4), speed_meters=3))
    enter_turn_mode(session)
    intent = OpenAIIntentInterpreter(client).interpret("ande 5 casas à direita", session.interpreter_context()).steps[0]
    result = session.execute(intent)
    assert "insuficiente" in result.stop_reason
    assert session.state.position == Position(6, 4)
    assert session.state.remaining_meters == 0


@pytest.mark.parametrize("text", [
    "", "not json", "[]", "null", "{}",
    json.dumps({**payload(), "position": [9, 9]}),
    json.dumps(payload(squares=True)),
    json.dumps(payload(squares=0)),
    json.dumps(payload(squares=10001)),
    json.dumps(payload(direction="teleport")),
    json.dumps(payload(dash="false")),
    json.dumps({**payload(), "clarification": None}),
    json.dumps({**payload(), "segments": [None]}),
    json.dumps({**payload(), "clarification": "Preciso perguntar antes"}),
])

def test_malformed_external_output_is_rejected(text):
    with pytest.raises(InterpretationError, match="inválida"):
        parse_intent(text)


@pytest.mark.parametrize("status,output,match", [
    ("incomplete", [], "incompleta"),
    ("failed", [], "incompleta"),
    ("completed", [SimpleNamespace(content=[SimpleNamespace(type="refusal")])], "recusou"),
])
def test_incomplete_or_refused_output_is_not_applied(status, output, match):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(payload(), status, output))
    with pytest.raises(InterpretationError, match=match):
        OpenAIIntentInterpreter(client).interpret("ande", build_context(Grid(10, 10), MovementState(Position(4, 4))))


def test_empty_prompt_never_calls_api():
    client = Mock()
    with pytest.raises(InterpretationError):
        OpenAIIntentInterpreter(client).interpret("  ", build_context(Grid(10, 10), MovementState(Position(4, 4))))
    client.responses.create.assert_not_called()


@pytest.mark.parametrize("error_class,status,expected", [
    (AuthenticationError, 401, "Chave da OpenAI inválida"),
    (RateLimitError, 429, "limite de uso"),
    (NotFoundError, 404, "Modelo indisponível"),
    (APIStatusError, 503, "HTTP 503"),
])
def test_api_errors_have_safe_messages(error_class, status, expected):
    client = Mock()
    api_response = Mock(status_code=status, headers={}, request=Mock())
    client.responses.create.side_effect = error_class(
        "sensitive-provider-details", response=api_response, body=None,
    )
    with pytest.raises(InterpretationError, match=expected) as raised:
        OpenAIIntentInterpreter(client).interpret(
            "ande uma casa ao norte", build_context(Grid(10, 10), MovementState(Position(4, 4))),
        )
    assert "sensitive-provider-details" not in str(raised.value)


def test_connection_failure_is_reported_without_provider_details():
    client = Mock()
    client.responses.create.side_effect = APIConnectionError(request=Mock())
    with pytest.raises(InterpretationError, match="conectar"):
        OpenAIIntentInterpreter(client).interpret(
            "ande uma casa ao norte", build_context(Grid(10, 10), MovementState(Position(4, 4))),
        )
