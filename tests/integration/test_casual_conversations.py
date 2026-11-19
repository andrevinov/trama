"""Conversas casuais pela composição/runner; escolhas fixas, sem avaliar IA real."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.agency import IntentDecision
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.situations import load_situation
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation
from trama.conversation_state import ConversationPoint, ConversationUpdate
from trama.spatial import Position


CASES = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/casual_conversations.json').read_text())
PRIVATE = 'Motivo privado casual-841, não é uma fala.'


def narrator(context):
    assert PRIVATE not in json.dumps(context, ensure_ascii=False)
    return Speech(on='Os acontecimentos percebidos são narrados.') if context['allow_on'] else Speech(off='Consulta ao estado.')


def decision(actor, initiative, actions, goal, waiting_for=None):
    return WorldPlan((WorldReaction(0, None, tuple(actions)),), intent=IntentDecision(
        actor, goal, 'Acompanhar esta conversa.', waiting_for, initiative, PRIVATE))


def configure_friend(game, row):
    game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
        NarrativeIntent(prompt, 'speak', conversation=ConversationUpdate(focus=row['focus'],
            target_ids=row.get('target_ids', ()), points=(
            ConversationPoint('question' if row.get('question') else 'statement', prompt),))),)), prompt))
    actions = []
    if row['reply']:
        actions.append(WorldAction('lia', 'say', row['reply'], conversation=ConversationUpdate(
            status='closed' if row.get('close_reason') else None, reason=row.get('close_reason'),
            resolves=('latest',) if row.get('question') else ())))
    if row['initiative'] == 'listen':
        actions.append(WorldAction('lia', 'wait', 'Ouve e aguarda, sem exigir uma resposta.'))
    plan = decision('lia', row['initiative'], actions, row['goal'], row['waiting_for'])
    game.flow.world_director = SimpleNamespace(decide=lambda context: plan if context['phase'] == 'npc_agency' else WorldPlan())
    game.flow.narrator = SimpleNamespace(narrate=narrator)


def test_friend_listens_across_real_turns_without_proposal_and_can_advise_then_close():
    with open_situation(load_situation('conversa-com-amiga'), allow_unconfigured=True) as game:
        session = game.flow.session
        initial = deepcopy(session.encounter.states)
        relation = session.relationships.get('lia', 'player')
        for row in CASES['friend']:
            configure_friend(game, row)
            result = game.runner.submit(row['prompt'])
            assert result.status == 'completed' and not result.report.failures
            assert [r.stage for r in result.requests] == ['interpret', 'world', 'npc_agency', 'narrate']
            frame = session.conversations.view('lia')[0]
            assert frame['focus'] == row['focus']
            assert frame['objective']['goal'] == row['goal']
            assert frame['proposals'] == [] and not session.social.opinions
            if row['initiative'] == 'listen':
                assert session.agency.intents['lia']['waits_used'] == 1
                assert any(e['operation'] == 'wait' for e in result.report.world_events)
            assert not any(e['operation'] == 'influence' for e in result.report.world_events)
        assert frame['status'] == 'closed' and frame['objective']['waiting_for'] is None
        assert 'lia' not in session.agency.intents
        assert session.encounter.states == initial and not session.encounter.roller.used
        assert session.relationships.get('lia', 'player') == relation
        assert not session.relationships.history('lia')
        reopening = dict(prompt='Oi, Lia. Quero falar da feira.', focus='feira', initiative='respond',
            reply='Podemos falar da feira.', goal='Conversar sobre um novo assunto.', waiting_for=None, target_ids=('lia',))
        configure_friend(game, reopening)
        reopened = game.runner.submit(reopening['prompt'])
        assert reopened.status == 'completed' and not reopened.report.failures
        frame = session.conversations.view('lia')[0]
        assert frame['id'] == 'conversation_2' and frame['status'] == 'active'
        assert frame['objective']['goal'] == reopening['goal']


def test_silence_and_off_do_not_renew_listening_but_a_new_addressed_speech_does():
    with open_situation(load_situation('conversa-com-amiga'), allow_unconfigured=True) as game:
        row = CASES['friend'][0]
        configure_friend(game, row)
        assert game.runner.submit(row['prompt']).status == 'completed'
        before = deepcopy(game.flow.session.agency.intents)
        off = game.runner.submit('[Ela está me escutando?]')
        assert off.status == 'completed' and [r.stage for r in off.requests] == ['narrate']
        assert game.flow.session.agency.intents == before
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt, 'wait'),)), prompt))
        repeated = game.runner.submit('Aguardo em silêncio.')
        assert repeated.status == 'failed' and 'espera' in str(repeated.error).lower()
        assert game.flow.session.agency.intents['lia']['waits_used'] == 1
        configure_friend(game, CASES['friend'][1])
        assert game.runner.submit(CASES['friend'][1]['prompt']).status == 'completed'


def test_ignoring_an_explicit_pending_question_does_not_renew_the_wait():
    with open_situation(load_situation('conversa-com-amiga'), allow_unconfigured=True) as game:
        configure_friend(game, CASES['friend'][0])
        plan = decision('lia', 'listen', [WorldAction('lia', 'say', 'Você quer uma sugestão?',
            conversation=ConversationUpdate(points=(ConversationPoint('question', 'Você quer uma sugestão?'),))),
            WorldAction('lia', 'wait', 'Aguarda uma resposta.')], 'Saber se o interlocutor quer uma sugestão.', 'Permissão para sugerir.')
        game.flow.world_director = SimpleNamespace(decide=lambda context: plan if context['phase'] == 'npc_agency' else WorldPlan())
        assert game.runner.submit(CASES['friend'][0]['prompt']).status == 'completed'
        ignored = dict(prompt='Ali tem uma árvore.', focus='uma árvore', initiative='listen', reply=None,
            goal='Ainda aguardar uma resposta.', waiting_for='Permissão para sugerir.')
        configure_friend(game, ignored)
        result = game.runner.submit(ignored['prompt'])
        assert result.status == 'failed' and game.flow.session.agency.intents['lia']['waits_used'] == 1
        assert any(p['text'] == 'Você quer uma sugestão?' and not p['resolved']
                   for p in game.flow.session.conversations.view('lia')[0]['points'])


def test_boy_can_thank_and_leave_after_wait_without_a_request_or_material_gift():
    with open_situation(load_situation('encontro-com-garoto'), allow_unconfigured=True) as game:
        session, row = game.flow.session, CASES['boy']
        initial = deepcopy(session.encounter.states)
        relation = session.relationships.get('street_boy', 'player')
        position = session.state.position
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt, 'wait'),)), prompt))
        def director(context):
            if context['phase'] != 'npc_agency':
                return WorldPlan()
            assert any(m['id'] == 'street_boy:prior_coin' for m in context['knowledge'])
            target = context['observations']['departure_targets'][0]
            return decision('street_boy', 'leave', [
                WorldAction('street_boy', 'say', row['thanks'], memory_ids=('street_boy:prior_coin',),
                    conversation=ConversationUpdate(status='closed', reason=row['close_reason'])),
                WorldAction('street_boy', 'move', 'Segue para a alameda.',
                    destination=Position(target['position'][0]-1, target['position'][1]-1))], 'Voltar aos próprios afazeres.')
        game.flow.world_director = SimpleNamespace(decide=director)
        game.flow.narrator = SimpleNamespace(narrate=narrator)
        result = game.runner.submit(row['wait_prompt'])
        assert result.status == 'completed' and not result.report.failures
        assert [r.stage for r in result.requests] == ['interpret', 'world', 'npc_agency', 'narrate']
        assert not any(e['operation'] == 'speak' for e in result.report.events)
        assert session.scene.area_at(session.creatures[0].position).id == 'north_lane'
        assert any(e['operation'] == 'move' and e['traveled_meters'] == 4.5 for e in result.report.world_events)
        assert session.state.position == position and session.encounter.states == initial
        assert session.conversations.view('street_boy')[0]['status'] == 'closed'
        assert 'street_boy' not in session.agency.intents
        assert session.relationships.get('street_boy', 'player') == relation
        assert not session.relationships.history('street_boy') and not session.social.opinions
        assert not session.encounter.roller.used
        assert game.runner.reset().status == 'completed'
        assert session.creatures[0].position == Position(4, 3)
        assert session.conversations.view('street_boy')[0]['status'] == 'active'
        assert session.relationships.get('street_boy', 'player') == relation


def test_boy_offers_known_directions_after_hearing_a_need_without_formal_proposal():
    with open_situation(load_situation('encontro-com-garoto'), allow_unconfigured=True) as game:
        session, row = game.flow.session, CASES['boy']
        position = session.state.position
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(ActionPlan((
            NarrativeIntent(prompt, 'speak', conversation=ConversationUpdate(focus='poço público')),)), prompt))
        def director(context):
            if context['phase'] != 'npc_agency':
                return WorldPlan()
            assert any(m['id'] == 'street_boy:well_route' for m in context['knowledge'])
            return decision('street_boy', 'respond', [WorldAction('street_boy', 'say', row['directions'],
                memory_ids=('street_boy:well_route',))], 'Oferecer orientação sem impor companhia.')
        game.flow.world_director = SimpleNamespace(decide=director)
        game.flow.narrator = SimpleNamespace(narrate=narrator)
        result = game.runner.submit(row['need_prompt'])
        assert result.status == 'completed' and not result.report.failures
        known = [m for m in session.knowledge.store.active('player') if m.claim.subject_id == 'public_well']
        assert len(known) == 1 and known[0].source.kind == 'report' and known[0].source.actor_id == 'street_boy'
        assert not session.conversations.view('street_boy')[0]['proposals']
        assert session.state.position == position and session.creatures[0].position == Position(4, 3)
        assert not session.social.opinions and not session.encounter.roller.used


@pytest.mark.parametrize('situation_id,actor,close,initiative', [
    ('encontro-com-garoto', 'street_boy', True, 'leave'),
    ('encontro-com-garoto', 'street_boy', False, 'leave'),
    ('encontro-com-garoto', 'street_boy', True, 'close'),
    ('conversa-com-amiga', 'lia', True, 'leave'),
])
def test_departure_rejects_unperceived_target_missing_goodbye_or_unsupported_movement(
        situation_id, actor, close, initiative):
    with open_situation(load_situation(situation_id), allow_unconfigured=True) as game:
        session = game.flow.session
        origin = session.perception.observer(actor).position
        plan = decision(actor, initiative, [WorldAction(actor, 'say', 'Até depois.',
            conversation=ConversationUpdate(status='closed' if close else None, reason='Até depois.' if close else None)),
            WorldAction(actor, 'move', 'Tenta seguir.', destination=Position(2, 2))], 'Encerrar e seguir o próprio caminho.')
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt, 'wait'),)), prompt))
        game.flow.world_director = SimpleNamespace(decide=lambda context: plan if context['phase'] == 'npc_agency' else WorldPlan())
        game.flow.narrator = SimpleNamespace(narrate=narrator)
        result = game.runner.submit('Aguardo um instante.')
        assert result.status == 'failed'
        assert session.perception.observer(actor).position == origin
        assert session.conversations.view(actor)[0]['status'] == 'active'
        assert not result.report.world_events  # Despedida inválida não é executada antes da rejeição.
