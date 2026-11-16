"""Composição do simulador: cenário, adaptadores opcionais e janela."""

import argparse
import logging
from pathlib import Path

# Reexporta os nomes usados pelos runners anteriores, sem duplicar a construção.
from trama.application.scenarios import load_dungeon, load_session
from trama.bootstrap import open_game
from trama.observability import configure_logging, close_logging
from trama.ui.movement_window import run_window

logger = logging.getLogger(__name__)


def main(default_scenario: Path):
    parser = argparse.ArgumentParser(description='Simulador narrado do Trama: fuga da dungeon.')
    parser.add_argument('--scenario', type=Path, default=default_scenario)
    parser.add_argument('--debug', action='store_true', help='Registra prompts, contexto, respostas e testes completos.')
    parser.add_argument('--log-file', type=Path, default=Path('logs/trama.jsonl'))
    args = parser.parse_args()
    configure_logging(level='DEBUG' if args.debug else 'INFO', log_file=args.log_file)
    try:
        logger.info('app.started', extra={'data': {'scenario': args.scenario, 'debug': args.debug}})
        with open_game(args.scenario, allow_unconfigured=True) as game:
            services, flow = game.services, game.flow
            run_window(flow.session, services.interpreter, services.config.model,
                       services.narrator, services.world_director, flow=flow)
    except Exception:
        logger.exception('app.failed')
        raise
    finally:
        logger.info('app.stopped')
        close_logging()
