"""Composição real e configuração efetiva; somente o transporte externo é simulado."""

from dataclasses import replace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import judged_output

from trama import simulator
from trama.bootstrap import compose_game, open_game
from trama.infrastructure import openai_config, openai_services
from trama.infrastructure.openai_config import OpenAIConfig, ResponseOptions
from trama.infrastructure.openai_services import open_services
from trama.ui.movement_window import MovementWindow

ROOT = Path(__file__).resolve().parents[2]


def client_with_answers():
    client = Mock()
    client.base_url = 'https://user:secret@example.test/path?token=hidden'

    def create(**kwargs):
        task = kwargs['text']['format']['name']
        if task == 'action_plan':
            prompt = json.loads(kwargs['input'])['player_prompt']
            output = {'request_parts': [{'text': prompt, 'kind': 'execute', 'operations': ['look'], 'step_indices': [0]}],
                      'steps': [{'operation': 'look', 'text': prompt}]}
        else:
            output = {'reactions': []} if task == 'world_response' else {'on': 'Você observa o local.', 'off': ''}
        return SimpleNamespace(status='completed', output=[], output_text=json.dumps(output), usage=None)

    client.responses.create.side_effect = create
    return client


def test_configuration_resolves_shared_default_environment_and_explicit_experiments(monkeypatch):
    default = replace(openai_config.DEFAULT_CONFIG, model='changed-default', max_corrections=0)
    monkeypatch.setattr(openai_config, 'DEFAULT_CONFIG', default)
    assert OpenAIConfig.from_env({}) == default
    assert OpenAIConfig.from_env({'TRAMA_OPENAI_MODEL': 'alternate'}).model == 'alternate'
    assert OpenAIConfig.from_env({'OPENAI_API_KEY': 'never-record-this'}).metadata()['profile'] == 'application_default'
    alternative = OpenAIConfig.from_env({'TRAMA_OPENAI_MODEL': 'alternate'})
    assert alternative.metadata()['profile'] == 'experiment'
    assert alternative.metadata()['differences_from_default']['model'] == {'default': 'changed-default', 'actual': 'alternate'}
    assert alternative.for_experiment('first_attempt', max_corrections=0).metadata()['experiment'] == 'first_attempt'


@pytest.mark.parametrize('change', [
    {'model': ''}, {'model': ' spaced '}, {'timeout_seconds': 0}, {'timeout_seconds': float('nan')},
    {'timeout_seconds': True}, {'max_retries': -1}, {'max_corrections': True}, {'max_corrections': 2},
    {'context_mode': 'unknown'}, {'schema_order': 'unknown'}, {'world': {}}, {'experiment': ' '},
])
def test_invalid_configuration_is_rejected_before_client_construction(change):
    with pytest.raises(ValueError):
        OpenAIConfig(**change)


def test_response_options_validate_token_limits():
    for value in (0, True, 2.5):
        with pytest.raises(ValueError):
            ResponseOptions(max_output_tokens=value)
    with pytest.raises(ValueError):
        ResponseOptions(reasoning_effort='')


def test_owned_client_uses_configured_timeout_and_retries_and_closes_on_failure(monkeypatch, capture_logs):
    client = client_with_answers()
    constructor = Mock(return_value=client)
    monkeypatch.setattr(openai_services, 'OpenAI', constructor)
    config = OpenAIConfig(timeout_seconds=12, max_retries=2)
    with capture_logs() as stream, pytest.raises(RuntimeError):
        with open_services(config) as services:
            assert services.client is client and services.metadata['provider_host'] == 'example.test'
            raise RuntimeError('Falha do consumidor.')
    constructor.assert_called_once_with(timeout=12, max_retries=2)
    client.close.assert_called_once()
    assert 'secret' not in stream.getvalue() and 'hidden' not in stream.getvalue()


def test_injected_client_is_not_closed_and_missing_credentials_are_only_optional_for_simulator(monkeypatch):
    client = client_with_answers()
    constructor = Mock(side_effect=RuntimeError('Credenciais ausentes.'))
    monkeypatch.setattr(openai_services, 'OpenAI', constructor)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with open_services(allow_unconfigured=True) as services:
        assert services.metadata['enabled'] is False
        assert services.interpreter is services.narrator is services.world_director is None
    constructor.assert_not_called()
    with open_services(client=client) as services:
        assert services.metadata['client_source'] == 'injected'
    client.close.assert_not_called()
    with pytest.raises(RuntimeError, match='Credenciais'):
        with open_services():
            pytest.fail('Não pode substituir o serviço ausente.')


