"""Regressão da resposta real e agrupamento determinístico de evidências sociais."""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.situations import load_situation
from trama.bootstrap import open_situation
from trama.infrastructure.openai_world_director import parse_world_plan
from trama.knowledge import Claim, Memory, MemorySource
from trama.social import (DispositionAssessment, Interest, MemoryEffect, Persona, PersonaEffect,
                          SocialError, SocialProfile, evaluate_disposition)

ROOT = Path(__file__).resolve().parents[2]
RAW = (ROOT / 'tests/fixtures/social_memory_links/world_response.json').read_text()
LIVE = runpy.run_path(str(ROOT / 'tests/live/test_memory_evidence_links_live.py'))


def sample(effects, *, source='report'):
    claim = Claim('player', 'parentage', 'noble_heir')
    interests = tuple(Interest(f'interest_{i}', 'Interesse afetado.', 1, evidence_predicates=('parentage',))
                      for i in range(len(effects)))
    profile = SocialProfile('neutral', Persona('Guarda', 'Guarda', 'Interesses diferentes.', interests))
    value = DispositionAssessment('listen', 'player', 'Ouvir sem soltar.', 0, 0, 'Neutro.',
        tuple(PersonaEffect(i.id, 0, 'Não altera a parcela base.') for i in interests),
        tuple(MemoryEffect(claim, i.id, effect, f'Consequência {i.id}.') for i, effect in zip(interests, effects)),
        'Vou ouvir.', 'Não.', ('Manter custódia.',))
    memory = Memory('guard:noble', 'guard', claim, 'Diz ser herdeiro.', MemorySource(source, 'event', 'player'),
                    'Agora.', 'Não confirmado.')
    return profile, value, memory


@pytest.mark.parametrize('effects,expected', [((1, 1), 1), ((-1, -1), -1), ((1, -1), 0),
    ((1, 0), 1), ((0, 0), 0), ((1, -1, -1), -1)])
@pytest.mark.parametrize('source,weight', [('report', 1), ('observation', 2)])
def test_each_fact_contributes_at_most_once_even_with_many_interests(effects, expected, source, weight):
    profile, value, memory = sample(effects, source=source)
    result = evaluate_disposition(profile, value, (memory,))
    contribution, = result['memory_effects']
    assert contribution['effect'] == expected
    assert contribution['score'] == result['components']['memories'] == expected * weight
    assert len(contribution['impacts']) == len(effects)
    assert {e['reason'] for e in contribution['impacts']} == {e.reason for e in value.memory_effects}


def test_order_does_not_change_how_mixed_consequences_are_scored():
    profile, value, memory = sample((1, -1, 1))
    for links in permutations(value.memory_effects):
        result = evaluate_disposition(profile, replace(value, memory_effects=links), (memory,))
        assert result['components']['memories'] == 1


def test_distinct_facts_still_keep_the_global_memory_cap():
    profile, value, memory = sample((1, 1))
    memories = tuple(replace(memory, id=f'guard:{i}', claim=replace(memory.claim, subject_id=f'person_{i}')) for i in range(3))
    links = tuple(replace(e, claim=m.claim) for m in memories for e in value.memory_effects)
    result = evaluate_disposition(profile, replace(value, memory_effects=links), memories)
    assert len(result['memory_effects']) == 3
    assert result['components']['memories'] == 3


def test_each_link_must_still_reference_a_known_interest_and_relevant_fact():
    profile, value, memory = sample((1, 1))
    with pytest.raises(SocialError, match='não conhece'):
        evaluate_disposition(profile, value, ())
    irrelevant = replace(profile.persona.interests[1], evidence_predicates=())
    profile = replace(profile, persona=replace(profile.persona, interests=(profile.persona.interests[0], irrelevant)))
    with pytest.raises(SocialError, match='sem vínculo'):
        evaluate_disposition(profile, value, (memory,))


def test_repeating_same_fact_and_same_interest_has_a_specific_diagnostic():
    _, value, _ = sample((1,))
    with pytest.raises(SocialError, match='mesmo fato para o mesmo interesse'):
        replace(value, memory_effects=value.memory_effects * 2)


def test_real_response_is_parsed_without_erasing_the_two_parentage_links():
    request = parse_world_plan(RAW).reactions[0].actions[0].influence
    links = [e for e in request.assessment.memory_effects if e.claim.predicate == 'parentage']
    assert len(links) == 2 and {e.interest_id for e in links} == {'safety', 'livelihood'}


def test_invalid_pair_is_explained_in_the_public_transport_error():
    value = json.loads(RAW)
    effects = value['reactions'][0]['actions'][0]['influence']['assessment']['memory_effects']
    effects.append(deepcopy(effects[-1]))
    with pytest.raises(ValueError, match='mesmo fato para o mesmo interesse'):
        parse_world_plan(json.dumps(value))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_actual_response_and_live_criteria_through_shared_runner(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        frozen = parse_world_plan(RAW)
        original = frozen.reactions[0].actions[0]
        claims = tuple(dict.fromkeys(e.claim for e in original.influence.assessment.memory_effects))
        request = replace(original.influence, assessment=replace(original.influence.assessment, goal=case['goal']))
        plan = replace(frozen, reactions=(replace(frozen.reactions[0], actions=(replace(original, influence=request),)),))
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt, 'speak', volume='loud', claims=claims),)), prompt))
        game.flow.world_director = SimpleNamespace(decide=lambda context: plan)
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='O guarda responde à distância.'))
        original_state = before = LIVE['snapshot'](game, roller)
        for index, prompt in enumerate(case['messages']):
            result = game.runner.submit(prompt)
            after = LIVE['snapshot'](game, roller)
            assert not LIVE['evaluate'](case, index, before, after, result), result.error or result.report.context()
            assert json.loads(json.dumps(LIVE['record'](result, game, roller)))['requests']
            event = next(e for e in result.report.world_events if e['operation'] == 'influence')
            # Resposta do log: promessa + nobreza valem 2, não 3 pontos.
            assert event['disposition']['components']['memories'] == 2
            assert event['disposition']['total'] == 1 and event['dice'] == [20]
            group = next(g for g in event['disposition']['memory_effects'] if g['claim']['predicate'] == 'parentage')
            assert len(group['impacts']) == 2 and group['score'] == 1
            broken = deepcopy(result)
            contribution = next(e for e in broken.report.world_events if e['operation'] == 'influence')['disposition']['memory_effects'][0]
            contribution['score'] = 99
            assert LIVE['evaluate'](case, index, before, after, broken)
            before = after
        assert game.runner.reset().status == 'completed'
        restored = LIVE['snapshot'](game, roller)
        # O reinício executa de novo a preparação e gera ids de observação novos.
        for state in (restored, original_state):
            for memory in state['knowledge']['memories']:
                memory['source'].pop('event_id', None)
        assert restored == original_state
