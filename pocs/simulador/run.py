"""Executar da raiz: poetry run python pocs/simulador/run.py --debug."""

from pathlib import Path
from trama.simulator import main

if __name__ == '__main__':
    main(Path(__file__).with_name('dungeon.json'))
