"""Composição do simulador: cenário, adaptadores opcionais e janela."""

import argparse
from contextlib import ExitStack
from importlib.resources import as_file, files
import logging
from pathlib import Path

from trama.application.situations import load_situation
from trama.bootstrap import open_game, open_situation
from trama.observability import configure_logging, close_logging
from trama.ui.movement_window import run_window

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Simulador narrado do Trama: fuga da dungeon.')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--scenario', type=Path,
                        help='Arquivo JSON de cenário; o padrão é a dungeon distribuída com o pacote.')
    selection.add_argument('--situation', help='Identificador de uma situação reproduzível do catálogo da dungeon.')
    parser.add_argument('--debug', action='store_true', help='Registra prompts, contexto, respostas e testes completos.')
    parser.add_argument('--log-file', type=Path, default=Path('logs/trama.jsonl'))
    args = parser.parse_args()
    configure_logging(level='DEBUG' if args.debug else 'INFO', log_file=args.log_file)
    try:
        with ExitStack() as resources:
            scenario = args.scenario
            situation = load_situation(args.situation) if args.situation else None
            if scenario is None and situation is None:
                resource = files('trama').joinpath('scenarios', 'dungeon_escape.json')
                scenario = resources.enter_context(as_file(resource))
            logger.info('app.started', extra={'data': {'scenario': scenario, 'situation_id': args.situation, 'debug': args.debug}})
            runtime = (open_situation(situation, allow_unconfigured=True) if situation else
                       open_game(scenario, allow_unconfigured=True))
            with runtime as game:
                services, flow = game.services, game.flow
                run_window(flow.session, services.interpreter, services.config.model,
                           services.narrator, services.world_director, flow=flow)
    except Exception:
        logger.exception('app.failed')
        raise
    finally:
        logger.info('app.stopped')
        close_logging()


if __name__ == '__main__':
    main()
