from conftest import scripted_responses, sourced_output, sourced_plan
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.conversation import Conversation
from trama.application.interpretation_evaluation import evaluate_plan
from trama.application.intents import ActionPlan, MovementIntent, RuleIntent
from trama.application.session import GameSession
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_plan
from trama.movement import MovementState
from trama.observability import log_context
from trama.scene import Scene
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "pocs/interpretacao/cases.json").read_text())
WALK = {"steps": [{"operation": "move", "segments": [], "dash": False, "clarification": "", "target_id": "guard_door"}]}
WIND = {"steps": [{"operation": "second_wind", "target_id": None, "weapon": "greatsword", "use_inspiration": False}]}
LOOK = {"steps": [{"operation": "look", "text": "Olhar para a porta e ficar de frente para ela."}]}


def response(value):
    return SimpleNamespace(status="completed", output=[], output_text=json.dumps(value))


@pytest.fixture
def session(dice):
    data = json.loads((ROOT / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                       creatures_from_data(data["creatures"]), roller=dice())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_reference_cases_have_independent_expected_results_and_authorization(session, case):
    plan = parse_plan(json.dumps(case["reference_plan"]))
    assert evaluate_plan(case["expected_steps"], plan)["matches_expected"]
    validate_player_plan(case["prompt"], plan, session.interpreter_context())


def test_wrong_resource_plan_is_corrected_once_before_any_game_effect(session, capture_logs):
    prompt = "Eu caminho em direção à porta da sala dos guardas e fico bem diante dela."
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(WIND), response(WALK), operations=["move"])
    original_resources = session.encounter.states.copy()
    with capture_logs() as stream, log_context(interaction_id="repair-walk"):
        plan = OpenAIIntentInterpreter(client).interpret(prompt, session.interpreter_context())
        assert session.encounter.states == original_resources and session.state == session.initial_state
        assert not session.encounter.roller.sides
        report = Conversation(session).execute(plan, player_prompt=prompt)
    calls = client.responses.create.call_args_list
    assert len(calls) == 2
    initial, repaired = [json.loads(call.kwargs["input"]) for call in calls]
    assert initial["player_prompt"] == repaired["player_prompt"] == prompt
    assert repaired["interpretation_attempt"] == 2
    assert repaired["correction"]["previous_plan"]["steps"] == WIND["steps"]
    assert session.state.position == Position(12, 5) and report.progress
    assert session.encounter.states == original_resources and not session.encounter.roller.sides
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    requests = [r for r in records if r["event"] == "ai.request_started"]
    assert len({r["ai_call_id"] for r in requests}) == 2
    assert all(r["interaction_id"] == "repair-walk" for r in requests)
    assert any(r["event"] == "ai.plan_correction_requested" for r in records)
    assert not any(r["event"] == "character.power_used" for r in records)


def test_second_contradiction_stops_without_dice_resources_or_movement(session):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(LOOK), response(WIND), operations=["move"])
    resources = session.encounter.states.copy()
    with pytest.raises(PlanAuthorizationError, match="Nenhuma ação foi executada"):
        OpenAIIntentInterpreter(client).interpret("Caminho até a porta.", session.interpreter_context())
    assert client.responses.create.call_count == 2
    assert session.state == session.initial_state and session.encounter.states == resources
    assert not session.encounter.roller.sides


def test_original_look_error_is_detected_and_corrected_without_extra_effects(session):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(LOOK), response(WALK), operations=["move"])
    plan = OpenAIIntentInterpreter(client).interpret(
        "Eu ando na direção da porta da sala dos guardas. Caminho até ela e fico de frente pra mesma.", session.interpreter_context())
    assert isinstance(plan.steps[0], MovementIntent)
    assert client.responses.create.call_count == 2


def test_whole_plan_is_checked_before_even_the_first_valid_step(session):
    conversation = Conversation(session)
    speech = conversation.prepare("Caminho até a porta.")
    malicious = ActionPlan((MovementIntent((), False, "", "guard_door"), RuleIntent("second_wind")))
    resources = session.encounter.states.copy()
    with pytest.raises(PlanAuthorizationError):
        conversation.execute(malicious, player_prompt=speech.on)
    assert session.state == session.initial_state and session.encounter.states == resources
    assert not session.encounter.roller.sides


def test_minimal_and_full_context_experiment_changes_only_context_not_rules(session):
    full = session.interpreter_context()
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(WALK), response(WALK))
    for mode in ("minimal", "full"):
        OpenAIIntentInterpreter(client, context_mode=mode).interpret("Caminho até a porta.", full)
    minimal_call, full_call = [call.kwargs for call in client.responses.create.call_args_list]
    minimal_payload, full_payload = [json.loads(call["input"]) for call in (minimal_call, full_call)]
    assert "world" not in minimal_payload and "player_sheet" not in minimal_payload
    assert "blocked" not in minimal_payload["map"]
    assert len(full_payload["world"]["npcs"]) == 3
    assert "abilities" in full_payload["player_sheet"]
    assert minimal_call["instructions"] == full_call["instructions"]
    assert minimal_call["text"] == full_call["text"]
    assert len(minimal_call["input"]) < len(full_call["input"])
    assert "world" in full  # Projeção não altera o estado nem o contexto original.


def test_world_and_narrator_keep_full_context_while_interpreter_is_small(session):
    conversation = Conversation(session)
    conversation.prepare("Caminho até a porta. [Como funciona Retomar o Fôlego?]")
    interpretation = conversation.interpretation_context()
    world = conversation.world_context(ActionPlan((MovementIntent((), False, "", "guard_door"),)))
    narration = conversation.narration_context(initial=True)
    assert "world" not in interpretation and "player_sheet" not in interpretation
    assert all("Como funciona" not in json.dumps(c) for c in (interpretation, world))
    assert len(world["world"]["npcs"]) == len(narration["world"]["npcs"]) == 3


def test_evaluator_rejects_correctly_formatted_but_wrong_look_and_power():
    expected = [{"operation": "move", "target_id": "guard_door", "dash": False}]
    assert not evaluate_plan(expected, parse_plan(json.dumps(LOOK)))["matches_expected"]
    assert not evaluate_plan(expected, parse_plan(json.dumps(WIND)))["matches_expected"]


def test_independent_evaluation_detects_semantic_error_even_with_consistent_sources(session):
    # O validador não promete provar o sentido de uma frase. Uma classificação
    # errada mas internamente coerente é medida pelo oráculo independente.
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(WIND))
    plan = OpenAIIntentInterpreter(client).interpret("Caminho até a porta.", session.interpreter_context())
    assert not evaluate_plan([{"operation": "move", "target_id": "guard_door"}], plan)["matches_expected"]
    assert session.encounter.states["player"].second_wind_uses == 2
    assert session.state == session.initial_state  # Interpretar não executa.


def test_experiment_can_disable_correction_to_measure_first_response(session):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(WIND), operations=["move"])
    with pytest.raises(PlanAuthorizationError):
        OpenAIIntentInterpreter(client, max_corrections=0).interpret("Caminho até a porta.", session.interpreter_context())
    assert client.responses.create.call_count == 1
