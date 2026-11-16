"""Entrada oficial, cenário empacotado e execução fora da raiz, sem rede ou GUI."""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from trama import simulator
from trama.application.game_flow import GameFlow
from trama.infrastructure import openai_services
from trama.spatial import Position


ROOT = Path(__file__).resolve().parents[2]


def forbid_provider(*args, **kwargs):
    raise AssertionError('A verificação do comando não pode criar um cliente de IA.')


def test_default_entry_loads_packaged_dungeon_from_another_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(openai_services, 'OpenAI', forbid_provider)
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', '--log-file', 'entry.jsonl'])
    windows = []

    def window(session, interpreter, model, narrator, director, *, flow):
        assert isinstance(flow, GameFlow) and flow.session is session
        assert session.state.position == Position(3, 21)
        assert (session.grid.width, session.grid.height) == (19, 25)
        assert len(session.scene.objects) == 4 and len(session.creatures) == 1
        assert session.encounter.player_sheet.weapons == ()
        assert interpreter is narrator is director is None
        windows.append(flow)

    monkeypatch.setattr(simulator, 'run_window', window)
    simulator.main()
    assert len(windows) == 1
    assert (tmp_path / 'entry.jsonl').is_file()


def test_explicit_relative_scenario_uses_callers_directory_without_default_fallback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(openai_services, 'OpenAI', forbid_provider)
    monkeypatch.setattr(simulator, 'files', lambda *args: pytest.fail('Não deve consultar o cenário padrão.'))
    (tmp_path / 'custom.json').write_text('{"width": 3, "height": 4, "start": [1, 2]}')
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', '--scenario', 'custom.json'])
    windows = []
    monkeypatch.setattr(simulator, 'run_window', lambda session, *args, **kwargs: windows.append(session))
    simulator.main()
    assert len(windows) == 1
    assert windows[0].scene is None
    assert windows[0].state.position == Position(1, 2)
    assert (windows[0].grid.width, windows[0].grid.height) == (3, 4)


def test_missing_explicit_scenario_is_reported_without_opening_window(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(openai_services, 'OpenAI', forbid_provider)
    monkeypatch.setattr(simulator, 'run_window', lambda *args, **kwargs: pytest.fail('Cenário ausente.'))
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', '--scenario', 'missing.json'])
    with pytest.raises(FileNotFoundError):
        simulator.main()


def test_window_failure_closes_shared_services_and_preserves_precomposed_flow(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-unused-key')
    monkeypatch.setenv('TRAMA_OPENAI_MODEL', 'configured-model')
    client = Mock()
    client.base_url = 'https://example.test'
    constructor = Mock(return_value=client)
    monkeypatch.setattr(openai_services, 'OpenAI', constructor)
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', '--debug'])
    windows = []

    def fail_window(session, interpreter, model, narrator, director, *, flow):
        assert flow.session is session
        assert (flow.interpreter, flow.narrator, flow.world_director) == (interpreter, narrator, director)
        assert model == 'configured-model'
        assert flow.interpreter.client is client
        windows.append(flow)
        raise RuntimeError('Falha da janela.')

    monkeypatch.setattr(simulator, 'run_window', fail_window)
    with pytest.raises(RuntimeError, match='Falha da janela'):
        simulator.main()
    assert len(windows) == constructor.call_count == 1
    client.close.assert_called_once()
    client.responses.create.assert_not_called()
    records = [json.loads(line) for line in (tmp_path / 'logs/trama.jsonl').read_text().splitlines()]
    assert [r['event'] for r in records if r['event'].startswith('app.')] == [
        'app.started', 'app.failed', 'app.stopped']
    failure = next(r for r in records if r['event'] == 'app.failed')
    assert failure['error']['type'] == 'RuntimeError'


def test_official_cli_opens_and_closes_real_pygame_loop_without_a_provider(tmp_path):
    code = r'''
import sys
import pygame
from trama import simulator
from trama.infrastructure import openai_services
def forbid_provider(*args, **kwargs):
    raise AssertionError('O smoke da janela não pode criar um cliente de IA.')
openai_services.OpenAI = forbid_provider
# Somente a entrada de eventos é simulada. Janela, desenho, composição e recurso
# da dungeon usam a implementação real, com o driver SDL sem tela.
pygame.event.get = lambda: [pygame.event.Event(pygame.QUIT)]
sys.argv = ['trama-simulator']
simulator.main()
assert not pygame.display.get_init() and not pygame.font.get_init()
print('pygame-cli-ok')
'''
    env = {k: v for k, v in os.environ.items() if k != 'OPENAI_API_KEY'}
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYGAME_HIDE_SUPPORT_PROMPT='1')
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'pygame-cli-ok' in result.stdout
    records = [json.loads(line) for line in (tmp_path / 'logs/trama.jsonl').read_text().splitlines()]
    assert [r['event'] for r in records if r['event'].startswith('app.')] == ['app.started', 'app.stopped']
    assert next(r for r in records if r['event'] == 'ai.services_configured')['data']['enabled'] is False


@pytest.fixture(scope='module')
def built_wheel(tmp_path_factory):
    output = tmp_path_factory.mktemp('simulator-wheel')
    result = subprocess.run(
        ['poetry', 'build', '--format', 'wheel', '--output', str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(output.glob('*.whl'))
    assert len(wheels) == 1
    return wheels[0]


@pytest.mark.parametrize('mode', ['help', 'open', 'situation'])
def test_wheel_entry_and_resource_work_without_source_checkout(built_wheel, tmp_path, mode):
    # Importa diretamente do wheel (ZIP), exercitando também a extração temporária
    # do recurso. Dependências vêm do ambiente Poetry; nenhum fonte do Trama é usado.
    code = r'''
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path
import sys

wheel, mode = sys.argv[1:]
sys.path.insert(0, wheel)
import trama
assert trama.__file__.startswith(wheel), trama.__file__
entry, = [e for e in distribution('trama').entry_points
          if e.group == 'console_scripts' and e.name == 'trama-simulator']
simulator = import_module('trama.simulator')
from trama.infrastructure import openai_services
def forbid_provider(*args, **kwargs):
    raise AssertionError('Nenhum serviço externo deve ser criado.')
openai_services.OpenAI = forbid_provider
windows = []
def window(session, interpreter, model, narrator, director, *, flow):
    assert flow.session is session
    assert session.grid.width == 19 and session.grid.height == 25
    assert (session.state.position.x, session.state.position.y) == ((7, 9) if mode == 'situation' else (3, 21))
    assert len(session.scene.objects) == 4 and len(session.creatures) == 1
    assert interpreter is narrator is director is None
    windows.append(flow)
simulator.run_window = window
sys.argv = ['trama-simulator', '--help'] if mode == 'help' else ['trama-simulator']
if mode == 'situation':
    sys.argv += ['--situation', 'investigar-cela-do-log']
if mode == 'help':
    try:
        entry.load()()
    except SystemExit as exit:
        assert exit.code == 0
    else:
        raise AssertionError('--help deveria encerrar antes de abrir a partida.')
    assert not windows
else:
    entry.load()()
    assert len(windows) == 1
    assert Path('logs/trama.jsonl').is_file()
print('wheel-entry-ok')
'''
    env = {k: v for k, v in os.environ.items() if k != 'OPENAI_API_KEY'}
    result = subprocess.run([sys.executable, '-I', '-c', code, str(built_wheel), mode],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'wheel-entry-ok' in result.stdout
