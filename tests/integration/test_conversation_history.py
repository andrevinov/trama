"""Histórico importado e conversa normal usam a mesma entrada; sem serviços externos."""

from copy import deepcopy

import pytest

from trama.application.conversation import Conversation
from trama.application.dialogue import DialogueMessage, Speech
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment
from trama.application.scenarios import build_session


def conversation():
    return Conversation(build_session({'width': 5, 'height': 5, 'start': [1, 1]}))


def test_imported_history_preserves_state_execution_memory_and_off_separation():
    c = conversation()
    report = c.execute(ActionPlan((MovementIntent((MovementSegment('east', 1),), False, ''),)))
    before = deepcopy(c.narration_context(report=report))
    state, budget, resources = c.session.state, c.session.budget, deepcopy(c.session.encounter.states)
    c.extend_history([
        DialogueMessage.from_data({'role': 'narrator', 'on': 'Você está aqui.', 'off': 'Explicação registrada.'}),
        DialogueMessage.from_data({'role': 'player', 'on': '', 'off': 'Ataco em off; não execute.'}),
    ])
    assert c.session.state == state and c.session.budget == budget and c.session.encounter.states == resources
    current = c.narration_context()
    assert current['previous_execution']['execution_id'] == report.execution_id
    assert current['previous_execution']['execution'] == before['execution']
    assert current['history'][0]['off'] == 'Explicação registrada.'
    assert current['history'][1] == {'role': 'player', 'on': '', 'off': 'Ataco em off; não execute.'}
    assert c.interpretation_context()['recent_messages'] == [{'role': 'narrator', 'on': 'Você está aqui.'}]
    c.prepare('Olho ao redor. [Como funciona?]')
    assert c.interpretation_context()['recent_messages'][-1] == {'role': 'player', 'on': 'Olho ao redor.'}
    assert c.narration_context()['history'][-1]['off'] == 'Como funciona?'


def test_import_validates_entire_batch_before_changing_history():
    c = conversation()
    c.prepare('Olho.')
    initial = list(c.messages)

    def invalid_batch():
        yield DialogueMessage('narrator', Speech('Mensagem válida.'))
        yield DialogueMessage.from_data({'role': 'system', 'on': 'Não pode entrar.'})

    with pytest.raises(ValueError):
        c.extend_history(invalid_batch())
    assert c.messages == initial
    with pytest.raises(ValueError, match='DialogueMessage'):
        c.extend_history([{'role': 'narrator', 'on': 'Não passou pelo contrato.'}])
    assert c.messages == initial


def test_player_narration_and_failure_use_the_shared_validated_history_entry(monkeypatch):
    c = conversation()
    recorded = []
    extend = c.extend_history

    def observe(messages):
        batch = tuple(messages)
        recorded.extend(batch)
        extend(batch)

    monkeypatch.setattr(c, 'extend_history', observe)
    c.prepare('Olho. [Dúvida.]')
    c.finish(Speech('Uma grade.', 'Explicação.'), c.narration_context(initial=True))
    c.failure('Falha registrada.')
    assert recorded == c.messages
    assert [m.role for m in recorded] == ['player', 'narrator', 'narrator']
    assert recorded[0].speech.off == 'Dúvida.'
