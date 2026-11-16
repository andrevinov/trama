"""Prévia e execução explícita de análises parciais; não é uma entrada de jogo."""

from pathlib import Path

from trama.analysis.interpretation import main

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    main(default_cases=ROOT / 'tests/fixtures/interpretation/cases.json',
         default_scenario=ROOT / 'tests/fixtures/scenarios/legacy_cell_and_guards.json')
