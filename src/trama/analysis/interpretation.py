"""Experimento somente de interpretação; não executa planos nem ações do Mundo."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

import openai

from trama.application.dialogue import split_speech
from trama.application.interpretation_evaluation import evaluate_plan, summarize_plan
from trama.application.scenarios import load_session
from trama.infrastructure.openai_intent_interpreter import InterpretationError, parse_plan
from trama.infrastructure.openai_config import OpenAIConfig
from trama.infrastructure.openai_services import open_services
from trama.observability import close_logging, configure_logging, log_context

def interaction_records(trace_path: Path, interaction: str) -> list[dict]:
    rotations = [p for p in trace_path.parent.glob(trace_path.name + ".*") if p.suffix[1:].isdigit()]
    paths = sorted(rotations, key=lambda p: int(p.suffix[1:]), reverse=True) + [trace_path]
    records = []
    for path in paths:
        with path.open() as source:
            for line in source:
                if interaction in line:
                    record = json.loads(line)
                    if record.get("interaction_id") == interaction:
                        records.append(record)
    return records


def scenario_context(scenario: str | Path) -> dict:
    """Projeção da sessão real usada por este experimento parcial do adaptador."""
    session = load_session(scenario)
    return session.interpreter_context()


def run_case(client, *, case: dict, context: dict, mode: str, model: str,
             max_corrections: int, trace_path: Path, schema_order: str = "operation-first",
             config: OpenAIConfig | None = None) -> dict:
    interaction = uuid4().hex
    started = perf_counter()
    error = None
    returned = None
    settings = (config or OpenAIConfig.from_env()).for_experiment('interpretation_comparison',
        model=model, context_mode=mode, max_corrections=max_corrections, schema_order=schema_order)
    with log_context(interaction_id=interaction), open_services(settings, client=client) as services:
        try:
            returned = services.interpreter.interpret(
                split_speech(case["prompt"]).on, deepcopy(context))
        except InterpretationError as failure:
            error = {"type": type(failure).__name__, "message": str(failure)}
    records = interaction_records(trace_path, interaction)
    requests = [r["data"]["request"] for r in records if r["event"] == "ai.request_payload"]
    responses = [r["data"] for r in records if r["event"] == "ai.response_received"]
    outputs = [r["data"]["output_text"] for r in records if r["event"] == "ai.response_payload"]
    candidates = []
    with log_context(interaction_id=interaction):
        for output in outputs:
            try:
                plan = parse_plan(output)
                candidates.append(evaluate_plan(case["expected_steps"], plan))
            except InterpretationError:
                candidates.append({"matches_expected": False, "actual": None})
    final_match = evaluate_plan(case["expected_steps"], returned)["matches_expected"] if returned else False
    return {
        "scope": "interpreter_contract",
        "case_id": case["id"], "prompt": case["prompt"], "context_mode": mode, "model": model,
        "schema_order": schema_order,
        "configuration": services.metadata,
        "interaction_id": interaction, "expected": case["expected_steps"], "candidates": candidates,
        "raw_outputs": outputs, "returned": summarize_plan(returned) if returned else None,
        "passed": final_match and error is None, "first_attempt_correct": bool(candidates and candidates[0]["matches_expected"]),
        "error": error, "authorization_rejected": any(r["event"] == "player.plan_authorization_rejected" for r in records),
        "calls": len(requests), "duration_ms": round((perf_counter() - started) * 1000, 3),
        "input_characters": [len(r["input"]) for r in requests],
        "provider_responses": responses,
    }


def summarize_results(results: list[dict]) -> dict:
    summary = {}
    for mode in sorted({r["context_mode"] for r in results}):
        summary[mode] = {}
        for order in sorted({r["schema_order"] for r in results if r["context_mode"] == mode}):
            group = [r for r in results if r["context_mode"] == mode and r["schema_order"] == order]
            usage = [response.get("usage", {}) for r in group for response in r["provider_responses"]]
            tokens = {field: sum(u[field] for u in usage) if usage and all(type(u.get(field)) is int for u in usage) else None
                      for field in ("input_tokens", "output_tokens", "total_tokens")}
            summary[mode][order] = {"cases": len(group), "passed": sum(r["passed"] for r in group),
                         "first_attempt_correct": sum(r["first_attempt_correct"] for r in group),
                         "authorization_rejected": sum(r["authorization_rejected"] for r in group),
                         "calls": sum(r["calls"] for r in group), "tokens": tokens}
    return summary


def main(argv: list[str] | None = None, *, default_cases: Path | None = None,
         default_scenario: Path | None = None):
    parser = argparse.ArgumentParser(description="Compara interpretação com contexto mínimo/completo, sem executar ações.")
    parser.add_argument("--live", action="store_true", help="Executa chamadas reais; exige RUN_OPENAI_LIVE_TESTS=1.")
    parser.add_argument("--cases", type=Path, default=default_cases, required=default_cases is None)
    parser.add_argument("--scenario", type=Path, default=default_scenario, required=default_scenario is None,
                        help="Cenário carregado pela aplicação; não executa planos.")
    parser.add_argument("--case", action="append", dest="case_ids", help="Seleciona um caso por id; pode repetir.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--context", choices=("minimal", "full", "both"), default="both")
    parser.add_argument("--schema-order", choices=("operation-first", "legacy", "both"), default="operation-first",
                        help="Compara a ordem das propriedades, mantendo o restante da chamada igual.")
    parser.add_argument("--max-corrections", type=int, choices=(0, 1), default=0)
    parser.add_argument("--model", help="Modelo alternativo para este experimento.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    config = OpenAIConfig.from_env()
    if args.model is not None:
        config = config.for_experiment('interpretation_comparison', model=args.model)
    if not 1 <= args.repeat <= 20:
        parser.error("--repeat deve estar entre 1 e 20.")
    cases = json.loads(args.cases.read_text())
    if args.case_ids:
        unknown = set(args.case_ids) - {case["id"] for case in cases}
        if unknown:
            parser.error("Casos desconhecidos: " + ", ".join(sorted(unknown)))
        cases = [case for case in cases if case["id"] in args.case_ids]
    modes = ("minimal", "full") if args.context == "both" else (args.context,)
    schema_orders = ("legacy", "operation-first") if args.schema_order == "both" else (args.schema_order,)
    variants = [(mode, order) for mode in modes for order in schema_orders]
    limit = len(cases) * len(variants) * args.repeat * (1 + args.max_corrections)
    if not args.live:
        print(json.dumps({"scope": "interpreter_contract", "live": False,
                          "case_ids": [c["id"] for c in cases], "contexts": modes,
                          "schema_orders": schema_orders,
                          "repeat": args.repeat, "max_calls_if_live": limit}, ensure_ascii=False, indent=2))
        return
    if os.environ.get("RUN_OPENAI_LIVE_TESTS") != "1" or not os.environ.get("OPENAI_API_KEY"):
        parser.error("Para chamadas reais, exporte OPENAI_API_KEY e defina RUN_OPENAI_LIVE_TESTS=1.")
    output = args.output or Path("logs/interpretacao") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    trace = output / "trace.jsonl"
    results = []
    # O contrato e os prompts completos ficam no arquivo, sem inundar o terminal.
    stream = io.StringIO()
    configure_logging(level="DEBUG", log_file=trace, stream=stream, max_bytes=50_000_000)
    try:
        context = scenario_context(args.scenario)
        with open_services(config) as services:
            client = services.client
            metadata = {"scope": "interpreter_contract", "context_source": "session.interpreter_context",
                        "requested_model": config.model, "sdk_version": openai.__version__,
                        "configuration": services.metadata,
                        "provider_host": urlsplit(str(client.base_url)).hostname,
                        "contexts": modes, "schema_orders": schema_orders, "max_corrections": args.max_corrections,
                        "max_calls": limit, "repeat": args.repeat}
            (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
            with (output / "results.jsonl").open("w") as result_file:
                for repetition in range(args.repeat):
                    for case in cases:
                        # Alterna a ordem para não favorecer sempre uma variante por cache/tempo.
                        ordered_variants = variants if repetition % 2 == 0 else list(reversed(variants))
                        for mode, schema_order in ordered_variants:
                            result = run_case(client, case=case, context=context, mode=mode, model=config.model,
                                              max_corrections=args.max_corrections, trace_path=trace, schema_order=schema_order,
                                              config=config)
                            result["repetition"] = repetition + 1
                            results.append(result)
                            result_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                            result_file.flush()
                            stream.seek(0)
                            stream.truncate()
                            print(f"{case['id']} / {mode} / {schema_order}: {'OK' if result['passed'] else 'FALHOU'} ({result['calls']} chamadas)")
        summary = summarize_results(results)
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Resultados e logs: {output}")
    finally:
        close_logging()


if __name__ == "__main__":
    main()
