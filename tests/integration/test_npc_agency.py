"""Acompanhamento após ações reais, audição e limites antes do combate; sem IA paga."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.actions import ActionError
from trama.agency import IntentDecision
from trama.application.conversation import Conversation
from trama.application.context_contracts import ContextError
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow
from trama.application.game_runner import GameRunner
from trama.application.intents import ActionPlan, NarrativeIntent, RuleIntent
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.application.world_resolution import WorldExecutor
from trama.infrastructure.openai_world_director import parse_world_plan
from trama.knowledge import Claim
from trama.spatial import Position


def scene(roller=None):
    return build_session(dict(width=25,height=6,start=[2,2],player=dict(armor='none'),
        creatures=[dict(id='sentinel',name='Sentinela',position=[18,2],senses=dict(response='observe'))],
        observers=[dict(id='ally',name='Companheiro',position=[3,2],senses=dict(perception_bonus=0))]),roller=roller)


def contact(session):
    WorldExecutor(session).execute(WorldAction('sentinel','parley','Preciso de uma resposta sua.'))
    session.drain_world_events()


def decision(operation='say',actor='sentinel'):
    return WorldPlan((WorldReaction(0,None,(WorldAction(actor,operation,
        'Quanto oferece para resolvermos isso?' if operation=='say' else 'Aguarda uma resposta concreta.'),)),),
        intent=IntentDecision(actor,'Concluir a negociação.','Cobrar uma proposta.','Valor da proposta.'))


def flow_for(session, *, replies=None):
    replies=iter(replies or [decision()])
    flow=GameFlow(session,
        SimpleNamespace(interpret=lambda prompt,context:sourced_plan(ActionPlan((
            NarrativeIntent('Segredo safira-947.','speak',volume='quiet',
                claims=(Claim('player','password','safira-947'),)),)),prompt)),
        SimpleNamespace(narrate=lambda context:Speech(on='Os acontecimentos registrados são narrados.',off='Consulta ao estado.')),
        SimpleNamespace(decide=lambda context:next(replies) if context['phase']=='npc_agency' else WorldPlan()))
    return flow


def test_private_words_do_not_reach_the_agency_context_or_npc_memory(dice):
    session=scene(dice())
    contact(session)
    flow=flow_for(session)
    result=GameRunner(flow).submit('Falo baixo ao companheiro: segredo safira-947.')
    assert result.status=='completed' and not result.report.failures
    assert [r.stage for r in result.requests]==['interpret','world','npc_agency','narrate']
    request=next(r for r in result.requests if r.stage=='npc_agency')
    assert 'safira-947' not in json.dumps(request.context)
    unheard=next(e for e in request.context['observations']['communications'] if e['actor_id']=='player')
    assert unheard['understood'] is False and unheard['text'] is None
    assert all(m.claim.predicate!='password' for m in session.knowledge.store.active('sentinel'))
    assert any(m.claim.predicate=='password' for m in session.knowledge.store.active('ally'))
    assert session.agency.intents['sentinel']['goal']=='Concluir a negociação.'
    speech=next(e for e in result.report.events if e['operation']=='speak')
    assert speech['heard_by']==['ally']
    assert any(e['operation']=='say' and e['actor_id']=='sentinel' for e in result.report.world_events)
    public=flow.conversation.narration_context(report=result.report)
    assert 'Concluir a negociação.' not in json.dumps(public)
    whisper=next(e for e in public['perception']['communications'] if e['actor_id']=='player')
    assert whisper['volume']=='quiet' and whisper['heard_by']==['ally']


def test_a_justified_wait_cannot_be_renewed_by_another_private_conversation(dice):
    session=scene(dice())
    contact(session)
    flow=flow_for(session,replies=[decision('wait'),decision('wait')])
    first=GameRunner(flow).submit('Falo baixo com meu companheiro.')
    assert first.status=='completed'
    assert session.agency.intents['sentinel']['waits_used']==1
    second=GameRunner(flow).submit('Continuo falando baixo com meu companheiro.')
    assert second.status=='failed' and 'não pode ser renovada' in str(second.error)
    assert session.agency.intents['sentinel']['waits_used']==1
    assert session.encounter.combat is None


def test_a_followup_can_carry_on_after_waiting_without_automatic_violence(dice):
    session=scene(dice());contact(session)
    flow=flow_for(session,replies=[decision('wait'),decision()])
    runner=GameRunner(flow)
    assert runner.submit('Falo baixo com meu companheiro.').status=='completed'
    result=runner.submit('Continuo conversando em voz baixa.')
    assert result.status=='completed' and session.encounter.combat is None
    assert session.agency.intents['sentinel']['unattended_interactions']==2
    assert any(e['operation']=='say' and e['actor_id']=='sentinel' for e in result.report.world_events)


def test_off_questions_and_look_queries_do_not_tick_or_call_the_npc(dice):
    session=scene(dice());contact(session)
    flow=flow_for(session)
    runner=GameRunner(flow)
    runner.submit('Falo baixo com meu companheiro.')
    before=deepcopy((session.agency.intents,session.knowledge.communications,session.state,session.encounter.states))
    result=runner.submit('[O que aconteceu? Ele ouviu o cochicho?]')
    assert result.status=='completed' and [r.stage for r in result.requests]==['narrate']
    assert (session.agency.intents,session.knowledge.communications,session.state,session.encounter.states)==before
    checkpoint=session.agency.checkpoint()
    report=Conversation(session).execute(ActionPlan((NarrativeIntent('Olho ao redor.','look'),)))
    assert session.agency.pending(report,checkpoint)==[]


def test_first_detection_and_direct_responses_do_not_get_an_extra_npc_action(dice):
    session=scene(dice())
    session.creatures=(replace(session.creatures[0],senses=replace(session.creatures[0].senses,response='challenge')),)
    checkpoint=session.agency.checkpoint()
    report=Conversation(session).execute(ActionPlan((NarrativeIntent('Olho ao redor.','look'),)))
    assert session.parley_pending and session.agency.pending(report,checkpoint)==[]
    checkpoint=session.agency.checkpoint()
    report=Conversation(session).execute(ActionPlan((NarrativeIntent('Explico a situação.','speak'),)),
        WorldPlan((WorldReaction(0,None,(WorldAction('sentinel','say','Vou ouvir sua explicação.'),)),)))
    assert session.agency.pending(report,checkpoint)==[]


@pytest.mark.parametrize('operation',['move','attack','influence','open'])
def test_followup_cannot_add_free_movement_or_attacks_before_initiative(operation,dice):
    session=scene(dice());contact(session)
    args=dict(actor_id='sentinel',operation=operation,text='Ação indevida.')
    if operation=='move':args['destination']=Position(3,2)
    if operation in {'attack','open'}:args['target_id']='player'
    if operation=='influence':
        from trama.application.parley import InfluenceRequest
        args['influence']=InfluenceRequest()
    plan=replace(decision(),reactions=(WorldReaction(0,None,(WorldAction(**args),)),))
    before=(session.state,session.creatures,session.encounter.combat)
    with pytest.raises(ActionError,match='sem movimento ou ataque gratuitos'):
        Conversation(session).execute_agency('sentinel',plan)
    assert (session.state,session.creatures,session.encounter.combat)==before


def test_hostile_choice_rolls_initiative_at_current_positions_and_then_uses_normal_turns(dice):
    session=scene(dice(20,19,1));contact(session)
    positions=(session.state.position,session.creatures[0].position)
    result=GameRunner(flow_for(session,replies=[decision('start_conflict')])).submit('Converso baixo com meu companheiro.')
    assert result.status=='completed'
    assert session.encounter.combat.active_id=='player'
    assert positions==(session.state.position,session.creatures[0].position)
    assert not any(e['operation'] in {'attack','move'} for e in result.report.world_events)
    assert not session.agency.intents


def test_resuming_activity_closes_the_conversation_without_moving_or_giving_items(dice):
    session=scene(dice());contact(session)
    before=(session.state.position,session.creatures[0].position,deepcopy(session.encounter.states))
    result=GameRunner(flow_for(session,replies=[decision('resume_activity')])).submit('Converso baixo com meu companheiro.')
    assert result.status=='completed' and session.parley.status=='peaceful'
    assert not session.agency.intents and session.encounter.combat is None
    assert before==(session.state.position,session.creatures[0].position,session.encounter.states)


def test_unheard_words_injected_into_the_context_are_rejected(dice):
    session=scene(dice());contact(session)
    conversation=Conversation(session)
    conversation.execute(ActionPlan((NarrativeIntent('Segredo.','speak',volume='quiet'),)))
    context=conversation.agency_context('sentinel')
    context['observations']['communications'][0]['text']='Segredo indevido.'
    with pytest.raises(ContextError,match='inaudível'):
        context.require(context.kind)


def test_reset_clears_the_intent_and_communication_history(dice):
    session=scene(dice());contact(session)
    Conversation(session).execute(ActionPlan((NarrativeIntent('Olá.','speak'),)))
    assert session.agency.intents and session.knowledge.communications
    session.reset()
    assert not session.agency.intents and not session.knowledge.communications


def test_agency_transport_round_trips_through_the_real_parser(dice):
    from trama.infrastructure.openai_world_director import ACTION_FIELDS
    value=asdict(decision())
    action=value['reactions'][0]['actions'][0]
    assert set(action)==set(ACTION_FIELDS)
    assert parse_world_plan(json.dumps(value))==decision()


def test_an_audible_exchange_renews_waiting_without_requiring_an_influence_check(dice):
    session=scene(dice());contact(session)
    conversation=Conversation(session)
    conversation.execute_agency('sentinel',decision('wait'))
    assert session.agency.intents['sentinel']['waits_used']==1
    conversation.execute(ActionPlan((NarrativeIntent('Vigia, meu nome é Raul.','speak'),)),
        WorldPlan((WorldReaction(0,None,(WorldAction('sentinel','say','Raul, diga aonde pretende ir.'),)),)))
    intent=session.agency.intents['sentinel']
    assert intent['waits_used']==0 and intent['unattended_interactions']==0
    assert intent['waiting_for']=='Raul, diga aonde pretende ir.'


def test_player_initiated_combat_also_closes_exploration_intentions(dice):
    session=scene(dice(20,19,1));contact(session)
    assert session.agency.intents
    session.execute(RuleIntent('start_combat'))
    assert session.encounter.combat and not session.agency.intents
