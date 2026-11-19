"""Foco resumido não bloqueia fala; citações e compromissos mantêm lastro literal."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.agency import IntentDecision
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_game
from trama.conversation_state import ConversationState, ConversationUpdate, ConversationPoint, ProposalTerm, ProposalUpdate, ConversationStateError
from trama.infrastructure.openai_intent_interpreter import parse_plan
from trama.infrastructure.openai_world_director import parse_world_plan

ROOT = Path(__file__).resolve().parents[2]
LIVE = runpy.run_path(str(ROOT / 'tests/live/test_conversation_focus_live.py'))
SOURCE = json.loads((ROOT / 'tests/fixtures/conversation_focus/regression_source.json').read_text())
RAW = [r['record']['data']['output_text'] for r in SOURCE if r['record']['event'] == 'ai.response_payload']


@pytest.mark.parametrize('phase,index', [('player_action', 1), ('npc_agency', 2)])
def test_original_rejected_responses_execute_without_rewriting_their_focus(phase, index, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    case = LIVE['CASES'][0]
    with open_game(LIVE['SCENARIO'], allow_unconfigured=True) as game:
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context: parse_plan(RAW[0], require_sources=True))
        game.flow.world_director = SimpleNamespace(decide=lambda context:
            parse_world_plan(RAW[index]) if context['phase'] == phase else WorldPlan())
        game.flow.narrator = SimpleNamespace(narrate=lambda context:
            Speech(on='As falas executadas são narradas.') if context['allow_on'] else Speech(off='Consulta às falas registradas.'))
        before = LIVE['snapshot'](game.flow.session)
        result = game.runner.submit(case['prompt'])
        after = LIVE['snapshot'](game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result)
        expected = json.loads(RAW[index])['reactions'][0]['actions'][0]['conversation']['focus']
        frame = after['conversations']['player'][0]
        assert frame['focus'] == expected
        assert frame['points'] and not frame['proposals']
        assert any(e['operation'] == 'gesture' and e['received'] for e in result.report.events)
        broken = replace(result, report=replace(result.report, world_events=tuple(
            e for e in result.report.world_events if e['operation'] != 'say')))
        assert LIVE['evaluate'](case, before, after, broken)
        off = game.runner.submit(case['off'])
        assert not LIVE['evaluate'](case, after, LIVE['snapshot'](game.flow.session), off, off=True)
        changed = deepcopy(after)
        changed['state']['position'] = [1, 1]
        assert LIVE['evaluate'](case, after, changed, off, off=True)
        assert game.runner.reset().status == 'completed'
        assert not game.flow.session.conversations.view('player')


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_oracles_detect_speech_missing_terms_and_off_changes_offline(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with open_game(LIVE['SCENARIO'], allow_unconfigured=True) as game:
        def interpret(prompt, context):
            proposal = ProposalUpdate('offer', terms=(ProposalTerm(None, 'condition',
                'trégua de trinta dias, com recuo simultâneo das nossas tropas'),)) if case['proposal'] else None
            return sourced_plan(ActionPlan((NarrativeIntent(prompt, 'speak', conversation=ConversationUpdate(
                target_ids=('general_voss',), focus='abertura de negociação' if case['proposal'] else 'reencontro cordial',
                proposal=proposal)),)), prompt)
        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.narrator = SimpleNamespace(narrate=lambda c: Speech(on='Você está no conselho.')
            if c['allow_on'] else Speech(off='Consulta aos termos efetivamente falados.'))
        game.flow.world_director = SimpleNamespace(decide=lambda c: WorldPlan() if c['phase'] != 'npc_agency' else WorldPlan(
            (WorldReaction(0, None, (WorldAction('general_voss', 'say', 'Lembro de você. Como pretende garantir a retirada?',
                conversation=ConversationUpdate(target_ids=('player',), focus='garantias para um novo acordo',
                    points=(ConversationPoint('question', 'Como pretende garantir a retirada?'),))),)),),
            intent=IntentDecision('general_voss', 'Obter garantias.', 'Perguntar sobre garantias.', 'Resposta do interlocutor.',
                'clarify', 'A pergunta precisa de uma resposta do interlocutor.')))
        before = LIVE['snapshot'](game.flow.session)
        initial = game.runner.start()
        after = LIVE['snapshot'](game.flow.session)
        assert not LIVE['evaluate'](case, before, after, initial, initial=True)
        result = game.runner.submit(case['prompt'])
        before, after = after, LIVE['snapshot'](game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result)
        if case['proposal']:
            broken = deepcopy(after)
            broken['conversations']['player'][0]['proposals'][0]['versions'][0]['terms'][0]['text'] = 'recuo'
            assert LIVE['evaluate'](case, before, broken, result)
        assert any(p['kind'] == 'question' and not p['resolved'] for p in after['conversations']['player'][0]['points'])
        off = game.runner.submit(case['off'])
        assert not LIVE['evaluate'](case, after, LIVE['snapshot'](game.flow.session), off, off=True)


@pytest.mark.parametrize('field', ['point', 'term', 'reason', 'boundary'])
def test_semantic_focus_does_not_relax_literal_evidence(field):
    update = ConversationUpdate(focus='garantias de segurança')
    if field == 'point':
        update = replace(update, points=(ConversationPoint('question', 'Vai retirar suas tropas?'),))
    elif field == 'term':
        update = replace(update, proposal=ProposalUpdate('offer', terms=(ProposalTerm(None, 'condition', 'Devolver a Bavária.'),)))
    elif field == 'reason':
        update = replace(update, status='closed', reason='Até a próxima.')
    else:
        update = replace(update, target_ids=('player',), romance_boundary='declined', boundary_text='Não quero romance.')
    with pytest.raises(ConversationStateError, match='não pertence à fala executada'):
        update.validate_source('Bom dia.', actor_id='general_voss', player_id='player')


def test_focus_is_bounded_and_does_not_grant_objectives_to_the_player():
    with pytest.raises(ConversationStateError):
        ConversationUpdate(focus='x'*161)
    with pytest.raises(ConversationStateError, match='objetivos privados'):
        ConversationUpdate(focus='negociação', goal='Aceitar a proposta.').validate_source(
            'Olá.', actor_id='player', player_id='player')


def test_live_redundant_active_response_is_a_continuation_without_a_lifecycle_event(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    rows = json.loads((ROOT / 'tests/fixtures/conversation_focus/active_status_source.json').read_text())
    answers = [r['record']['data']['output_text'] for r in rows if r['record']['event'] == 'ai.response_payload']
    with open_game(LIVE['SCENARIO'], allow_unconfigured=True) as game:
        game.flow.interpreter = SimpleNamespace(interpret=lambda p, c: parse_plan(answers[1], require_sources=True))
        game.flow.world_director = SimpleNamespace(decide=lambda c: parse_world_plan(answers[2])
            if c['phase'] == 'player_action' else WorldPlan())
        game.flow.narrator = SimpleNamespace(narrate=lambda c: Speech(on='A resposta efetivamente falada é narrada.'))
        before = LIVE['snapshot'](game.flow.session)
        case = LIVE['CASES'][1]
        result = game.runner.submit(case['prompt'])
        after = LIVE['snapshot'](game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result)
        record = game.flow.session.conversations._records[0]
        assert record['contributions'][-1]['actor_id'] == 'general_voss'
        assert record['contributions'][-1]['status'] is None and record['contributions'][-1]['reason'] is None


@pytest.mark.parametrize('previous', ['suspended', 'closed'])
def test_active_without_literal_reason_cannot_resume_a_suspended_or_closed_conversation(previous):
    state, cid = ConversationState().prepare('player', 'Olá.', ('general_voss',),
        ConversationUpdate(target_ids=('general_voss',)), event_id='greeting', player_id='player',
        actor_ids={'player', 'general_voss'})
    state, _ = state.prepare('general_voss', 'Paremos.', ('player',),
        ConversationUpdate(status=previous, reason='Paremos.'), event_id='pause', player_id='player',
        actor_ids={'player', 'general_voss'})
    before = deepcopy(state.view('player'))
    with pytest.raises(ConversationStateError, match='motivo literal'):
        state.prepare('general_voss', 'Olá.', ('player',), ConversationUpdate(conversation_id=cid, status='active'),
            event_id='bad-resume', player_id='player', actor_ids={'player', 'general_voss'})
    assert state.view('player') == before
    resumed, _ = state.prepare('general_voss', 'Retomemos.', ('player',),
        ConversationUpdate(conversation_id=cid, status='active', reason='Retomemos.'), event_id='resume',
        player_id='player', actor_ids={'player', 'general_voss'})
    assert resumed.view('player')[0]['status'] == 'active'
