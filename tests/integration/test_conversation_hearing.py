"""Margem de conversa com percepção mútua, sem ampliar ruídos ou sussurros."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.parley import InfluenceRequest
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_game
from trama.knowledge import Claim
from trama.perception import Noise
from trama.social import DispositionAssessment, MemoryEffect, PersonaEffect
from trama.spatial import Position


def corridor(*, guard_x=16, senses=None, dark=(), observers=()):
    return build_session(dict(width=40, height=5, start=[1, 2], player=dict(armor='none'),
        areas=[dict(id='hall', name='Salão', x=0, y=0, width=40, height=5)], passages=[],
        dark=list(dark), creatures=[dict(id='guard', name='Guarda', position=[guard_x, 2],
        senses=senses or {})], observers=list(observers)))


@pytest.mark.parametrize('guard_x,heard', [(15, True), (16, True), (22, True), (23, False)])
def test_normal_conversation_has_a_finite_fifty_percent_margin(guard_x, heard):
    session = corridor(guard_x=guard_x)
    result = session.execute(NarrativeIntent('Por favor, me ouça.', 'speak'))
    assert ('guard' in result.event['heard_by']) is heard


@pytest.mark.parametrize('speech,volume,heard', [
    (False, 'normal', False), (True, 'normal', True), (True, 'quiet', False), (True, 'loud', True)])
def test_only_normal_speech_receives_the_margin(speech, volume, heard):
    session = corridor()
    assert session.perception.hears(session.creatures[0], Noise('player', session.state.position,
        volume, speech=speech)) is heard


@pytest.mark.parametrize('senses,dark', [
    ({'can_see': False}, ()),
    ({'sight_range_meters': 3}, ()),
    ({'can_hear': False}, ()),
    ({'hearing_range_meters': 0}, ()),
    ({'sleeping': True}, ()),
    ({}, ([16, 2],)),
    ({}, ([1, 2],)),
])
def test_both_characters_must_currently_perceive_each_other(senses, dark):
    session = corridor(senses=senses, dark=dark)
    result = session.execute(NarrativeIntent('Me ouça.', 'speak'))
    assert 'guard' not in result.event['heard_by']


def test_remembering_an_earlier_sighting_does_not_extend_hearing():
    session = corridor()
    session.perceive()
    assert session.perception.awareness['guard']['player']['level'] == 'seen'
    # Uma condição de cena atual pode remover a visão sem apagar a lembrança.
    from dataclasses import replace
    session.creatures = tuple(replace(c, senses=replace(c.senses, can_see=False)) for c in session.creatures)
    result = session.execute(NarrativeIntent('Ainda estou aqui.', 'speak'))
    assert 'guard' not in result.event['heard_by']


def test_margin_scales_with_the_listeners_own_auditory_capacity():
    session = corridor(guard_x=10, senses={'hearing_range_meters': 9})
    assert 'guard' in session.execute(NarrativeIntent('Olá.', 'speak')).event['heard_by']
    beyond = corridor(guard_x=11, senses={'hearing_range_meters': 9})
    assert 'guard' not in beyond.execute(NarrativeIntent('Olá.', 'speak')).event['heard_by']


def test_speech_margin_does_not_increase_wake_range():
    session = corridor(senses={'sleeping': True, 'wake_range_meters': 21})
    session.execute(NarrativeIntent('Acorde.', 'speak'))
    assert 'guard' not in session.perception.awakened


def test_closed_door_keeps_the_original_acoustic_limit():
    data = dict(width=30, height=5, start=[2, 2], areas=[
        dict(id='west', name='Oeste', x=1, y=1, width=9, height=3),
        dict(id='east', name='Leste', x=11, y=1, width=18, height=3)],
        passages=[dict(id='door', name='Porta', kind='door', position=[10, 2], is_open=False,
                       locked=False, connects=['west', 'east'])],
        creatures=[dict(id='guard', name='Guarda', position=[20, 2])])
    session = build_session(data)
    assert 'guard' not in session.execute(NarrativeIntent('Olá.', 'speak')).event['heard_by']


def test_npcs_can_share_memories_in_normal_conversation_without_transmitting_to_blind_bystanders():
    session = corridor(observers=[dict(id='other', name='Outro NPC', position=[16, 3]),
        dict(id='bystander', name='Sem contato visual', position=[17, 2], senses={'can_see': False})])
    claim = Claim('player', 'parentage', 'noble_heir')
    first = session.execute(NarrativeIntent('Sou filho de um nobre.', 'speak', claims=(claim,)))
    assert set(first.event['heard_by']) == {'guard', 'other'}
    memory = next(m for m in session.knowledge.store.active('guard') if m.claim == claim)
    result = session.knowledge.communicate('guard', 'Ele diz ser filho de um nobre.', Position(16, 2),
                                           memory_ids=(memory.id,))
    assert 'player' in result['heard_by']
    assert any(m.claim == claim and m.source.actor_id == 'guard' for m in session.knowledge.store.active('player'))


def test_actual_dungeon_distance_accepts_normal_speech_and_social_reply_through_runner(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    data = json.loads((Path(__file__).resolve().parents[2] / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [7, 19]
    data['creatures'][0]['position'] = [9, 5]
    next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
    data['observers'][0]['senses']['sleeping'] = False
    claim = Claim('player', 'offer_reward', 'gold_if_listen')
    with open_game(data, allow_unconfigured=True) as game:
        session = game.flow.session
        session.offer_parley('guard_1', 'Pare! O que está fazendo aqui?')
        assert session.perception.sound_distance(session.state.position, session.creatures[0].position) == 22.5
        before = deepcopy(session.encounter.states)
        profile = session.social.profiles['guard_1']
        assessment = DispositionAssessment('listen', 'player', 'Ouvir sem conceder liberdade.', 0, 0, 'Neutro.',
            tuple(PersonaEffect(i.id, int(i.id == 'profit'), 'Interesse no ganho.') for i in profile.persona.interests),
            (MemoryEffect(claim, 'profit', 1, 'Oferta nova ouvida.'),),
            'Fale daí. Você continua sob custódia.', 'Não.', ('Manter custódia e distância.',))
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt, 'speak', claims=(claim,)),)), prompt))
        game.flow.world_director = SimpleNamespace(decide=lambda context: WorldPlan((WorldReaction(0, None, (
            WorldAction('guard_1', 'influence', 'Considera a proposta.',
                        influence=InfluenceRequest(skill='persuasion', assessment=assessment)),)),)))
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='O guarda aceita ouvir.'))
        result = game.runner.submit('Falo calmamente: prometo ouro se você me ouvir.')
        assert result.status == 'completed' and not result.report.failures
        assert not result.report.stop_reason and session.parley.status == 'listening'
        assert 'guard_1' in result.report.events[0]['heard_by']
        response = next(e for e in result.report.world_events if e['operation'] == 'say')
        assert response['perceptible'] and 'player' in response['heard_by']
        assert session.encounter.states == before and session.encounter.combat is None
        assert session.state.position == Position(7, 19) and session.creatures[0].position == Position(9, 5)
