"""Crenças, proveniência, seleção limitada e serialização sem serviços externos."""

from dataclasses import replace
import json

import pytest

from trama.knowledge import Claim, KnowledgeError, KnowledgeStore, Memory, MemorySource, memory_from_data


def memory(*, id='npc:old-key', owner='npc', value='desk', kind='observation', **changes):
    return Memory(id, owner, Claim('key', 'location', value), 'Vi a chave na mesa.',
                  MemorySource(kind, 'arrival', 'friend' if kind == 'report' else None),
                  'Ontem.', 'O guarda acabava de fechar as celas.', ('guard', 'prison'), ('escape',), **changes)


def test_initial_memory_has_context_source_and_an_owner():
    record = memory().data()
    assert record['claim'] == {'subject_id': 'key', 'predicate': 'location', 'value': 'desk'}
    assert record['source']['kind'] == 'observation' and record['when'] == 'Ontem.'
    assert memory_from_data(json.loads(json.dumps(record))) == memory()
    with pytest.raises(KnowledgeError, match='não possui'):
        KnowledgeStore((memory(),)).get('other', 'npc:old-key')


@pytest.mark.parametrize('changes', [{'text': ''}, {'when': ''}, {'context': ''}, {'shareable': 1}, {'acquired_at': True}])
def test_memory_requires_valid_context_and_metadata(changes):
    with pytest.raises(KnowledgeError):
        replace(memory(), **changes)


def test_new_observation_supersedes_belief_without_deleting_its_history():
    store = KnowledgeStore((memory(),))
    new = store.learn('npc', Claim('key', 'location', 'drawer'), 'Vejo a chave na gaveta.',
                      MemorySource('observation', 'opened-drawer'), when='Agora.', context='A gaveta foi aberta.')
    assert store.select('npc', entities=('key',)) == (new,)
    assert store.get('npc', 'npc:old-key').claim.value == 'desk'
    assert store.export()['superseded'] == {'npc:old-key': new.id}


def test_conflicting_report_preserves_observation_and_names_the_source():
    store = KnowledgeStore((memory(),))
    report = store.learn('npc', Claim('key', 'location', 'player'), 'A chave está comigo.',
                         MemorySource('report', 'speech-1', 'player'), when='Agora.', context='O jogador afirmou isso.')
    records = store.select('npc', entities=('key',))
    assert records == (report, memory())
    assert report.source.actor_id == 'player' and not store.export()['superseded']


def test_direct_reconfirmation_supersedes_a_conflicting_report():
    store = KnowledgeStore((memory(),))
    store.learn('npc', Claim('key', 'location', 'drawer'), 'Disseram que está na gaveta.',
                MemorySource('report', 'rumor', 'player'), when='Agora.', context='Um rumor.')
    confirmed = store.learn('npc', Claim('key', 'location', 'desk'), 'Olhei de novo: está na mesa.',
                MemorySource('observation', 'look-again'), when='Depois do rumor.', context='Inspeção direta.')
    assert confirmed.id != memory().id
    assert store.select('npc', entities=('key',)) == (confirmed,)
    assert len(store.export()['memories']) == 3


def test_repeated_observation_is_deduplicated_but_new_report_has_a_new_moment():
    store = KnowledgeStore((memory(),))
    same = store.learn('npc', memory().claim, 'Ainda vejo a chave.', MemorySource('observation', 'look-again'),
                       when='Agora.', context='Olha novamente.')
    assert same == memory() and len(store.export()['memories']) == 1
    reports = [store.learn('npc', Claim('key', 'location', 'drawer'), 'Disseram gaveta.',
               MemorySource('report', f'speech-{n}', 'player'), when='Agora.', context='Conversa.') for n in range(2)]
    assert reports[0].acquired_at < reports[1].acquired_at


def test_an_observed_action_can_refresh_attribution_without_repeating_passive_observations():
    store = KnowledgeStore((memory(),))
    action = store.learn('npc', memory().claim, 'Vi o jogador colocar a chave.',
        MemorySource('observation', 'action', 'player'), when='Agora.',
        context='Ação observada com autoria.', replace_existing=True)
    assert action.id != memory().id and action.acquired_at > memory().acquired_at
    assert store.active('npc') == (action,)
    again = store.learn('npc', memory().claim, 'A chave continua ali.',
        MemorySource('observation', 'look-again'), when='Depois.', context='Estado ainda visível.')
    assert again == action
    assert len(store.export()['memories']) == 2


def test_indexes_select_only_relevant_owner_and_respect_count_and_content_budget():
    store = KnowledgeStore((memory(), memory(id='other:secret', owner='other')))
    for n in range(40):
        store.learn('npc', Claim(f'stone-{n}', 'color', 'gray'), 'Pedra cinzenta.', MemorySource('observation', str(n)),
                    when='Agora.', context='Uma pedreira.', topics=('rocks',))
    assert store.select('npc', query='CHÁVE') == (memory(),)
    assert store.select('npc', topics=('escape',)) == (memory(),)
    assert store.select('npc', entities=('key',), limit=0) == ()
    assert store.select('npc', entities=('key',), max_chars=1) == ()
    selected = store.select('npc', topics=('rocks',), limit=3, max_chars=1400)
    assert 0 < len(selected) <= 3
    assert sum(len(json.dumps(m.data(), ensure_ascii=False)) for m in selected) <= 1400


def test_export_restore_keeps_provenance_revisions_and_next_identity():
    store = KnowledgeStore((memory(),))
    store.learn('npc', Claim('key', 'location', 'drawer'), 'Vejo gaveta.', MemorySource('observation', 'new'),
                when='Agora.', context='Nova observação.')
    saved = json.loads(json.dumps(store.export()))
    restored = KnowledgeStore.restore(saved)
    assert restored.export() == saved
    assert restored.select('npc', entities=('key',)) == store.select('npc', entities=('key',))
    restored.learn('npc', Claim('key', 'location', 'hall'), 'No salão.', MemorySource('report', 'new', 'friend'),
                   when='Depois.', context='Outro relato.')
    assert len(restored.export()['memories']) == 3 and len(store.export()['memories']) == 2


def test_generated_identity_does_not_collide_with_an_authored_initial_memory():
    store = KnowledgeStore((memory(id='npc:memory:1'),))
    learned = store.learn('npc', Claim('door', 'open', 'true'), 'A porta abriu.', MemorySource('observation', 'open'),
                          when='Agora.', context='O guarda abriu a porta.')
    assert learned.id != 'npc:memory:1' and store.get('npc', 'npc:memory:1')


def test_restore_rejects_a_cycle_in_superseded_beliefs():
    data = KnowledgeStore((memory(),)).export()
    data['superseded'] = {'npc:old-key': 'npc:old-key'}
    with pytest.raises(KnowledgeError, match='Ciclo'):
        KnowledgeStore.restore(data)


@pytest.mark.parametrize('field', ['claim', 'source'])
def test_strings_alone_are_not_a_valid_memory(field):
    data = memory().data()
    data[field] = 'a chave está na mesa'
    with pytest.raises(KnowledgeError):
        memory_from_data(data)
