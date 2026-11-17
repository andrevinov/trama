"""Pontuação social e alinhamentos: critérios fixos, sem IA nem dados."""

from dataclasses import replace

import pytest

from trama.knowledge import Claim, Memory, MemorySource
from trama.social import (ALIGNMENTS, DispositionAssessment, Interest, MemoryEffect, Persona, PersonaEffect,
                          SocialError, SocialProfile, evaluate_disposition, profile_from_data)


def profile(alignment='neutral', weight=2):
    return SocialProfile(alignment, Persona('Guarda', 'Guarda', 'Quer compreender a situação.',
        (Interest('understanding', 'Ouvir uma explicação.', weight, evidence_predicates=('identity',)),)))


def assessment(effect=1, **changes):
    value = DispositionAssessment('listen', 'player', 'Ouvir brevemente sem soltar.', 0, 0, 'Pedido neutro.',
        (PersonaEffect('understanding', effect, 'Ouvir ajuda a compreender.'),), (),
        'Fique onde está e explique. Você continua sob custódia.', 'Não. Volte à sua cela.', ('Ficar onde está.',))
    return replace(value, **changes)


@pytest.mark.parametrize('alignment,score', [
    ('lawful_good', 4), ('neutral_good', 3), ('chaotic_good', 2), ('lawful_neutral', 3),
    ('neutral', 2), ('chaotic_neutral', 1), ('lawful_evil', 2), ('neutral_evil', 1), ('chaotic_evil', 0),
    ('unaligned', 2),
])
def test_alignment_is_a_limited_two_axis_contribution(alignment, score):
    result = evaluate_disposition(profile(alignment), assessment(order=1, morality=1), ())
    assert result['total'] == score
    assert result['components']['alignment'] == score - 2


@pytest.mark.parametrize('alignment', list(ALIGNMENTS))
def test_alignment_does_not_force_all_members_to_make_the_same_choice(alignment):
    helpful = evaluate_disposition(profile(alignment, 4), assessment(), ())
    hostile = evaluate_disposition(profile(alignment, 4), assessment(-1), ())
    assert helpful['willingness'] == 'willing' and hostile['willingness'] == 'unwilling'


@pytest.mark.parametrize('weight,effect,expected', [(3,1,'willing'),(2,1,'hesitant'),(3,-1,'unwilling'),(2,-1,'hesitant')])
def test_thresholds_classify_without_random_rolls(weight, effect, expected):
    assert evaluate_disposition(profile(weight=weight), assessment(effect), ())['willingness'] == expected


def test_relevant_report_changes_points_without_becoming_confirmed_truth():
    memory = Memory('npc:report', 'npc', Claim('player', 'identity', 'noble_heir'), 'Diz ser herdeiro.',
                    MemorySource('report', 'speech', 'player'), 'Agora.', 'Afirmação não confirmada.')
    value = assessment(memory_effects=(MemoryEffect(memory.claim, 'understanding', 1, 'Alegação merece escuta.'),))
    result = evaluate_disposition(profile(), value, (memory,))
    assert result['total'] == 3 and result['willingness'] == 'willing'
    assert result['memory_effects'][0]['source']['kind'] == 'report'
    assert result['components'] == dict(alignment=0, persona=2, memories=1)


def test_unknown_and_irrelevant_memories_cannot_add_points():
    effect = MemoryEffect(Claim('player', 'clothing', 'blue'), 'understanding', 1, 'Tentativa irrelevante.')
    value = assessment(memory_effects=(effect,))
    with pytest.raises(SocialError, match='não conhece'):
        evaluate_disposition(profile(), value, ())
    memory = Memory('npc:color', 'npc', effect.claim, 'Roupa azul.', MemorySource('observation','look'), 'Agora.', 'Roupa.')
    with pytest.raises(SocialError, match='sem vínculo'):
        evaluate_disposition(profile(), value, (memory,))


def test_persona_requires_each_real_interest_once():
    with pytest.raises(SocialError, match='cada interesse'):
        evaluate_disposition(profile(), assessment(persona_effects=()), ())
    with pytest.raises(SocialError):
        assessment(persona_effects=(PersonaEffect('understanding',1,'Um.'),PersonaEffect('understanding',1,'Dois.')))


def test_profile_data_preserves_job_family_and_evidence_anchors():
    result = profile_from_data(dict(alignment='lawful_neutral', persona=dict(name='Rui', role='Guarda',
        background='Sustenta a família com o salário.', interests=[dict(id='livelihood', description='Preservar emprego.',
        weight=3, evidence_topics=['família'], evidence_predicates=['identity'])])), 'NPC')
    assert result.persona.role == 'Guarda' and result.persona.interests[0].weight == 3
    with pytest.raises(SocialError):
        profile_from_data(dict(alignment='invented'), 'NPC')


def test_many_memories_cannot_override_persona_without_a_limit():
    memories = tuple(Memory(f'npc:{n}', 'npc', Claim(f'person-{n}', 'identity', 'heir'), 'Alegação.',
        MemorySource('observation', str(n)), 'Agora.', 'Observação.') for n in range(6))
    value = assessment(-1, memory_effects=tuple(MemoryEffect(m.claim,'understanding',1,'Importa.') for m in memories))
    result = evaluate_disposition(profile(weight=4), value, memories)
    assert result['components']['memories'] == 3 and result['total'] == -1


@pytest.mark.parametrize('field,value', [('order',True),('morality',2),('goal','invented'),('conditions',('same','same'))])
def test_assessment_contract_rejects_ambiguous_structures(field,value):
    with pytest.raises(SocialError):
        assessment(**{field:value})
