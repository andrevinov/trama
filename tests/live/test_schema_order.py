"""Comparação real da ordem das chaves, sem executar planos ou alterar o mundo."""

import json
import os
from pathlib import Path
import runpy

import pytest

from trama.infrastructure.openai_services import open_services

ROOT = Path(__file__).resolve().parents[2]
CASES = [case for case in json.loads((ROOT / "pocs/interpretacao/cases.json").read_text())
         if case["id"] in {"real_5_terra", "look", "second_wind"}]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("RUN_OPENAI_LIVE_TESTS") != "1",
                                                reason="Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.")]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_real_operation_first_schema_with_legacy_control(case, tmp_path, capture_logs):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    experiment = runpy.run_path(str(ROOT / "pocs/interpretacao/run.py"))
    trace = tmp_path / "trace.jsonl"
    results = []
    with capture_logs(log_file=trace):
        context = experiment["scenario_context"]()
        with open_services() as services:
            for order in ("legacy", "operation-first"):
                results.append(experiment["run_case"](
                    services.client, case=case, context=context, mode="minimal", model=services.config.model,
                    max_corrections=0, trace_path=trace, schema_order=order, config=services.config))
    (tmp_path / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    # A variante antiga é controle, não uma expectativa de acerto.
    assert results[1]["passed"], f"Esquema corrigido falhou; evidências em {tmp_path}"
