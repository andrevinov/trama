"""Aquisição, segredo, desatualização e comunicação pelo motor compartilhado."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from trama.actions import ActionError
from trama.application.conversation import Conversation
from trama.application.intents import NarrativeIntent, ScenarioIntent, MovementIntent, DoorIntent
from trama.application.scenarios import build_session, load_session
from trama.application.world import WorldAction
from trama.application.world_resolution import WorldExecutor
from trama.knowledge import Claim, KnowledgeError
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]


def rooms(**changes):
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    data.update(changes)
    return build_session(data)


def say(session, actor='archivist', ids=('archivist:key-on-desk',), volume='normal'):
    return WorldExecutor(session).execute(WorldAction(actor, 'say', 'Na inspeção, vi a chave na mesa.',
                                                     volume=volume, memory_ids=ids))


def key_memories(session, owner):
    return tuple(m for m in session.knowledge.store.select(owner, entities=('archive_key',))
                 if m.claim.subject_id == 'archive_key')


def test_npc_memory_is_not_updated_from_hidden_world_truth():
    session = rooms(objects=[dict(id='archive_key', name='Chave do arquivo', position=[17, 2])])
    session.execute(NarrativeIntent('Olho ao redor.'))
    assert key_memories(session, 'archivist')[0].claim.value == 'position:13,3'
    assert session.scene.objects[0].position == Position(17, 2)
    assert not key_memories(session, 'apprentice') and not key_memories(session, 'player')


def test_speech_transmits_as_report_and_retains_the_original_reference():
    session = rooms()
    event = say(session)
    assert event['memory_ids'] == ['archivist:key-on-desk']
    assert set(event['heard_by']) == {'player', 'apprentice'}
    for owner in ('player', 'apprentice'):
        memory = key_memories(session, owner)[0]
        assert memory.source.kind == 'report' and memory.source.actor_id == 'archivist'
        assert memory.source.memory_id == 'archivist:key-on-desk'
        assert memory.claim.value == 'position:13,3'
        assert memory.when == 'Na última inspeção, antes desta conversa.'
    received = key_memories(session, 'apprentice')[0]
    relayed = say(session, 'apprentice', (received.id,))
    assert relayed['shared_memories'][0]['source']['actor_id'] == 'archivist'
    assert key_memories(session, 'player')[0].source.actor_id == 'apprentice'


def test_sharing_claim_does_not_transmit_the_speakers_private_context():
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    data['observers'][0]['knowledge'][0]['context'] = 'O arquivista planeja abandonar o aprendiz.'
    session = build_session(data)
    event = say(session)
    assert 'context' not in event['shared_memories'][0]
    assert 'abandonar' not in key_memories(session, 'player')[0].context
    assert 'abandonar' in session.knowledge.store.get('archivist', 'archivist:key-on-desk').context


def test_report_from_player_does_not_move_the_object_or_erase_prior_observation():
    session = rooms()
    session.execute(NarrativeIntent('Disseram que levaram a chave para a coluna 18, linha 3.', 'speak',
        claims=(Claim('archive_key', 'location', 'position:18,3'),)))
    memories = key_memories(session, 'archivist')
    assert {m.claim.value for m in memories} == {'position:13,3', 'position:18,3'}
    report = next(m for m in memories if m.source.kind == 'report')
    assert report.source.actor_id == 'player' and 'não confirmada' in report.context
    assert session.scene.objects[0].position == Position(12, 2)


@pytest.mark.parametrize('sleeping,deaf,far', [(True, False, False), (False, True, False), (False, False, True)])
def test_receiving_requires_consciousness_and_audible_distance(sleeping, deaf, far):
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    listener = data['observers'][1]
    listener['senses'] = {'sleeping': sleeping, 'can_hear': not deaf, 'hearing_range_meters': 0 if far else 21}
    session = build_session(data)
    event = say(session)
    assert 'apprentice' not in event['heard_by']
    assert not key_memories(session, 'apprentice')


@pytest.mark.parametrize('ids,private', [(('archivist:not-owned',), False), (('archivist:key-on-desk',), True)])
def test_unknown_or_private_references_are_rejected_before_transmission(ids, private):
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    data['observers'][0]['knowledge'][0]['shareable'] = not private
    session = build_session(data)
    before = session.knowledge.store.export()
    with pytest.raises(ActionError):
        say(session, ids=ids)
    assert session.knowledge.store.export() == before
    assert not session.drain_world_events()


def test_foreign_owner_cannot_reuse_a_memory_reference():
    session = rooms()
    with pytest.raises(ActionError, match='não possui'):
        say(session, 'apprentice')


def test_observation_uses_actual_line_of_sight_and_updates_only_the_witness():
    session = rooms()
    session.knowledge.observe(Claim('archive_key', 'location', 'position:18,3'), 'Vi a chave no leste.',
                              Position(17, 2), context='Chave movida no leste.')
    assert key_memories(session, 'archivist')[0].claim.value == 'position:13,3'
    session.execute(MovementIntent((), False, '', 'door'))
    session.execute(DoorIntent('open', 'door'))
    session.execute(NarrativeIntent('Olho para a sala leste.'))
    assert key_memories(session, 'player')[0].source.kind == 'observation'


def test_contexts_select_memories_and_do_not_expose_npc_memories_to_player_or_narrator():
    session = rooms()
    conversation = Conversation(session)
    conversation.prepare('Arquivista, onde viu a chave?')
    interpreter = conversation.interpretation_context()
    assert interpreter['knowledge'] == [] and 'world' not in interpreter
    world = conversation.world_context()
    assert any(m['id'] == 'archivist:key-on-desk' for a in world['world']['knowledge']['actors'] for m in a['memories'])
    narrator = conversation.narration_context(initial=True)
    assert narrator['knowledge'] == [] and 'knowledge' not in narrator['world']
    say(session)
    assert conversation.interpretation_context()['knowledge']


def test_off_question_can_retrieve_own_memories_without_changing_state():
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    data['observers'][0]['knowledge'][0]['entities'] = ['east']
    session = build_session(data)
    say(session)
    conversation = Conversation(session)
    before = session.knowledge.store.export()
    context = conversation.narration_context(conversation.prepare('[Onde me disseram que estava a chave?]'))
    assert any(m['claim']['subject_id'] == 'archive_key' for m in context['knowledge'])
    assert not context['allow_on'] and 'knowledge' not in context['world']
    assert session.knowledge.store.export() == before


def test_reset_restores_authored_memories_and_discards_learned_reports():
    session = rooms()
    original = deepcopy(session.knowledge.store.export())
    say(session)
    session.reset()
    assert session.knowledge.store.export() == original


def test_world_projection_bounds_the_number_of_npcs_and_memory_content():
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    occupied = {tuple(data['start']), *(tuple(o['position']) for o in data['observers'])}
    positions = [(x, y) for y in range(1, 4) for x in range(1, 10) if (x, y) not in occupied]
    seed = data['observers'][0]['knowledge'][0]
    for n, p in enumerate(positions[:12]):
        records = []
        for k in range(10):
            record = deepcopy(seed)
            record['id'] = f'record-{k}'
            record['claim']['subject_id'] = f'item-{k}'
            records.append(record)
        data['observers'].append(dict(id=f'npc-{n}', name=f'Leitor {n}', position=list(p), knowledge=records))
    session = build_session(data)
    context = session.interpreter_context(knowledge_query='Onde está a chave?')['world']['knowledge']
    assert len(context['actors']) == 8
    assert all(len(actor['memories']) <= 6 for actor in context['actors'])
    content = sum(len(json.dumps(m, ensure_ascii=False)) for a in context['actors'] for m in a['memories'])
    assert content <= 9000
    assert len(session.knowledge.store.export()['memories']) > sum(len(a['memories']) for a in context['actors'])


def test_knowledge_loader_refuses_a_plain_string_list():
    data = json.loads((ROOT / 'src/trama/scenarios/knowledge_rooms.json').read_text())
    data['observers'][0]['knowledge'] = ['a chave está na mesa']
    with pytest.raises((KnowledgeError, ValueError)):
        build_session(data)


def test_prisoner_shares_a_memory_instead_of_an_unconditional_world_fact():
    session = load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json')
    session.execute(MovementIntent((), False, '', 'corridor'))
    session.execute(MovementIntent((), False, '', 'gate_2'))
    events = session.drain_world_events()
    speech = next(e for e in events if e['operation'] == 'say' and e['actor_id'] == 'prisoner')
    assert speech['memory_ids'] == ['prisoner:key-custodian']
    assert 'É o guarda quem fica com a chave' in speech['text'] and 'Não sei onde' in speech['text']
    assert speech['shared_memories'][0]['claim'] == dict(subject_id='cell_key', predicate='custodian', value='guard_1')
    item = next(o for o in session.interpreter_context()['visible_objects'] if o['id'] == 'cell_key')
    assert item['position'] is None and not item['visible']
    assert 'cell_key' in session.dungeon.discovered and 'cell_key' not in session.dungeon.inventory


def test_prisoner_without_that_memory_cannot_announce_the_key():
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['observers'][0]['knowledge'] = []
    session = build_session(data)
    session.execute(MovementIntent((), False, '', 'corridor'))
    session.execute(MovementIntent((), False, '', 'gate_2'))
    speech = next(e for e in session.drain_world_events() if e['operation'] == 'say' and e['actor_id'] == 'prisoner')
    assert speech['memory_ids'] == [] and 'chave' not in speech['text'].casefold()
    assert 'cell_key' not in session.dungeon.discovered


def test_unheard_prisoner_speech_does_not_discover_the_item_for_player():
    session = load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json')
    session.knowledge.communicate('prisoner', 'Vi a chave.', session.prisoner_position, 'quiet',
                                  memory_ids=('prisoner:key-custodian',))
    assert 'cell_key' not in session.dungeon.discovered


def test_taking_key_without_witnesses_does_not_update_the_prisoner_memory():
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [11, 2]
    data['creatures'][0]['senses'] = {'can_see': False, 'can_hear': False}
    session = build_session(data)
    session.execute(NarrativeIntent('Olho a mesa.'))
    session.execute(ScenarioIntent('take', 'cell_key'))
    assert 'cell_key' in session.dungeon.inventory
    memories = session.knowledge.store.select('prisoner', entities=('cell_key',))
    assert len(memories) == 1 and memories[0].claim.value == 'guard_1'
    assert memories[0].claim.predicate == 'custodian'
    assert all(m.claim.value != 'carried:player' for m in memories)


def test_old_report_does_not_reveal_actual_hidden_item_position_in_context_or_path():
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    # Variante histórica intencional: este teste requer uma localização antiga,
    # enquanto o prisioneiro padrão conhece somente quem fica com a chave.
    memory = data['observers'][0]['knowledge'][0]
    memory['id'] = 'key-last-seen'
    memory['claim'] = dict(subject_id='cell_key', predicate='location', value='position:12,3')
    memory['text'] = 'Antes da prisão, vi a chave na mesa da Sala dos Guardas.'
    next(i for i in data['dungeon']['items'] if i['id'] == 'cell_key')['position'] = [16, 2]
    session = build_session(data)
    session.execute(MovementIntent((), False, '', 'corridor'))
    session.execute(MovementIntent((), False, '', 'gate_2'))
    item = next(o for o in session.interpreter_context()['visible_objects'] if o['id'] == 'cell_key')
    assert item['position'] == [12, 3] and not item['visible']
    assert session.item_positions['cell_key'] == Position(16, 2)
    requirement = session.spatial_requirement(ScenarioIntent('take', 'cell_key'))
    assert requirement and max(p.x for p in requirement.cells) <= 12


def test_guards_order_suspicion_and_fear_are_distinct_contextual_memories():
    session = load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json')
    records = {m.id: m for m in session.initial_memories if m.owner_id == 'guard_1'}
    order = records['guard_1:superior-imprisoned-prisoner']
    suspicion = records['guard_1:possible-lords-son']
    fear = records['guard_1:fear-of-reprisals']
    assert order.source.kind == 'observation' and order.claim.value == 'guard_superior'
    assert suspicion.source.kind == 'inference' and suspicion.claim.predicate == 'possible_parentage'
    assert suspicion.claim.subject_id == order.claim.subject_id == 'unidentified_prisoner'
    assert suspicion.claim.subject_id not in {'player', 'prisoner'}
    assert 'não tenho confirmação' in suspicion.text
    assert fear.source.kind == 'inference' and fear.claim.predicate == 'fears_if_suspicion_confirmed'
    assert 'Se esse prisioneiro for realmente' in fear.text
    assert 'não uma ameaça já recebida' in fear.context


def test_guards_fear_is_available_to_world_without_becoming_player_knowledge():
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [11, 2]
    session = build_session(data)
    conversation = Conversation(session)
    conversation.prepare('Guarda, esse prisioneiro é filho de um lorde? Você teme represálias?')
    selected = next(a['memories'] for a in conversation.world_context()['world']['knowledge']['actors'] if a['actor_id'] == 'guard_1')
    assert {'guard_1:possible-lords-son', 'guard_1:fear-of-reprisals'} <= {m['id'] for m in selected}
    assert conversation.interpretation_context()['knowledge'] == []
    assert conversation.narration_context(initial=True)['knowledge'] == []


def test_reset_preserves_the_updated_dungeon_npc_memories():
    session = load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json')
    initial = session.knowledge.store.export()
    session.reset()
    assert session.knowledge.store.export() == initial


def test_sleight_of_hand_success_does_not_give_guard_omniscient_knowledge(dice):
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [11, 2]
    session = build_session(data, roller=dice(20))
    session.execute(ScenarioIntent('take', 'cell_key'))
    assert 'cell_key' in session.dungeon.inventory
    assert all(m.claim.value != 'carried:player' for m in session.knowledge.store.select('guard_1', entities=('cell_key',)))


def test_learning_that_an_item_exists_does_not_reveal_a_location():
    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['creatures'][0]['senses'] = {'can_see': False, 'can_hear': False}
    memory = data['observers'][0]['knowledge'][0]
    memory['claim'] = dict(subject_id='cell_key', predicate='opens', value='gate_2')
    memory['text'] = 'Existe uma chave que abre a grade.'
    session = build_session(data)
    session.execute(MovementIntent((), False, '', 'corridor'))
    session.execute(MovementIntent((), False, '', 'gate_2'))
    item = next(o for o in session.interpreter_context()['visible_objects'] if o['id'] == 'cell_key')
    assert item['position'] is None and not item['visible']
    with pytest.raises(ActionError, match='não uma localização'):
        session.validate_preparation(ScenarioIntent('take', 'cell_key'))
