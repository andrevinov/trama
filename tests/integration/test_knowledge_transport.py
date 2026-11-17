"""Novos campos das intenções e planos reais, sem consultar um modelo."""

import json

import pytest

from trama.application.intents import NarrativeIntent
from trama.application.world import WorldAction, WorldError
from trama.infrastructure.openai_intent_interpreter import parse_intent
from trama.infrastructure.openai_world_director import parse_world_plan
from trama.knowledge import Claim


def test_interpreter_parses_report_without_granting_world_effects():
    intent = parse_intent(json.dumps(dict(operation='speak', text='Disseram que levaram a chave.', volume='normal',
        claims=[dict(subject_id='archive_key', predicate='location', value='position:18,3')])))
    assert intent.claims == (Claim('archive_key', 'location', 'position:18,3'),)


def test_world_director_parses_memory_references():
    action = dict(actor_id='archivist', operation='say', text='Vi a chave ontem.', target_id=None, destination=None,
                  weapon='unarmed', influence=None, volume='normal', memory_ids=['archivist:key-on-desk'])
    plan = parse_world_plan(json.dumps(dict(reactions=[dict(step_index=0, after_squares=None, actions=[action],
                                                          interrupt=False, reason='', check=None)])))
    assert plan.reactions[0].actions[0].memory_ids == ('archivist:key-on-desk',)


def test_legacy_speech_without_new_fields_remains_readable():
    assert parse_intent(json.dumps(dict(operation='speak', text='Olá.'))).claims == ()


@pytest.mark.parametrize('operation', ['look', 'wait'])
def test_look_and_wait_cannot_transmit_proposed_claims(operation):
    with pytest.raises(ValueError):
        NarrativeIntent('Disseram que levaram a chave.', operation, claims=(Claim('key', 'location', 'hall'),))


@pytest.mark.parametrize('ids', [('id', 'id'), ('',), tuple(str(n) for n in range(7))])
def test_world_reference_validation_rejects_invalid_lists(ids):
    with pytest.raises(WorldError):
        WorldAction('archivist', 'say', 'Algo.', memory_ids=ids)


def test_nonspeech_world_action_cannot_disclose_memories():
    with pytest.raises(WorldError):
        WorldAction('archivist', 'wait', 'Espera.', memory_ids=('archivist:key-on-desk',))
