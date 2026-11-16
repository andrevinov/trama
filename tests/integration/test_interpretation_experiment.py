"""Contrato parcial do interpretador; somente o transporte externo é simulado."""

from conftest import scripted_responses, sourced_output, sourced_plan
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.analysis import interpretation as experiment
from trama.infrastructure import openai_services

ROOT = Path(__file__).resolve().parents[2]


def test_preview_never_constructs_client_even_when_credentials_exist(monkeypatch, capsys):
    constructor = Mock(side_effect=AssertionError("Não deve criar cliente na prévia"))
    monkeypatch.setattr(openai_services, "OpenAI", constructor)
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("RUN_OPENAI_LIVE_TESTS", "1")
    monkeypatch.setattr("sys.argv", ["run.py", "--case", "real_4"])
    experiment.main(default_cases=ROOT / "tests/fixtures/interpretation/cases.json",
                        default_scenario=ROOT / "tests/fixtures/scenarios/legacy_cell_and_guards.json")
    preview = json.loads(capsys.readouterr().out)
    assert not preview["live"] and preview["max_calls_if_live"] == 2
    assert preview['scope'] == 'interpreter_contract'
    constructor.assert_not_called()


def test_live_needs_explicit_gate_before_client_or_output_files(monkeypatch, tmp_path):
    constructor = Mock(side_effect=AssertionError("Não deve criar cliente sem autorização"))
    monkeypatch.setattr(openai_services, "OpenAI", constructor)
    monkeypatch.delenv("RUN_OPENAI_LIVE_TESTS", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    output = tmp_path / "experiment"
    monkeypatch.setattr("sys.argv", ["run.py", "--live", "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        experiment.main(default_cases=ROOT / "tests/fixtures/interpretation/cases.json",
                        default_scenario=ROOT / "tests/fixtures/scenarios/legacy_cell_and_guards.json")
    assert error.value.code == 2 and not output.exists()
    constructor.assert_not_called()


def test_experiment_records_wrong_raw_plan_and_grades_independently_without_execution(capture_logs, tmp_path):
    case = next(c for c in json.loads((ROOT / "tests/fixtures/interpretation/cases.json").read_text()) if c["id"] == "real_4")
    client = Mock()
    client.responses.create.side_effect = scripted_responses(*[
        SimpleNamespace(status="completed", output=[], output_text=json.dumps(case["reference_plan"]), model="reported-model"),
        SimpleNamespace(status="completed", output=[], output_text='{"steps":[{"operation":"second_wind","target_id":null,"weapon":"greatsword","use_inspiration":false}]}', model="reported-model"),
    ], operations=["move"])
    trace = tmp_path / "trace.jsonl"
    with capture_logs(log_file=trace):
        context = experiment.scenario_context(ROOT / "tests/fixtures/scenarios/legacy_cell_and_guards.json")
        results = [experiment.run_case(client, case=case, context=context, mode=mode, model="requested-model",
                                           max_corrections=0, trace_path=trace) for mode in ("minimal", "full")]
    compact, full = results
    assert compact['scope'] == full['scope'] == 'interpreter_contract'
    assert compact["passed"] and compact["first_attempt_correct"]
    assert not full["passed"] and full["authorization_rejected"]
    assert full["candidates"][0]["actual"][0]["operation"] == "second_wind"
    assert full["raw_outputs"] and full["returned"] is None
    assert compact["provider_responses"][0]["response_model"] == "reported-model"
    assert compact["input_characters"][0] < full["input_characters"][0]
    summary = experiment.summarize_results(results)
    assert summary["minimal"]["operation-first"]["passed"] == 1 and summary["full"]["operation-first"]["passed"] == 0
    assert summary["full"]["operation-first"]["tokens"]["total_tokens"] is None
    records = [json.loads(line) for line in trace.read_text().splitlines()]
    assert not any(r["event"].startswith(("game.operation_", "world.action_", "dice.")) for r in records)


def test_experiment_live_loop_can_be_exercised_with_fake_sdk(monkeypatch, tmp_path, capture_logs):
    cases = json.loads((ROOT / "tests/fixtures/interpretation/cases.json").read_text())
    case = next(c for c in cases if c["id"] == "real_4")
    client = Mock()
    client.base_url = "https://user:secret@example.test/api/?secret=hidden"
    client.responses.create.side_effect = scripted_responses(*[SimpleNamespace(status="completed", output=[], output_text=json.dumps(case["reference_plan"])) for _ in range(2)])
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(openai_services, "OpenAI", Mock(return_value=client))
    monkeypatch.setenv("RUN_OPENAI_LIVE_TESTS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    output = tmp_path / "experiment"
    monkeypatch.setattr("sys.argv", ["run.py", "--live", "--case", "real_4", "--output", str(output)])
    with capture_logs():
        experiment.main(default_cases=ROOT / "tests/fixtures/interpretation/cases.json",
                        default_scenario=ROOT / "tests/fixtures/scenarios/legacy_cell_and_guards.json")
    results = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert len(results) == 2 and all(r["passed"] for r in results)
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["provider_host"] == "example.test"
    assert metadata['scope'] == 'interpreter_contract'
    assert metadata['context_source'] == 'session.interpreter_context'
    assert "secret" not in (output / "metadata.json").read_text()
    assert (output / "summary.json").exists()


def test_tool_preview_from_another_directory_uses_shared_entry_and_repository_data(tmp_path):
    # Mesmo com chave e autorização, a ausência de --live mantém a prévia offline.
    env = {**os.environ, 'OPENAI_API_KEY': 'offline-unused-key', 'RUN_OPENAI_LIVE_TESTS': '1'}
    result = subprocess.run([sys.executable, str(ROOT / 'tools/analyze_interpretation.py'), '--case', 'real_4'],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview['case_ids'] == ['real_4']
    assert preview['scope'] == 'interpreter_contract' and not preview['live']
    assert preview['max_calls_if_live'] == 2
    assert list(tmp_path.iterdir()) == []


def test_analysis_context_loads_explicit_scenario_through_application(monkeypatch, tmp_path):
    scenario = tmp_path / 'custom.json'
    scenario.write_text('{"width": 3, "height": 4, "start": [1, 2]}')
    loader = Mock(wraps=experiment.load_session)
    monkeypatch.setattr(experiment, 'load_session', loader)
    monkeypatch.chdir(tmp_path)
    context = experiment.scenario_context(scenario)
    loader.assert_called_once_with(scenario)
    assert context['character']['column'] == 2 and context['character']['row'] == 3
