"""Executar da raiz: poetry run python pocs/movimento/run.py."""

import json
import os
import argparse
from pathlib import Path

from openai import OpenAI

from trama.application.session import GameSession
from trama.infrastructure.openai_intent_interpreter import DEFAULT_MODEL, OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.creatures import creatures_from_data
from trama.movement import Grid, MovementState, Position
from trama.scene import Scene
from trama.ui.movement_window import run_window


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstração de movimento por prompt.")
    parser.add_argument("--scenario", type=Path, default=Path(__file__).with_name("cela_guardas.json"),
                        help="Caminho do arquivo JSON do cenário.")
    data = json.loads(parser.parse_args().scenario.read_text())
    scene = Scene.from_data(data) if "areas" in data else None
    grid = scene.grid if scene else Grid(
        data["width"], data["height"],
        frozenset(Position(*p) for p in data["blocked"]),
        frozenset(Position(*p) for p in data["difficult"]),
    )
    session = GameSession(grid, MovementState(Position(*data["start"]), data["speed_meters"]), scene,
                          creatures_from_data(data.get("creatures", [])))
    model = os.environ.get("TRAMA_OPENAI_MODEL", DEFAULT_MODEL)
    client = OpenAI(timeout=30, max_retries=0) if os.environ.get("OPENAI_API_KEY") else None
    try:
        interpreter = OpenAIIntentInterpreter(client, model) if client is not None else None
        narrator = OpenAINarrator(client, model) if client is not None else None
        run_window(session, interpreter, model, narrator)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
