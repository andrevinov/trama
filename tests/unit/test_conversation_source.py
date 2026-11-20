"""Tolerância de superfície, sem equivalência semântica ou alteração de conteúdo."""

import pytest

from trama.conversation_state import (ConversationUpdate, ConversationPoint, ProposalUpdate,
                                      ProposalTerm, ConversationStateError)


@pytest.mark.parametrize('fragment,source', [
    ('Queremos paz.', '"Queremos paz", falo.'),
    ('Queremos paz', '“Queremos paz.”'),
    ('Queremos  paz.', 'Queremos\n paz'),
    ('“Não aceito.”', '"Não aceito."'),
    ('Condição: fiscalização.', 'Condição: fiscalizac\u0327a\u0303o.'),
    ('Pago 30.', 'Pago 30'),
])
def test_source_accepts_only_documented_surface_variations(fragment, source):
    ConversationUpdate(points=(ConversationPoint('statement', fragment),)).validate_source(
        source, actor_id='player', player_id='player')


@pytest.mark.parametrize('fragment,source', [
    ('Eu aceito.', 'Eu não aceito.'),
    ('Eu não aceito.', 'Eu aceito.'),
    ('Trégua de 30 dias.', 'Trégua de 300 dias.'),
    ('Trégua de trinta dias.', 'Trégua de trezentos dias.'),
    ('Pago 3.', 'Pago 3,5.'),
    ('Pago 3.', 'Pago 3.500.'),
    ('5 dias.', '3,5 dias.'),
    ('aceito.', 'desaceito.'),
    ('Não aceito.', 'Não, aceito.'),
    ('Aceito.', 'Aceito?'),
    ('Aceito.', 'Aceito!'),
    ('Aceito.', 'Aceito...'),
    ('Aceito.', 'Aceito…'),
    ('Recuo se houver fiscalização.', 'Recuo sem fiscalização.'),
    ('Devolver a Bavária.', 'Devolver a ponte.'),
])
def test_source_does_not_discard_words_numbers_conditions_or_significant_punctuation(fragment, source):
    with pytest.raises(ConversationStateError, match='Ponto 1 da conversa'):
        ConversationUpdate(points=(ConversationPoint('statement', fragment),)).validate_source(
            source, actor_id='player', player_id='player')


@pytest.mark.parametrize('field', ['point', 'term', 'reason', 'boundary'])
def test_all_cited_fields_use_the_same_surface_contract(field):
    if field == 'point':
        update = ConversationUpdate(points=(ConversationPoint('statement', 'Não aceito.'),))
    elif field == 'term':
        update = ConversationUpdate(proposal=ProposalUpdate('offer', terms=(ProposalTerm(None, 'condition', 'Não aceito.'),)))
    elif field == 'reason':
        update = ConversationUpdate(status='closed', reason='Não aceito.')
    else:
        update = ConversationUpdate(target_ids=('npc',), romance_boundary='declined', boundary_text='Não aceito.')
    update.validate_source('“Não aceito”, digo.', actor_id='player', player_id='player')
    with pytest.raises(ConversationStateError):
        update.validate_source('“Aceito”, digo.', actor_id='player', player_id='player')


def test_source_error_identifies_field_fragment_and_comparison_source():
    update = ConversationUpdate(points=(ConversationPoint('statement', 'Olá.'),
        ConversationPoint('request', 'Devolva a Bavária.')))
    with pytest.raises(ConversationStateError) as error:
        update.validate_source('Olá.', actor_id='player', player_id='player', source_label='mensagem original do jogador')
    assert all(t in str(error.value) for t in ('Ponto 2 da conversa', 'mensagem original do jogador', 'Devolva a Bavária.'))
