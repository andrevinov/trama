"""Executar da raiz: poetry run python pocs/movimento/run.py."""

import os
import argparse
import logging
from pathlib import Path

from openai import OpenAI

from trama.simulator import load_session
from trama.infrastructure.openai_intent_interpreter import DEFAULT_MODEL, OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector
from trama.ui.movement_window import run_window
from trama.observability import configure_logging, close_logging

logger = logging.getLogger("trama.pocs.simulador")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador do Trama (entrada compatível com a demonstração anterior).")
    parser.add_argument("--scenario", type=Path, default=Path(__file__).resolve().parents[1] / "simulador/dungeon.json",
                        help="Caminho do arquivo JSON do cenário.")
    parser.add_argument("--debug", action="store_true", help="Inclui prompts, respostas, decisões e detalhes das regras nos logs.")
    parser.add_argument("--log-file", type=Path, default=Path("logs/trama.jsonl"), help="Arquivo JSONL de logs (com rotação).")
    args = parser.parse_args()
    configure_logging(level="DEBUG" if args.debug else "INFO", log_file=args.log_file)
    try:
        logger.info("app.started", extra={"data": {"scenario": args.scenario, "debug": args.debug, "log_file": args.log_file}})
        run_demo(args.scenario)
    except Exception:
        logger.exception("app.failed")
        raise
    finally:
        logger.info("app.stopped")
        close_logging()


def run_demo(scenario_path: Path) -> None:
    session = load_session(scenario_path)
    model = os.environ.get("TRAMA_OPENAI_MODEL", DEFAULT_MODEL)
    client = OpenAI(timeout=30, max_retries=0) if os.environ.get("OPENAI_API_KEY") else None
    try:
        interpreter = OpenAIIntentInterpreter(client, model) if client is not None else None
        narrator = OpenAINarrator(client, model) if client is not None else None
        world_director = OpenAIWorldDirector(client, model) if client is not None else None
        run_window(session, interpreter, model, narrator, world_director)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
