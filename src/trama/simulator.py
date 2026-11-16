"""Composição do simulador: cenário, adaptadores opcionais e janela."""

import argparse
import json
import logging
import os
from pathlib import Path

from openai import OpenAI

from trama.application.dungeon import DungeonSession
from trama.application.session import GameSession
from trama.characters import sheet_from_data
from trama.creatures import creatures_from_data
from trama.movement import Grid, MovementState, Position
from trama.scene import Scene
from trama.infrastructure.openai_intent_interpreter import DEFAULT_MODEL, OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector
from trama.observability import configure_logging, close_logging
from trama.ui.movement_window import run_window

logger = logging.getLogger(__name__)


def load_dungeon(path: Path, *, roller=None) -> DungeonSession:
    return DungeonSession.from_data(json.loads(path.read_text()), roller=roller)


def load_session(path: Path, *, roller=None) -> GameSession:
    """A dungeon é o padrão; mapas anteriores continuam úteis para regressões."""
    data = json.loads(path.read_text())
    if 'dungeon' in data:
        return DungeonSession.from_data(data, roller=roller)
    scene = Scene.from_data(data) if 'areas' in data else None
    grid = scene.movement_grid if scene else Grid(data['width'], data['height'],
        frozenset(Position(*p) for p in data.get('blocked', [])),
        frozenset(Position(*p) for p in data.get('difficult', [])))
    player = sheet_from_data(data.get('player', {}), id='player', name='Jogador', default_level=3)
    return GameSession(grid, MovementState(Position(*data['start']), data.get('speed_meters', player.speed_meters)),
                       scene, creatures_from_data(data.get('creatures', [])), player_sheet=player,
                       enemy_sheets=tuple(sheet_from_data(c.get('sheet', {}), id=c['id'], name=c['name'])
                                          for c in data.get('creatures', [])), roller=roller)


def main(default_scenario: Path):
    parser = argparse.ArgumentParser(description='Simulador narrado do Trama: fuga da dungeon.')
    parser.add_argument('--scenario', type=Path, default=default_scenario)
    parser.add_argument('--debug', action='store_true', help='Registra prompts, contexto, respostas e testes completos.')
    parser.add_argument('--log-file', type=Path, default=Path('logs/trama.jsonl'))
    args = parser.parse_args()
    configure_logging(level='DEBUG' if args.debug else 'INFO', log_file=args.log_file)
    client = None
    try:
        logger.info('app.started', extra={'data': {'scenario': args.scenario, 'debug': args.debug}})
        session = load_session(args.scenario)
        model = os.environ.get('TRAMA_OPENAI_MODEL', DEFAULT_MODEL)
        if os.environ.get('OPENAI_API_KEY'):
            client = OpenAI(timeout=30, max_retries=0)
        run_window(session, OpenAIIntentInterpreter(client, model) if client else None, model,
                   OpenAINarrator(client, model) if client else None,
                   OpenAIWorldDirector(client, model) if client else None)
    except Exception:
        logger.exception('app.failed')
        raise
    finally:
        if client:
            client.close()
        logger.info('app.stopped')
        close_logging()
