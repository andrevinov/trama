"""Reprodução da autorização real e fluxo oficial com decisões locais fixas."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import sourced_plan
from trama.agency import IntentDecision
from trama.application.authorization import validate_player_plan
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.scenarios import load_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_game
from trama.conversation_state import ConversationUpdate, ConversationPoint, ProposalUpdate, ProposalTerm
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_plan

ROOT = Path(__file__).resolve().parents[2]
LIVE = runpy.run_path(str(ROOT / 'tests/live/test_conversation_focus_live.py'))
SOURCE = json.loads((ROOT / 'tests/fixtures/conversation_punctuation/regression_source.json').read_text())
PROMPT = next(r['record']['data']['text'] for r in SOURCE if r['record']['event'] == 'conversation.player_message')
RAW = [r['record']['data']['output_text'] for r in SOURCE if r['record']['event'] == 'ai.response_payload']
PARTS = [
    ['A posição de Auren é a mesma de antes da invasão, general.',
     'Queremos a manutenção do Tratado da Ponte, a reintegração dos cidadãos removidos e a convivência pacífica entre nossos reinos.',
     'Acredito que esse também é o desejo de Valdren e de seus cidadãos.'],
    ['Proponho uma trégua de trinta dias com recuo simultâneo.',
     'O recuo só começaria se houver fiscalização aceita pelos dois lados.'],
    ['Não aceito uma retirada unilateral.',
     'Proponho trinta dias de trégua, não trezentos, com recuo simultâneo apenas se houver fiscalização.'],
]


@pytest.mark.parametrize('raw', RAW, ids=['primeira-tentativa-real', 'correcao-real'])
def test_both_recorded_plans_authorize_against_the_original_message_without_rewriting(raw):
    context = Conversation(load_session(LIVE['SCENARIO'])).interpretation_context()
    plan = parse_plan(raw, require_sources=True)
    assert plan.steps[0].conversation.points[1].text not in PROMPT
    validate_player_plan(PROMPT, plan, context)


def test_interpreter_receives_a_precise_correction_for_a_genuinely_invented_point():
    broken = json.loads(RAW[0])
    broken['steps'][0]['text'] += ' Aceito entregar a Bavária.'
    broken['steps'][0]['conversation']['points'].append(dict(kind='statement', text='Aceito entregar a Bavária.'))
    client = Mock()
    client.responses.create.side_effect = [SimpleNamespace(status='completed', output=[], output_text=json.dumps(broken)),
                                          SimpleNamespace(status='completed', output=[], output_text=RAW[0])]
    context = Conversation(load_session(LIVE['SCENARIO'])).interpretation_context()
    plan = OpenAIIntentInterpreter(client).interpret(PROMPT, context)
    assert len(plan.steps[0].conversation.points) == 3
    payload = json.loads(client.responses.create.call_args_list[1].kwargs['input'])
    assert all(t in payload['correction']['reason'] for t in (
        'Ponto 4 da conversa', 'mensagem original do jogador', 'Aceito entregar a Bavária.'))


@pytest.mark.parametrize('index,case', list(enumerate(LIVE['PUNCTUATION_CASES'])),
                         ids=[c['id'] for c in LIVE['PUNCTUATION_CASES']])
def test_quoted_speeches_execute_through_the_runner_and_live_oracles_reject_lost_content(index, case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with open_game(LIVE['SCENARIO'], allow_unconfigured=True) as game:
        parts = PARTS[index]
        def interpret(prompt, context):
            proposal = ProposalUpdate('offer', terms=tuple(ProposalTerm(None, 'condition', p)
                for p in parts if 'trégua' in p or 'fiscalização' in p)) if case['proposal'] else None
            return sourced_plan(ActionPlan((NarrativeIntent(' '.join(parts), 'speak', conversation=ConversationUpdate(
                target_ids=('general_voss',), focus='posição e condições de paz',
                points=tuple(ConversationPoint('statement', p) for p in parts), proposal=proposal)),)), prompt)
        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=lambda c: WorldPlan() if c['phase'] != 'npc_agency' else WorldPlan(
            (WorldReaction(0, None, (WorldAction('general_voss', 'say', 'Ouvi sua posição. Que garantias oferece?',
                conversation=ConversationUpdate(target_ids=('player',), points=(
                    ConversationPoint('question', 'Que garantias oferece?'),))),)),),
            intent=IntentDecision('general_voss', 'Avaliar garantias.', 'Perguntar.', 'Garantias.', 'clarify', 'Faltam garantias concretas.')))
        game.flow.narrator = SimpleNamespace(narrate=lambda c: Speech(on='A conversa executada é narrada.')
            if c['allow_on'] else Speech(off='Consulta às falas executadas.'))
        before = LIVE['snapshot'](game.flow.session)
        assert game.runner.start().status == 'completed'
        result = game.runner.submit(case['prompt'])
        after = LIVE['snapshot'](game.flow.session)
        assert not LIVE['evaluate_punctuation'](case, before, after, result)
        changed_events = [dict(e, text='A proposta foi alterada.') if e['operation'] == 'speak' else e for e in result.report.events]
        broken = replace(result, report=replace(result.report, events=tuple(changed_events)))
        assert LIVE['evaluate_punctuation'](case, before, after, broken)
        if case['required_terms']:
            broken_state = deepcopy(after)
            for proposal in broken_state['conversations']['player'][0]['proposals']:
                for version in proposal['versions']:
                    version['terms'] = []
            assert LIVE['evaluate_punctuation'](case, before, broken_state, result)
        off = game.runner.submit(case['off'])
        assert not LIVE['evaluate_punctuation'](case, after, LIVE['snapshot'](game.flow.session), off, off=True)
