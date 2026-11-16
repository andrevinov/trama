"""Regressões da ordem do discriminador no contrato de saída estruturada."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
from conftest import sourced_output
from openai import OpenAI

from trama.analysis import interpretation as experiment
from trama.application.intents import MovementIntent
from trama.infrastructure import openai_services
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, PLAN_SCHEMA, action_plan_schema

ROOT = Path(__file__).resolve().parents[2]
WALK = {"steps": [{"operation": "move", "segments": [], "target_id": "guard_door", "dash": False, "clarification": ""}]}


def test_every_action_format_starts_with_operation_and_variants_only_differ_in_key_order():
    corrected = action_plan_schema()
    legacy = action_plan_schema("legacy")
    assert all(next(iter(branch["properties"])) == "operation"
               for branch in corrected["properties"]["steps"]["items"]["anyOf"])
    assert next(iter(legacy["properties"]["steps"]["items"]["anyOf"][0]["properties"])) == "segments"
    assert json.dumps(corrected, sort_keys=True) == json.dumps(legacy, sort_keys=True)
    assert json.dumps(corrected) != json.dumps(legacy)
    legacy["properties"]["steps"]["items"]["anyOf"][0]["properties"].clear()
    assert corrected == PLAN_SCHEMA  # Variantes não alteram o contrato global.


def test_real_sdk_serializes_operation_first_and_ab_changes_only_schema_order():
    requests = []

    def intercept(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json={
            "id": "resp_offline", "object": "response", "created_at": 0, "status": "completed",
            "model": "offline-model", "output": [{"id": "msg_offline", "type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text", "text": json.dumps(sourced_output(WALK, "Caminho até a porta.")), "annotations": []}]}],
        })

    context = {"mode": "narrated", "character": {"column": 4, "row": 6},
               "map": {"scene": {"passages": [{"id": "guard_door"}]}}}
    with OpenAI(api_key="offline-test-key", max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(intercept))) as client:
        for order in ("legacy", "operation-first"):
            plan = OpenAIIntentInterpreter(client, schema_order=order).interpret("Caminho até a porta.", context)
            assert isinstance(plan.steps[0], MovementIntent)
    before, after = requests
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    before_schema, after_schema = [r["text"]["format"]["schema"] for r in requests]
    assert next(iter(before_schema["properties"]["steps"]["items"]["anyOf"][0]["properties"])) == "segments"
    assert next(iter(after_schema["properties"]["steps"]["items"]["anyOf"][0]["properties"])) == "operation"


def test_schema_comparison_runner_records_separate_results_and_preserves_other_parameters(tmp_path, monkeypatch, capture_logs):
    client = Mock()
    recorded = []

    def create(**kwargs):
        recorded.append(kwargs)
        branch = kwargs["text"]["format"]["schema"]["properties"]["steps"]["items"]["anyOf"][0]
        output = WALK if next(iter(branch["properties"])) == "operation" else {
            "steps": [{"operation": "attack", "target_id": "guard_door", "weapon": "greatsword", "use_inspiration": False}]}
        return SimpleNamespace(status="completed", output=[], output_text=json.dumps(sourced_output(output, json.loads(kwargs["input"])["player_prompt"], operations=["move"])))

    client.responses.create.side_effect = create
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(openai_services, "OpenAI", Mock(return_value=client))
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("RUN_OPENAI_LIVE_TESTS", "1")
    output = tmp_path / "comparison"
    monkeypatch.setattr("sys.argv", ["run.py", "--live", "--case", "real_5_terra", "--context", "minimal",
                                    "--schema-order", "both", "--output", str(output)])
    with capture_logs():
        experiment.main(default_cases=ROOT / "tests/fixtures/interpretation/cases.json",
                        default_scenario=ROOT / "tests/fixtures/scenarios/legacy_cell_and_guards.json")
    results = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert [(r["schema_order"], r["passed"]) for r in results] == [("legacy", False), ("operation-first", True)]
    assert all(r["calls"] == 1 for r in results)
    assert json.dumps(recorded[0], sort_keys=True) == json.dumps(recorded[1], sort_keys=True)
    summary = json.loads((output / "summary.json").read_text())["minimal"]
    assert summary["legacy"]["passed"] == 0 and summary["operation-first"]["passed"] == 1
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["max_calls"] == 2 and metadata["schema_orders"] == ["legacy", "operation-first"]