def test_shared_services_send_actual_generation_parameters_and_preserve_prompts():
    client = client_with_answers()
    config = OpenAIConfig(model='explicit-model', max_corrections=0,
        interpretation=ResponseOptions(321, 'medium'), narration=ResponseOptions(654, 'medium'),
        world=ResponseOptions(987, 'medium'))
    with open_game({'width': 4, 'height': 4, 'start': [1, 1]}, config, client=client) as game:
        flow = game.flow
        runner = game.runner
        assert runner is game.runner and runner.flow is flow
        assert runner.start().status == 'completed'
        assert runner.submit('Olho ao redor.').status == 'completed'
        assert flow.error is None
        metadata = game.services.metadata
        assert flow.interpreter.max_corrections == 0
        assert flow.session is flow.conversation.session
    calls = [c.kwargs for c in client.responses.create.call_args_list]
    assert len(calls) == 4
    for call in calls:
        task = call['text']['format']['name']
        phase = {'action_plan': 'interpretation', 'narrator_reply': 'narration', 'world_response': 'world'}[task]
        assert call['model'] == metadata['model'] == 'explicit-model'
        assert call['reasoning']['effort'] == metadata[phase]['reasoning_effort'] == 'medium'
        assert call['max_output_tokens'] == metadata[phase]['max_output_tokens']
        assert call['store'] is False and call['text']['format']['strict'] is True
    from trama.infrastructure import openai_intent_interpreter, openai_narrator, openai_world_director
    instructions = {m.INSTRUCTIONS for m in (openai_intent_interpreter, openai_narrator, openai_world_director)}
    assert {call['instructions'] for call in calls} == instructions
    assert metadata['profile'] == 'experiment'


def test_changed_application_defaults_reach_simulator_window_and_live_composition(monkeypatch, tmp_path, capture_logs):
    settings = replace(openai_config.DEFAULT_CONFIG, model='new-application-model', timeout_seconds=17,
                       max_retries=1, max_corrections=0, interpretation=ResponseOptions(777))
    monkeypatch.setattr(openai_config, 'DEFAULT_CONFIG', settings)
    monkeypatch.delenv('TRAMA_OPENAI_MODEL', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-unused-key')
    clients = []

    def construct(**kwargs):
        assert kwargs == {'timeout': 17, 'max_retries': 1}
        client = client_with_answers()
        clients.append(client)
        return client

    monkeypatch.setattr(openai_services, 'OpenAI', construct)
    windows = []

    def window(session, interpreter, model, narrator, director, *, flow):
        view = MovementWindow(session, interpreter, model, narrator, director, flow=flow)
        assert view.flow is flow and flow.interpreter.max_corrections == 0
        windows.append(view)

    monkeypatch.setattr(simulator, 'run_window', window)
    monkeypatch.setattr('sys.argv', ['simulador', '--log-file', str(tmp_path / 'ui.jsonl')])
    simulator.main()
    assert windows[0].model == 'new-application-model'
    support = runpy.run_path(str(ROOT / 'tests/live/test_contextual_movement.py'))
    case = next(c for c in support['CASES'] if c['expected'] == 'investigate')
    # Respostas explícitas do transporte; preparação e avaliação continuam reais.
    answers = iter([
        {'on': 'Você ouve sua cela abrir.', 'off': ''},
        {'request_parts': [{'text': case['prompt'], 'kind': 'execute', 'operations': ['investigate'], 'step_indices': [0]}],
         'steps': [{'operation': 'investigate', 'target_id': 'cell_4'}]},
        {'reactions': []}, {'on': 'Você entra na cela e encontra os objetos.', 'off': ''}])
    original = construct

    def live_client(**kwargs):
        client = original(**kwargs)
        client.responses.create.side_effect = lambda **kw: SimpleNamespace(status='completed', output=[], output_text=json.dumps(judged_output(next(answers), kw)), usage=None)
        return client

    monkeypatch.setattr(openai_services, 'OpenAI', live_client)
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path / 'live'))
    support['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next((tmp_path / 'live').rglob('result.json')).read_text())
    assert evidence['stage'] == 'passed'
    assert evidence['configuration']['profile'] == 'application_default'
    assert evidence['configuration']['model'] == windows[0].model
    assert evidence['configuration']['max_corrections'] == windows[0].flow.interpreter.max_corrections
    assert all(call.kwargs['max_output_tokens'] == 777 for call in clients[-1].responses.create.call_args_list
               if call.kwargs['text']['format']['name'] == 'action_plan')
    for client in clients:
        client.close.assert_called_once()


def test_composing_prepared_session_preserves_state_and_rejects_late_roller():
    client = client_with_answers()
    with open_game({'width': 4, 'height': 4, 'start': [1, 1]}, client=client) as game:
        session = game.flow.session
        again = compose_game(session, game.services)
        assert again.session is session
        with pytest.raises(ValueError, match='rolagens'):
            compose_game(session, game.services, roller=Mock())
        with pytest.raises(ValueError, match='fluxo composto'):
            MovementWindow(session, None, 'teste', flow=game.flow)


def test_live_evidence_recorder_saves_effective_configuration_even_if_client_initialization_fails(monkeypatch, tmp_path):
    recorder = runpy.run_path(str(ROOT / 'tests/live/conftest.py'))['record_service_configuration'].__wrapped__(tmp_path)
    monkeypatch.setattr(openai_services, 'OpenAI', Mock(side_effect=RuntimeError('Falha de inicialização.')))
    next(recorder)
    try:
        with pytest.raises(RuntimeError, match='inicialização'):
            with open_services(OpenAIConfig(model='attempted-model')):
                pytest.fail('Cliente deveria falhar antes de iniciar.')
    finally:
        with pytest.raises(StopIteration):
            next(recorder)
    evidence = json.loads((tmp_path / 'configurations.json').read_text())
    assert evidence[0]['model'] == 'attempted-model'
    assert evidence[0]['status'] == 'initialization_failed' and evidence[0]['enabled'] is False
