"""Situações jogáveis e avaliações compartilham dados, preparação e reinício."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import without_correlation_ids

from trama import simulator
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, ScenarioIntent
from trama.application.situations import Situation, SituationError, load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure import openai_services


INITIAL_STATES = [
    ('investigar-cela-do-log', [8, 10], 'narrated', 0),
    ('pegar-espada-distante', [8, 10], 'narrated', 0),
    ('atacar-com-aproximacao', [9, 8], 'narrated', 0),
    ('ataque-com-movimento-insuficiente', [9, 8], 'turn_based', 7.5),
    ('ataque-guarda-vence-iniciativa', [9, 8], 'narrated', 0),
    ('investigar-grade-fechada', [8, 10], 'narrated', 0),
    ('investigar-sem-sair-do-lugar', [8, 10], 'narrated', 0),
    ('investigar-com-ataque-de-oportunidade', [12, 4], 'turn_based', 0),
]


@pytest.mark.parametrize('id,position,mode,spent', INITIAL_STATES)
def test_cli_and_headless_open_same_validated_situation(id, position, mode, spent, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    constructor = Mock(side_effect=AssertionError('Nenhum cliente real nesta verificação.'))
    monkeypatch.setattr(openai_services, 'OpenAI', constructor)
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', '--situation', id])
    observed = []

    def window(session, *args, flow):
        assert session is flow.session
        observed.append(situation_state(session))
        assert observed[-1]['position'] == position
        assert observed[-1]['mode'] == mode
        assert observed[-1]['spent_meters'] == spent

    monkeypatch.setattr(simulator, 'run_window', window)
    simulator.main()
    with open_situation(load_situation(id), allow_unconfigured=True) as game:
        assert without_correlation_ids(situation_state(game.flow.session)) == without_correlation_ids(observed[0])
    constructor.assert_not_called()


def test_reset_replays_preparation_dice_history_and_execution_memory(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation('investigar-cela-do-log')
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='Você observa o local.'))
        initial = situation_state(game.flow.session)
        assert game.runner.start().status == 'completed'
        for _ in range(2):
            assert game.flow.conversation.messages[-1].speech.on.startswith('Você percorre 6 m')
            assert len(game.flow.conversation.messages) == 1 + len(situation.initial_history)
            report = game.flow.conversation.execute(ActionPlan((ScenarioIntent('investigate', 'cell_4'),)))
            assert report.status == 'completed'
            assert set(game.flow.session.dungeon.discovered) == {'longsword', 'cleaner_uniform'}
            assert game.runner.reset().status == 'completed'
            assert without_correlation_ids(situation_state(game.flow.session)) == without_correlation_ids(initial)
            assert roller.used == [[20, 20]]
            assert len(roller.pending) == 1
            previous = game.flow.conversation.narration_context()['previous_execution']['execution']
            assert [e['operation'] for e in previous['events']] == ['move', 'open']


@pytest.mark.parametrize('selection', [
    ['--situation', 'nao-existe'],
    ['--situation', 'investigar-cela-do-log', '--scenario', 'ignored.json'],
])
def test_invalid_cli_selection_never_opens_window_or_provider(selection, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['trama-simulator', *selection])
    window = Mock(side_effect=AssertionError('Não deve abrir janela.'))
    client = Mock(side_effect=AssertionError('Não deve abrir cliente.'))
    monkeypatch.setattr(simulator, 'run_window', window)
    monkeypatch.setattr(openai_services, 'OpenAI', client)
    with pytest.raises((SituationError, SystemExit)):
        simulator.main()
    window.assert_not_called()
    client.assert_not_called()


@pytest.mark.parametrize('defect', ['unknown_field', 'unknown_setup', 'invalid_history', 'variation', 'hp'])
def test_invalid_declaration_fails_without_a_provider(defect, monkeypatch):
    original = load_situation('investigar-cela-do-log')
    data = deepcopy(original.data)
    if defect == 'unknown_field':
        data['system_prompt'] = 'Não pode substituir o prompt da aplicação.'
    elif defect == 'unknown_setup':
        data['setup'] = ['teleport']
    elif defect == 'invalid_history':
        data['history']['messages'][0]['role'] = 'system'
    elif defect == 'variation':
        data['passage_variations'] = {'gate_4': {'locked': 'false'}}
    else:
        data['preconditions']['resources.player.hp'] = 999
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError):
        situation = Situation(data, original.preparations)
        with open_situation(situation, allow_unconfigured=True):
            pytest.fail('Situação inválida não deve ser disponibilizada.')


def test_failed_preparation_closes_owned_client_without_any_model_request(monkeypatch):
    original = load_situation('investigar-cela-do-log')
    data = deepcopy(original.data)
    data['preconditions']['resources.player.hp'] = 999
    client = Mock()
    client.base_url = 'https://offline.test'
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-unused-key')
    monkeypatch.setattr(openai_services, 'OpenAI', Mock(return_value=client))
    with pytest.raises(SituationError, match='pré-condição'):
        with open_situation(Situation(data, original.preparations)):
            pytest.fail('Não deve abrir uma situação inválida.')
    client.close.assert_called_once()
    client.responses.create.assert_not_called()


def test_live_case_data_only_add_inputs_limits_and_independent_criteria():
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / 'tests/fixtures/contextual_movement/cases.json').read_text())
    for case in cases:
        assert set(case) == {'id', 'prompt', 'expected', 'choices', 'max_sdk_calls'}
        assert not Situation.fields & (case.keys() - {'id'})
        assert load_situation(case['id']).data['id'] == case['id']
