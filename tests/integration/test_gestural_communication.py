"""Comunicação visual no motor e no fluxo oficial, com adaptadores locais explícitos."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan, judged_world
from trama.agency import IntentDecision
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow
from trama.application.game_runner import GameRunner
from trama.application.intents import ActionPlan, GestureIntent, MovementIntent, MovementSegment, NarrativeIntent
from trama.application.intents import RuleIntent
from trama.application.scenarios import build_session, load_session
from trama.application.situations import load_situation
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.application.parley import InfluenceRequest
from trama.social import DispositionAssessment, PersonaEffect
from trama.difficulty import Adjudication
from trama.infrastructure.openai_intent_interpreter import parse_intent
from trama.spatial import Position


def scene(*, blocked=False, senses=None, dark=False, observer=True, bystander=False):
    data = dict(width=9, height=5, start=[2, 2], player=dict(armor='none', weapons=[]),
                blocked=[[4, y] for y in range(5)] if blocked else [],
                observers=[dict(id='friend', name='Amigo', position=[6, 2], senses=senses or {})] if observer else [],
                creatures=[] if observer else [dict(id='friend', name='Amigo', position=[6, 2], senses=senses or {})])
    if bystander:
        data['observers'].append(dict(id='bystander', name='Testemunha', position=[2, 3]))
    s = build_session(data)
    if dark:
        # Mapa nomeado para testar iluminação pelo mesmo construtor.
        data.update(areas=[dict(id='room', name='Sala', x=0, y=0, width=9, height=5)], passages=[], dark=[[2, 2]])
        s = build_session(data)
    return s


def gesture(**kwargs):
    return GestureIntent('friend', 'Aceno com a mão para o amigo.', 'Peço que se manifeste.', **kwargs)


def flow_for(s, world=None):
    def decide(ctx):
        if ctx['phase'] == 'npc_agency':
            return judged_world(WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'say',
                'O que você quer dizer?', volume='quiet'),)),), intent=IntentDecision('friend',
                    'Entender o aceno.', 'Perguntar o que significa.', 'Explicação.')), ctx)
        return judged_world(world or WorldPlan(), ctx)
    return GameFlow(s, SimpleNamespace(interpret=lambda p, ctx: sourced_plan(ActionPlan((gesture(),)), p)),
        SimpleNamespace(narrate=lambda ctx: Speech(on='Seu gesto e a resposta são narrados.') if ctx['allow_on']
                        else Speech(off='O sinal não pode chegar ao destinatário dessa posição.')),
        SimpleNamespace(decide=decide))


@pytest.mark.parametrize('senses,blocked,dark', [({}, True, False), ({'can_see': False}, False, False),
    ({'sleeping': True}, False, False), ({'sight_range_meters': 3}, False, False), ({}, False, True)])
def test_invisible_gesture_has_structured_reason_and_no_effects(senses, blocked, dark):
    s = scene(blocked=blocked, senses=senses, dark=dark)
    before = s.state, s.budget, deepcopy(s.knowledge.store.export()), list(s.knowledge.communications)
    report = Conversation(s).execute(ActionPlan((gesture(),)))
    assert report.status == 'blocked' and not report.events and not report.world_events
    assert report.failures[0].code == 'gesture_not_visible'
    assert 'visão' in report.stop_reason or 'visual' in report.stop_reason
    assert (s.state, s.budget, s.knowledge.store.export(), s.knowledge.communications) == before


def test_original_dungeon_geometry_reports_no_line_of_sight_after_preserving_speech():
    situation = load_situation('agencia-off-consulta')
    roller = situation.new_roller()
    s = build_session(situation.scenario_data(), roller=roller)
    c = Conversation(s)
    situation.initialize(c, roller)
    plan = ActionPlan((NarrativeIntent('Peço que confirme minha história.', 'speak'),
        GestureIntent('prisoner', 'Faço um sinal com a mão ao prisioneiro.', 'Quero que confirme minha história.')))
    report = c.execute(plan)
    assert [e['operation'] for e in report.events] == ['speak']
    assert report.failures[0].code == 'gesture_not_visible'
    assert 'linha de visão' in report.stop_reason
    assert s.state.position == Position(7, 19)


def test_clear_gesture_is_visual_free_and_does_not_share_intended_message():
    s = scene(senses={'can_hear': False}, bystander=True)
    before = s.state, s.budget, deepcopy(s.knowledge.store.export())
    report = Conversation(s).execute(ActionPlan((gesture(),)))
    event = report.events[0]
    assert not report.failures and event['received'] and event['understood'] is None
    assert set(event['seen_by']) == {'friend', 'bystander'} and not event['heard_by']
    assert (s.state, s.budget, s.knowledge.store.export()) == before
    for actor in ('friend', 'bystander'):
        observation = s.knowledge.communications_for(actor)[0]
        assert observation['text'] == gesture().text and observation['understood'] is None
        assert 'message' not in observation and gesture().message not in json.dumps(observation)


@pytest.mark.parametrize('outcome,difficulty,advantage,disadvantage,expected', [
    ('automatic', None, False, False, True), ('impossible', None, False, False, False),
    ('check', 'easy', False, False, True), ('check', 'moderate', False, False, False),
    ('check', 'moderate', True, False, True), ('check', 'easy', False, True, False)])
def test_subtle_gesture_uses_context_and_passive_perception_without_dice(outcome, difficulty, advantage, disadvantage, expected):
    s = scene()
    c = Conversation(s)
    intent = GestureIntent('friend', 'Pisco um olho.', 'Quero apoio.', True)
    plan = ActionPlan((intent,))
    ctx = c.world_context(plan)
    request = next(r for r in ctx['world']['adjudication']['requests'] if r['kind'] == 'visual_signal')
    decision = Adjudication(request['id'], outcome, difficulty, advantage, disadvantage,
                            ('gesture:distance_meters',), 'Avaliação contextual explícita do teste local.')
    report = c.execute(plan, WorldPlan(adjudications=(decision,)), require_adjudications=True)
    assert not report.failures and report.events[0]['received'] is expected
    assert all(e['operation'] == 'perception_detected' for e in report.world_events)


def test_dim_light_affects_subtle_gesture_but_does_not_change_line_of_sight():
    s = build_session(dict(width=9, height=5, start=[2, 2],
        areas=[dict(id='room', name='Sala', x=0, y=0, width=9, height=5)], passages=[], dim=[[2, 2]],
        observers=[dict(id='friend', name='Amigo', position=[6, 2])]))
    assert s.npc_sees_player('friend')
    c = Conversation(s)
    plan = ActionPlan((gesture(subtle=True),))
    request = c.world_context(plan)['world']['adjudication']['requests'][0]
    decision = Adjudication(request['id'], 'check', 'easy', False, False, ('gesture:dim',), 'Luz fraca.')
    assert not c.execute(plan, WorldPlan(adjudications=(decision,)), require_adjudications=True).events[0]['received']


def test_new_recipient_gets_response_phase_even_when_world_omits_it():
    s = scene()
    result = GameRunner(flow_for(s)).submit('Aceno para meu amigo.')
    assert result.status == 'completed' and not result.report.failures, str(result.error)
    assert [r.stage for r in result.requests] == ['interpret', 'world', 'npc_agency', 'narrate']
    own = next(r for r in result.requests if r.stage == 'npc_agency')
    assert own.context['actor']['id'] == 'friend' and own.context['parley'] is None
    assert own.context['observations']['communications'][0]['medium'] == 'gesture'
    assert gesture().message not in json.dumps(own.context, ensure_ascii=False)
    assert any(e['operation'] == 'say' and e['actor_id'] == 'friend' for e in result.report.world_events)
    assert 'friend' not in s.agency.intents


def test_recipient_response_is_not_duplicated_if_world_already_replied():
    s = scene()
    world = WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'say', 'Não vou confirmar isso.'),)),))
    result = GameRunner(flow_for(s, world)).submit('Aceno para meu amigo.')
    assert not result.report.failures
    assert [r.stage for r in result.requests] == ['interpret', 'world', 'narrate']
    assert sum(e['operation'] == 'say' for e in result.report.world_events) == 1


def test_conscious_observer_can_choose_not_to_reply_without_fictitious_fighter_turn():
    s = scene()
    flow = flow_for(s)
    def decide(ctx):
        if ctx['phase'] == 'npc_agency':
            return judged_world(WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'wait',
                'Não compreendeu o pedido e opta por não responder.'),)),), intent=IntentDecision('friend',
                    'Avaliar o gesto.', 'Permanece em silêncio.', 'Um esclarecimento.')), ctx)
        return judged_world(WorldPlan(), ctx)
    flow.world_director = SimpleNamespace(decide=decide)
    result = GameRunner(flow).submit('Aceno para meu amigo.')
    assert result.status == 'completed' and not result.report.failures, str(result.error)
    assert any(e['operation'] == 'wait' for e in result.report.world_events)
    assert not s.agency.intents and s.encounter.combat is None


def test_failed_gesture_cannot_trigger_proposed_reply_or_movement():
    s = scene(blocked=True)
    c = Conversation(s)
    world = WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'say', 'Eu vi seu sinal.'),)),))
    report = c.execute(ActionPlan((gesture(),)), world)
    assert not report.events and not report.world_events and report.failures
    assert s.state.position == Position(2, 2)


def test_uncaught_gesture_cannot_trigger_proposed_response():
    s = scene()
    c = Conversation(s)
    plan = ActionPlan((gesture(subtle=True),))
    request = c.world_context(plan)['world']['adjudication']['requests'][0]
    decision = Adjudication(request['id'], 'impossible', None, False, False,
                            ('gesture:distance_meters',), 'Pequeno demais nesta distância.')
    world = WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'say', 'Recebi o sinal!'),)),),
                      adjudications=(decision,))
    report = c.execute(plan, world, require_adjudications=True)
    assert not report.events[0]['received']
    assert all(e['operation'] == 'perception_detected' for e in report.world_events)


def test_known_but_currently_hidden_recipient_is_available_without_hidden_position():
    s = scene()
    s.execute(NarrativeIntent('Olho a sala.'))
    s.grid = replace(s.grid, blocked=frozenset(Position(4, y) for y in range(5)))
    ctx = Conversation(s).interpretation_context()
    assert not ctx['visible_creatures']
    assert ctx['communication_targets'] == [dict(id='friend', name='Amigo', visible=False)]
    prompt = 'Faço um sinal ao meu amigo.'
    validate_player_plan(prompt, sourced_plan(ActionPlan((gesture(),)), prompt), ctx)
    with pytest.raises(PlanAuthorizationError):
        validate_player_plan(prompt, sourced_plan(ActionPlan((replace(gesture(), target_id='unknown'),)), prompt), ctx)


def test_gesture_parse_roundtrip_and_reset_forgets_communication():
    intent = gesture(subtle=True)
    assert parse_intent(json.dumps(asdict(intent))) == intent
    s = scene()
    s.execute(gesture())
    assert s.knowledge.communications
    s.reset()
    assert not s.knowledge.communications and not s.agency.intents


def test_simple_combat_gesture_preserves_action_and_movement(dice):
    s = scene(observer=False)
    s.encounter.roller = dice(20, 20, 1)
    s.execute(RuleIntent('start_combat'))
    before = s.state, s.budget, deepcopy(s.encounter.states)
    report = Conversation(s).execute(ActionPlan((gesture(),)))
    assert not report.failures and report.events[0]['received']
    assert (s.state, s.budget, s.encounter.states) == before


def test_subtle_gesture_after_walking_uses_the_prepared_final_position():
    s = scene()
    c = Conversation(s)
    plan = ActionPlan((MovementIntent((MovementSegment('east', 1),), False, ''), gesture(subtle=True)))
    context = c.world_context(plan)
    requests = [r for r in context['world']['adjudication']['requests'] if r['kind'] == 'visual_signal']
    assert requests[0]['facts']['gesture:distance_meters'] == 4.5
    decision = Adjudication(requests[0]['id'], 'automatic', None, False, False,
                            ('gesture:distance_meters',), 'Gesto nítido nessa distância.')
    report = c.execute(plan, WorldPlan(adjudications=(decision,)), require_adjudications=True)
    assert not report.failures and report.events[-1]['received']


def test_gestural_appeal_can_use_existing_influence_check_when_hesitant(dice):
    s = scene(observer=False, senses={'can_hear': False})
    s.offer_parley('friend', 'Explique-se.')
    s.encounter.roller = dice(20)
    profile = s.social.profiles['friend']
    assessment = DispositionAssessment('listen', 'player', 'Peço que me ouça.', 0, 0, 'Apelo neutro.',
        tuple(PersonaEffect(i.id, 0, 'Nenhum incentivo novo.') for i in profile.persona.interests), (),
        'Vou ouvir.', 'Não vou ouvir.', ('Sem outra concessão.',))
    world = WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'influence', 'Avalia o pedido por gestos.',
        influence=InfluenceRequest(skill='persuasion', assessment=assessment)),)),))
    report = Conversation(s).execute(ActionPlan((gesture(),)), world)
    assert not report.failures
    event = next(e for e in report.world_events if e['operation'] == 'influence')
    assert event['passed'] and event['dc'] == 15 and event['dice'] == [20]


def test_world_wait_is_a_decision_and_does_not_request_a_second_response():
    s = scene()
    world = WorldPlan((WorldReaction(0, None, (WorldAction('friend', 'wait', 'Decide ficar em silêncio.'),)),))
    result = GameRunner(flow_for(s, world)).submit('Aceno para meu amigo.')
    assert result.status == 'completed' and not result.report.failures
    assert 'npc_agency' not in [r.stage for r in result.requests]


def test_darkvision_cancels_dim_light_penalty_within_its_range():
    s = build_session(dict(width=9, height=5, start=[2, 2],
        areas=[dict(id='room', name='Sala', x=0, y=0, width=9, height=5)], passages=[], dim=[[2, 2]],
        observers=[dict(id='friend', name='Amigo', position=[6, 2], senses=dict(darkvision_meters=9))]))
    c = Conversation(s)
    plan = ActionPlan((gesture(subtle=True),))
    request = c.world_context(plan)['world']['adjudication']['requests'][0]
    assert request['facts']['gesture:dim'] is False
    decision = Adjudication(request['id'], 'check', 'easy', False, False, ('gesture:dim',), 'Enxerga com nitidez.')
    report = c.execute(plan, WorldPlan(adjudications=(decision,)), require_adjudications=True)
    assert report.events[0]['received']
