"""Acompanhamento após ações reais, audição e limites antes do combate; sem IA paga."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from types import SimpleNamespace
from pathlib import Path

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
from trama.application.world import WorldAction, WorldError, WorldPlan, WorldReaction
from trama.application.world_resolution import WorldExecutor
from trama.infrastructure.openai_world_director import parse_world_plan
from trama.knowledge import Claim, MemorySource
from trama.relationships import RelationshipEpisode
from trama.bootstrap import open_game
from trama.characters import CharacterError
from trama.conversation_state import ConversationUpdate, ConversationPoint, ProposalUpdate, ProposalTerm
from trama.opinions import OptionAssessment, TermAssessment
from trama.social import PersonaEffect, MemoryEffect
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


def episode_scene(roller):
    return build_session(dict(width=8, height=6, start=[2, 2], creatures=[dict(
        id='sentinel', name='Sentinela', position=[3, 2], relationships=[dict(target_id='player',
            trust=dict(value=4, reason='História inicial.'),
            affection=dict(value=4, reason='História inicial.'))])]), roller=roller)


def episode_evidence(session, subject, value, *, owner='sentinel', kind='observation',
                     actor='player', topics=('betrayal',)):
    return session.knowledge.store.learn(owner, Claim(subject, 'aftermath', value),
        'Evidência preparada para este controle.',
        MemorySource(kind, f'{subject}:{value}:{session.knowledge.store.revision}', actor),
        when='Ocasião do controle.', context='Percepção ou relato com dono explícito.',
        entities=('player',), topics=topics)


def apply_episode(session, kind, memory):
    return session.relationship_history.apply((RelationshipEpisode(
        'sentinel', 'player', kind, memory.id, 'Interpretação da evidência percebida.'),))


def test_suspicion_confirmation_and_correction_replace_one_contribution_and_keep_history(dice):
    session = episode_scene(dice())
    rumor = episode_evidence(session, 'incident', 'accused', kind='report', actor='ally')
    apply_episode(session, 'suspicion', rumor)
    repeated = episode_evidence(session, 'incident', 'accused', kind='report', actor='ally')
    apply_episode(session, 'suspicion', repeated)
    assert session.relationships.get('sentinel', 'player').trust.value == 3
    assert len(session.relationships.history('sentinel')) == 1
    observed = episode_evidence(session, 'incident', 'accused')
    apply_episode(session, 'betrayal_discovered', observed)
    relation = session.relationships.get('sentinel', 'player')
    assert (relation.trust.value, relation.affection.value) == (2, 3)
    corrected = episode_evidence(session, 'incident', 'another_actor', actor=None)
    apply_episode(session, 'correction', corrected)
    relation = session.relationships.get('sentinel', 'player')
    assert (relation.trust.value, relation.affection.value) == (4, 4)
    history = session.relationships.history('sentinel')
    assert [e['kind'] for e in history] == ['suspicion', 'betrayal_discovered', 'correction']
    assert history[0]['source']['kind'] == 'report'
    assert history[1]['before']['trust'] == 3 and history[1]['after']['trust'] == 2
    summaries = [m for m in session.knowledge.store.active('sentinel')
                 if m.claim.predicate == 'relationship_episode']
    assert len(summaries) == 1 and summaries[0].claim.value == 'correction'
    assert not summaries[0].shareable
    session.reset()
    assert not session.relationships.history('sentinel')
    assert session.relationships.get('sentinel', 'player').trust.value == 4


def test_episode_correction_recomputes_from_initial_levels_at_the_cap(dice):
    session = episode_scene(dice())
    for subject in ('help_one', 'help_two'):
        apply_episode(session, 'costly_help', episode_evidence(session, subject, 'true', topics=('costly_help',)))
    for subject, expected in (('help_one', 5), ('help_two', 4)):
        apply_episode(session, 'correction', episode_evidence(session, subject, 'false', actor=None))
        relation = session.relationships.get('sentinel', 'player')
        assert (relation.trust.value, relation.affection.value) == (expected, expected)


def test_episode_evidence_must_be_owned_and_confirmed_and_invalid_batches_are_atomic(dice):
    session = episode_scene(dice())
    rumor = episode_evidence(session, 'rumor', 'true', kind='report', actor='ally')
    foreign = episode_evidence(session, 'secret', 'true', owner='player')
    observed = episode_evidence(session, 'care', 'true', topics=('care',))
    before = session.knowledge.store.export()
    for memory in (rumor, foreign):
        with pytest.raises(ActionError):
            apply_episode(session, 'betrayal_discovered', memory)
    with pytest.raises(ActionError):
        session.relationship_history.apply((
            RelationshipEpisode('sentinel', 'player', 'care_shown', observed.id, 'Cuidado observado.'),
            RelationshipEpisode('sentinel', 'missing', 'care_shown', observed.id, 'Alvo inválido.')))
    assert not session.relationships.history('sentinel')
    assert session.knowledge.store.export() == before
    apply_episode(session, 'care_shown', observed)
    assert session.relationships.get('sentinel', 'player').affection.value == 5


def council_events_data(predicate='supply_outlook'):
    data = json.loads((Path(__file__).resolve().parents[2] / 'src/trama/scenarios/generals_council.json').read_text())
    data['creatures'][0]['senses']['hearing_range_meters'] = 6
    data['observers'] = [dict(id='messenger', name='Mensageira', position=[5, 4], knowledge=[dict(
        id='dispatch', claim=dict(subject_id='supply_train', predicate=predicate, value='blocked'),
        text='O comboio está bloqueado.', source=dict(kind='observation', event_id='dispatch-observed'),
        when='Antes do encontro.', context='Observação autoral; quando transmitida será relato do destinatário.')])]
    return data


def council_opinion(session, *, changed=False):
    profile = session.social.profiles['general_voss']
    term = TermAssessment('at:1', 'Proponho uma retirada verificável.', 0, 0, 'Termo local de controle.',
        tuple(PersonaEffect(i.id, 0, 'A objeção territorial permanece.') for i in profile.persona.interests),
        (MemoryEffect(Claim('supply_train', 'supply_outlook', 'blocked'), 'population', 1,
                      'A notícia torna urgente discutir abastecimento; ainda é relato.'),) if changed else ())
    return WorldPlan((WorldReaction(0, None, (), opinions=(OptionAssessment(
        'general_voss', 'conversation_1', 'proposal', 'Retirada verificável.', (term,), proposal_id='proposal_1'),)),))


def council_choice(initiative, text, **update):
    return WorldPlan((WorldReaction(0, None, (WorldAction('general_voss', 'say', text,
        conversation=ConversationUpdate(**update)),)),), intent=IntentDecision(
            'general_voss', 'Preservar a população de Valdren.', 'Considerar os acontecimentos percebidos.',
            'Garantia da fronteira.', initiative, 'Decisão própria conforme os fatos percebidos.'))


def prepare_council_game(game):
    flow = game.flow
    prompt = 'Proponho uma retirada verificável.'
    flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
        NarrativeIntent(prompt, 'speak', conversation=ConversationUpdate(target_ids=('general_voss',),
            proposal=ProposalUpdate('offer', terms=(ProposalTerm(None, 'request', prompt, 'player'),)))),)), prompt))
    flow.world_director = SimpleNamespace(decide=lambda context: council_opinion(flow.session)
        if context['phase'] == 'player_action' else council_choice('clarify', 'Quem garante a fronteira?',
            points=(ConversationPoint('question', 'Quem garante a fronteira?'),)))
    flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='Os acontecimentos reais são narrados.')
        if context['allow_on'] else Speech(off='Consulta às informações já percebidas.'))
    assert game.runner.submit(prompt).status == 'completed'
    assert len(flow.session.social.opinions) == 1


@pytest.mark.parametrize('predicate,volume,review', [
    ('supply_outlook', 'normal', True), ('favorite_color', 'normal', False), ('supply_outlook', 'quiet', False)])
def test_npc_revelation_reopens_only_perceived_relevant_information_without_another_player_speech(
        dice, predicate, volume, review):
    from trama.application.intents import MovementIntent, MovementSegment
    with open_game(council_events_data(predicate), roller=dice(), allow_unconfigured=True) as game:
        prepare_council_game(game)
        flow, session = game.flow, game.flow.session
        flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
            MovementIntent((MovementSegment('east', 1),), False, ''),)), prompt))
        def decide_event(context):
            if context['phase'] == 'player_action':
                return WorldPlan((WorldReaction(0, None, (WorldAction('messenger', 'say',
                    'O comboio está bloqueado.', memory_ids=('messenger:dispatch',), volume=volume),)),))
            if context['phase'] == 'npc_review':
                memory = context['observations']['events'][0]['memory']
                assert memory['owner_id'] == 'general_voss' and memory['source']['kind'] == 'report'
                assert memory['source']['actor_id'] == 'messenger'
                return council_opinion(session, changed=True)
            if review:
                assert context['opinions'][-1]['current']
                return council_choice('suspend', 'Suspendamos a audiência para conferir essa notícia.',
                    status='suspended', reason='Suspendamos a audiência para conferir essa notícia.')
            return council_choice('insist', 'Ainda preciso da garantia da fronteira.')
        flow.world_director = SimpleNamespace(decide=decide_event)
        result = game.runner.submit('Dou um passo para contornar a mesa.')
        assert result.status == 'completed' and not result.report.failures
        stages = [r.stage for r in result.requests]
        assert stages == (['interpret', 'world', 'npc_review', 'npc_agency', 'narrate'] if review else
                          ['interpret', 'world', 'npc_agency', 'narrate'])
        assert all(e['operation'] != 'speak' for e in result.report.events)
        assert len(session.social.opinions) == (2 if review else 1)
        frame = session.conversations.view('general_voss')[0]
        assert frame['status'] == ('suspended' if review else 'active')
        assert any(p['text'] == 'Quem garante a fronteira?' and not p['resolved'] for p in frame['points'])
        assert 'Decisão própria conforme os fatos percebidos.' not in json.dumps(result.reply.__dict__)
        if not review:
            return
        # Outro acontecimento percebido permite retomar a mesma conversa e sua pergunta.
        flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
            NarrativeIntent(prompt, 'speak', claims=(Claim('supply_train', 'supply_outlook', 'clear'),),
                conversation=ConversationUpdate(conversation_id='conversation_1')),)), prompt))
        flow.world_director = SimpleNamespace(decide=lambda context:
            council_choice('resume', 'Retomemos a audiência. Quem garante a fronteira?',
                status='active', reason='Retomemos a audiência.') if context['phase'] == 'npc_agency' else WorldPlan())
        resumed = game.runner.submit('Disseram que o comboio voltou a passar.')
        assert resumed.status == 'completed' and not resumed.report.failures
        assert [r.stage for r in resumed.requests] == ['interpret', 'world', 'npc_review', 'npc_agency', 'narrate']
        assert session.conversations.view('general_voss')[0]['status'] == 'active'
        assert any(not p['resolved'] for p in session.conversations.view('general_voss')[0]['points'])


def test_a_new_report_can_reconsider_an_npc_who_already_acted_once_and_duplicate_reports_do_not_loop(dice):
    from trama.application.intents import MovementIntent, MovementSegment
    data = council_events_data()
    data['observers'][0]['social'] = dict(alignment='neutral', persona=dict(name='Mensageira',
        role='Mensageira', background='Entrega notícias ao conselho.', interests=[]))
    with open_game(data, roller=dice(), allow_unconfigured=True) as game:
        prepare_council_game(game)
        flow, session = game.flow, game.flow.session
        # Participação da mensageira é estabelecida por fala percebida, sem editar o registro.
        text = 'Mensageira, permaneça nesta audiência.'
        introduction = flow.conversation.execute(ActionPlan((NarrativeIntent(text, 'speak', conversation=ConversationUpdate(
            conversation_id='conversation_1', target_ids=('messenger',))),)))
        session.agency.pending(introduction, {})
        flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((MovementIntent((MovementSegment('east', 1),), False, ''),)), prompt))
        calls = []
        def director(context):
            calls.append((context['phase'], context.get('actor', {}).get('id')))
            if context['phase'] in {'player_action', 'npc_review'}:
                return WorldPlan()
            if context['actor']['id'] == 'messenger':
                return WorldPlan((WorldReaction(0, None, tuple(WorldAction('messenger', 'say',
                    'O comboio está bloqueado.', memory_ids=('messenger:dispatch',)) for _ in range(2))),),
                    intent=IntentDecision('messenger', 'Entregar a notícia.', 'Relatar o ocorrido.', None,
                        'respond', 'Tem uma notícia própria para compartilhar.'))
            return council_choice('clarify', 'Preciso conferir as informações sem perder a pergunta anterior.')
        flow.world_director = SimpleNamespace(decide=director)
        result = game.runner.submit('Dou um passo para contornar a mesa sem falar.')
        assert result.status == 'completed' and not result.report.failures
        assert calls == [('player_action', None), ('npc_agency', 'general_voss'),
            ('npc_agency', 'messenger'), ('npc_review', 'general_voss'), ('npc_agency', 'general_voss')]
        event = next(r for r in result.requests if r.stage == 'npc_review').context['observations']['events']
        assert len(event) == 1
        snapshot = deepcopy(session.agency._pending_events)
        assert game.runner.submit('[Quais informações foram ouvidas?]').status == 'completed'
        assert session.agency._pending_events == snapshot
        assert game.runner.reset().status == 'completed'
        assert not session.agency._pending_events and not session.agency._review_events


def test_incident_acquisition_distinguishes_noise_visible_injury_and_identified_attacker(dice):
    data = dict(width=10, height=7, start=[6, 1], player=dict(armor='none', weapons=[]), creatures=[
        dict(id='victim', name='Soldado', position=[5, 2], hostile=True, sheet=dict(armor='none')),
        dict(id='seer', name='Testemunha', position=[6, 3], hostile=False),
        dict(id='injury_only', name='Testemunha distante', position=[3, 2], hostile=False,
             senses=dict(sight_range_meters=3))], observers=[
        dict(id='listener', name='Ouvinte', position=[3, 3], senses=dict(can_see=False)),
        dict(id='unaware', name='Ausente', position=[1, 5], senses=dict(can_see=False, can_hear=False))])
    session = build_session(data, roller=dice(20, 20, 1, 15))
    conversation = Conversation(session)
    conversation.execute(ActionPlan((NarrativeIntent('Quem garante a fronteira?', 'speak',
        conversation=ConversationUpdate(target_ids=('seer', 'injury_only', 'listener'),
            points=(ConversationPoint('question', 'Quem garante a fronteira?'),))),)))
    session.execute(RuleIntent('start_combat'))
    before = session.encounter.states['victim'].hp
    session.execute(RuleIntent('attack', 'victim', weapon='unarmed', allow_approach=False))
    assert session.encounter.states['victim'].hp < before
    own = lambda actor: [m for m in session.knowledge.store.active(actor) if m.claim.predicate == 'observed_injury']
    assert own('seer')[0].source.actor_id == 'player'
    assert own('injury_only')[0].source.actor_id is None
    assert 'player' not in json.dumps(own('injury_only')[0].data())
    assert not own('listener') and not own('unaware')
    session.emit_noise('unidentified_sound', Position(5, 2), 'loud')
    assert session.agency._pending_events['listener'][0]['kind'] == 'noise'
    assert session.agency._pending_events['listener'][0]['position'] is None
    assert 'unaware' not in session.agency._pending_events
    assert session.agency.next_review(set()) is None  # Nenhuma agência durante iniciativa.
    WorldExecutor(session).execute(WorldAction('victim', 'end_conflict', 'O confronto termina.'))
    actor = session.agency.next_review(set())
    assert actor == 'seer'
    context = conversation.agency_context(actor, review=True)
    assert context['observations']['events'][0]['memory']['source']['actor_id'] == 'player'
    with pytest.raises(WorldError, match='revisão|Reconsideração'):
        conversation.execute_review(actor, WorldPlan((WorldReaction(0, None, (
            WorldAction(actor, 'attack', 'Tenta atacar fora da vez.', target_id='player'),)),)))


def test_investigation_moves_only_toward_a_perceived_incident_and_preserves_pending_questions(dice):
    with open_game(council_events_data(), roller=dice(), allow_unconfigured=True) as game:
        prepare_council_game(game)
        session, conversation = game.flow.session, game.flow.conversation
        session.emit_noise('messenger', session.perception.observer('messenger').position, 'loud')
        messages = len(conversation.messages)
        bad = WorldPlan((WorldReaction(0, None, (WorldAction('general_voss', 'move', 'Investiga.',
            destination=Position(1, 1)),)),), intent=IntentDecision('general_voss', 'Conferir o ruído.',
                'Investigar.', None, 'investigate', 'Ruído percebido.'))
        good = replace(bad, reactions=(WorldReaction(0, None, (
            WorldAction('general_voss', 'say', 'Suspendamos a audiência para conferir o ruído.',
                conversation=ConversationUpdate(status='suspended', reason='Suspendamos a audiência para conferir o ruído.')),
            WorldAction('general_voss', 'move', 'Aproxima-se do local visto.', destination=Position(6, 4)))),))
        origin = session.creatures[0].position
        game.flow.world_director = SimpleNamespace(decide=lambda context:
            WorldPlan() if context['phase'] == 'npc_review' else good)
        scheduled = game.runner.react_to_events(max_requests=0)
        assert scheduled.status == 'request_limit'
        assert scheduled.pending_request_id == game.flow.pending_request.id
        with pytest.raises(ActionError, match='localização percebida'):
            session.agency.validate('general_voss', bad)
        result = game.runner.run_until_input()
        assert result.status == 'completed'
        assert [r.stage for r in result.requests] == ['npc_review', 'npc_agency', 'narrate']
        report = result.report
        assert not report.failures and not report.stop_reason
        assert session.creatures[0].position != origin
        assert any(e['operation'] == 'move' and e['traveled_meters'] > 0 for e in report.world_events)
        frame = session.conversations.view('general_voss')[0]
        assert frame['status'] == 'suspended' and any(not p['resolved'] for p in frame['points'])
        assert not game.runner.react_to_events().requests
        assert len(conversation.messages) == messages + 1  # Somente a narração, sem fala falsa do jogador.


def test_combat_suspends_participants_without_a_fake_speech_or_free_attack_and_keeps_pending_points(dice):
    data = council_events_data()
    data['start'] = [7, 3]
    with open_game(data, roller=dice(20, 20, 1, 1), allow_unconfigured=True) as game:
        prepare_council_game(game)
        session = game.flow.session
        before = session.knowledge.communication_sequence
        previous_speaker = session.conversations.view('general_voss')[0]['last_speaker']
        WorldExecutor(session).execute(WorldAction('general_voss', 'start_conflict', 'Inicia um confronto.'))
        assert session.encounter.combat.active_id == 'player'
        assert session.knowledge.communication_sequence == before
        for actor in ('player', 'general_voss'):
            frame = session.conversations.view(actor)[0]
            assert frame['status'] == 'suspended' and frame['last_speaker'] == previous_speaker
            assert any(not p['resolved'] for p in frame['points'])
        assert session.agency.next_review(set()) is None
        hp = session.encounter.states['player'].hp
        with pytest.raises(CharacterError, match='turno'):
            WorldExecutor(session).execute(WorldAction('general_voss', 'attack', 'Tenta agir fora do turno.',
                target_id='player', weapon='unarmed'))
        assert session.encounter.states['player'].hp == hp
