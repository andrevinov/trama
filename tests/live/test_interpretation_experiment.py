"""Critérios reais de interpretação; executados somente com autorização explícita."""

import json
import os
from pathlib import Path
import runpy

import pytest

from trama.infrastructure.openai_services import open_services

ROOT = Path(__file__).resolve().parents[2]
CASES = [case for case in json.loads((ROOT / "pocs/interpretacao/cases.json").read_text())
         if case["id"] in {"real_4", "negated_power", "question"}]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("RUN_OPENAI_LIVE_TESTS") != "1",
                                                reason="Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.")]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
@pytest.mark.parametrize("mode", ["minimal", "full"])
def test_real_first_interpretation_preserves_request(case, mode, tmp_path, capture_logs):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    experiment = runpy.run_path(str(ROOT / "pocs/interpretacao/run.py"))
    trace = tmp_path / "trace.jsonl"
    with capture_logs(log_file=trace):
        context = experiment["scenario_context"]()
        with open_services() as services:
            result = experiment["run_case"](services.client, case=case, context=context, mode=mode, model=services.config.model,
                                              max_corrections=0, trace_path=trace, config=services.config)
    (tmp_path / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert result["passed"], f"Resposta incorreta; evidências em {tmp_path}"
