"""Avaliação inicial e reavaliação com informações realmente percebidas."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from trama.actions import ActionError
from trama.application.intents import MovementIntent, MovementSegment, NarrativeIntent, RuleIntent
from trama.application.parley import InfluenceRequest
from trama.application.scenarios import build_session
from trama.application.situations import load_situation
from trama.application.world import WorldAction
from trama.application.world_resolution import WorldExecutor
from trama.knowledge import Claim
from trama.social import DispositionAssessment, MemoryEffect, PersonaEffect


def game(dice, *rolls, weight=2, alignment='neutral'):
    return build_session(dict(width=15,height=5,start=[2,2],creatures=[dict(id='guard',name='Guarda',position=[10,2],
        social=dict(alignment=alignment,persona=dict(name='Guarda',role='Guarda',background='Mantém custódia, mas pode ouvir.',
        interests=[dict(id='safety',description='Evitar riscos ouvindo.',weight=weight,evidence_predicates=['identity'])])))]),roller=dice(*rolls))


def assess(effect=1, memories=()):
    return DispositionAssessment('listen','player','Ouvir brevemente mantendo a custódia.',0,0,'Pedido neutro.',
        (PersonaEffect('safety',effect,'Ouvir sem relaxar controle.'),),memories,
        'Fique aí. Vou ouvir, mas você continua sob custódia.','Não. Volte à cela.',('Ficar onde está.','Manter a custódia.'))


def speak_and_resolve(session, value, *, claims=(), text='Por favor, me ouça.',skill='persuasion',attitude='indifferent'):
    if session.parley is None:
        session.offer_parley('guard','Pare onde está.')
    session.execute(NarrativeIntent(text,'speak',claims=claims))
    return session.resolve_influence('guard',InfluenceRequest(skill=skill,attitude=attitude,assessment=value),'O guarda avalia o pedido.')


@pytest.mark.parametrize('weight,effect,expected',[(4,1,'willing'),(4,-1,'unwilling')])
def test_disposition_extremes_do_not_roll_or_start_combat(dice,weight,effect,expected):
    session=game(dice,weight=weight)
    before=deepcopy(session.encounter.states)
    event=speak_and_resolve(session,assess(effect))
    assert event['willingness']==expected and 'dice' not in event
    assert not session.encounter.roller.sides and session.encounter.combat is None
    assert session.encounter.states==before


@pytest.mark.parametrize('die,accepted',[(20,True),(1,False)])
def test_hesitation_uses_influence_and_returns_a_concrete_response(dice,die,accepted):
    session=game(dice,die)
    event=speak_and_resolve(session,assess())
    assert event['willingness']=='hesitant' and event['accepted'] is accepted
    assert event['dice']==[die] and event['dc']==15 and session.encounter.combat is None
    assert session.parley.status==('listening' if accepted else 'pending')
    responses=[e for e in session.drain_world_events() if e['operation']=='say']
    assert len(responses)==1 and responses[0]['text']==event['response_text']


def test_accepting_to_listen_never_grants_free_movement(dice):
    session=game(dice,weight=4)
    speak_and_resolve(session,assess())
    assert session.parley.concession['goal']=='listen' and not session.peaceful_npcs
    with pytest.raises(ActionError,match='Responda'):
        session.execute(MovementIntent((MovementSegment('east',1),),False,''))


def test_rewording_does_not_change_the_verdict_or_reroll(dice):
    session=game(dice,1)
    first=speak_and_resolve(session,assess())
    second=speak_and_resolve(session,replace(assess(),description='Ouça minha outra formulação.'),text='Por favor, escute.')
    assert first['accepted'] is False and second['accepted'] is False
    assert second['reused'] and not second['reevaluated']
    assert session.encounter.roller.sides==[20]


def test_listener_reference_does_not_allow_another_roll(dice):
    session=game(dice,1)
    speak_and_resolve(session,assess())
    repeated=speak_and_resolve(session,replace(assess(),target_id='guard'))
    assert repeated['reused'] and session.encounter.roller.sides==[20]


def test_irrelevant_information_does_not_reevaluate(dice):
    session=game(dice,1)
    speak_and_resolve(session,assess())
    event=speak_and_resolve(session,assess(),claims=(Claim('player','clothing','blue'),),text='Minha roupa é azul. Ouça-me.')
    assert event['reused'] and not event['relevant_change']
    assert session.encounter.roller.sides==[20]


def test_new_relevant_report_reevaluates_but_does_not_become_world_truth(dice):
    session=game(dice,1)
    first=speak_and_resolve(session,assess())
    claim=Claim('player','identity','noble_heir')
    updated=assess(memories=(MemoryEffect(claim,'safety',1,'Alegação pode envolver represálias.'),))
    event=speak_and_resolve(session,updated,claims=(claim,),text='Sou filho de um lorde.')
    assert not first['accepted'] and event['accepted'] and event['willingness']=='willing'
    assert event['reevaluated'] and event['relevant_change'] and not event['reused']
    assert event['disposition']['components']['memories']==1
    assert event['disposition']['memory_effects'][0]['source']['kind']=='report'
    assert session.encounter.roller.sides==[20] and session.encounter.combat is None


def test_repeating_the_same_claim_is_not_new_evidence(dice):
    session=game(dice,1)
    claim=Claim('player','identity','noble_heir')
    value=assess(memories=(MemoryEffect(claim,'safety',-1,'Alega uma identidade que suscita cautela.'),))
    first=speak_and_resolve(session,value,claims=(claim,))
    repeated=speak_and_resolve(session,value,claims=(claim,))
    assert first['willingness']=='hesitant' and not first['accepted']
    assert repeated['reused'] and session.encounter.roller.sides==[20]


def test_evidence_must_have_been_heard_and_belong_to_the_npc(dice):
    session=game(dice,weight=4)
    claim=Claim('player','identity','noble_heir')
    value=assess(memories=(MemoryEffect(claim,'safety',1,'Tenta inventar evidência.'),))
    with pytest.raises(ActionError,match='não conhece'):
        speak_and_resolve(session,value)


def test_initial_assessment_is_required_even_for_legacy_willingness(dice):
    session=game(dice)
    session.offer_parley('guard','Pare.')
    session.execute(NarrativeIntent('Me ouça.','speak'))
    with pytest.raises(ActionError,match='avaliação'):
        session.resolve_influence('guard',InfluenceRequest('willing'),'Não pode ignorar os fatores.')


def test_reset_clears_social_results_and_restores_profile(dice):
    session=game(dice,weight=4)
    speak_and_resolve(session,assess())
    profile=session.social.profiles['guard']
    session.reset()
    assert not session.social.decisions and session.social.profiles['guard']==profile
    assert session.parley is None


def test_explicit_attack_can_still_start_combat_after_social_refusal(dice):
    session=game(dice,20,19,1,weight=4)
    speak_and_resolve(session,assess(-1))
    session.execute(RuleIntent('start_combat'))
    assert session.encounter.combat is not None


def test_off_speech_does_not_resolve_or_reassess_social_requests(dice):
    from trama.application.conversation import Conversation
    session=game(dice,weight=4)
    speak_and_resolve(session,assess())
    before=deepcopy(session.social.context(('guard',)))
    context=Conversation(session).narration_context()
    assert 'social' not in context['world']
    assert session.social.context(('guard',))==before
