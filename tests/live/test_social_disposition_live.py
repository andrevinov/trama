"""Disposição social por pedido, no fluxo real da aplicação e com IA real."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from trama.application.game_flow import FlowStage
from trama.application.game_runner import RunStatus
from trama.application.situations import load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/social/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Autorize a bateria descrita em disposicao-live.md.')]


def evaluate(case, index, before, after, result):
    errors = []
    if result.status != RunStatus.COMPLETED or result.error or result.awaiting_reaction:
        errors.append('O runner não concluiu a interação.')
    if result.report.failures or any(r.stage == FlowStage.NPC_TURN for r in result.requests):
        errors.append('A conversa gerou falha ou turno de NPC.')
    for field in ('position', 'creatures', 'resources', 'budgets', 'passages', 'inventory', 'combat', 'mode'):
        if before[field] != after[field]:
            errors.append(f'A conversa alterou {field}.')
    influence = [e for e in result.report.world_events if e['operation'] == 'influence']
    # Não avaliar outra vez é válido para informação irrelevante/reformulação.
    if not influence and ((case['expected'] == 'relevance' and index in {1, 2})
                          or (case['expected'] == 'reward' and index == 2)):
        if not before['social']['decisions']:
            errors.append('Não existe decisão inicial para reutilizar.')
        if before['social'] != after['social'] or before['parley'] != after['parley']:
            errors.append('Mudou a decisão sem avaliação de nova evidência relevante.')
        if not result.reply or not result.reply.on.strip():
            errors.append('Faltou continuidade narrativa da conversa.')
        return errors
    if len(influence) != 1:
        return [*errors, 'Faltou uma avaliação social única do pedido.']
    event = influence[0]
    verdict = event.get('disposition', {})
    if verdict.get('goal') != 'listen' or verdict.get('target_id') not in {'player', 'guard_1'}:
        errors.append('O pedido de escuta virou outro tipo de concessão.')
    components = verdict.get('components', {})
    if set(components) != {'alignment', 'persona', 'memories'} or sum(components.values()) != verdict.get('total'):
        errors.append('Faltou decomposição auditável do resultado.')
    if event.get('willingness') == 'hesitant':
        if not event.get('dice') or event.get('skill') != 'persuasion' or event.get('dc') != 15:
            errors.append('Hesitação não resolveu Persuasão com dado real.')
    elif 'dice' in event:
        errors.append('Rolou para NPC disposto/indisposto.')
    accepted = event.get('accepted')
    parley = after['parley'] or {}
    if parley.get('status') != ('listening' if accepted else 'pending'):
        errors.append('A abordagem não preservou o resultado limitado à escuta.')
    if accepted and (not parley.get('concession') or parley['concession'].get('goal') != 'listen'
                     or not parley['concession'].get('conditions')):
        errors.append('Escuta sem limites explícitos de custódia/posição.')
    says = [e for e in result.report.world_events if e['operation'] == 'say' and e['actor_id'] == 'guard_1']
    if len(says) != 1 or says[0]['text'] != event.get('response_text'):
        errors.append('O NPC não emitiu exclusivamente a resposta escolhida pelo código.')
    expected = case['expected']
    if expected in {'limited_listen', 'willing', 'lawful', 'chaotic'} and not accepted:
        errors.append('O caso claro de escuta limitada foi recusado.')
    required = {'willing': 'willing', 'unwilling': 'unwilling', 'lawful': 'willing', 'chaotic': 'hesitant'}.get(expected)
    if required and event.get('willingness') != required:
        errors.append(f'Esperado {required}, obtido {event.get("willingness")}.')
    if expected in {'lawful', 'chaotic'} and components.get('alignment') != (1 if expected == 'lawful' else -1):
        errors.append('Não distinguiu o mesmo apelo ao protocolo entre os alinhamentos.')
    if expected == 'reward':
        if index == 0 and (event.get('willingness') != 'hesitant' or accepted):
            errors.append('Sem recompensa, o guarda corrupto deveria hesitar e falhar no dado fixado.')
        if index == 1 and (event.get('willingness') != 'willing' or not accepted or not event.get('reevaluated')):
            errors.append('A nova recompensa não mudou a disposição do guarda corrupto.')
        if index == 2 and (not event.get('reused') or event.get('reevaluated')):
            errors.append('Repetir a recompensa criou outra avaliação.')
    if expected == 'relevance':
        if index in {1, 2} and (not event.get('reused') or event.get('reevaluated')):
            errors.append('Reformulação/roupa azul provocou nova avaliação.')
        if index == 3:
            evidence = verdict.get('memory_effects', [])
            if not event.get('reevaluated') or not event.get('relevant_change'):
                errors.append('A nova alegação de nobreza não provocou reavaliação.')
            if not any(e.get('source', {}).get('kind') == 'report' and e['source'].get('actor_id') == 'player'
                       and e['claim']['subject_id'] == 'player' and e.get('effect') == 1 for e in evidence):
                errors.append('A alegação nova não pesou como relato não confirmado do jogador.')
    if not result.reply or not result.reply.on.strip():
        errors.append('Faltou narração do resultado.')
    return errors


def record(result, game):
    return {'status': result.status, 'interaction_id': game.flow.interaction_id,
            'requests': [{'request_id': r.request_id, 'stage': r.stage, 'context': dict(r.context),
                'prompt': r.prompt, 'applied': r.applied,
                **({'error': str(r.result)} if isinstance(r.result, Exception) else {'result': asdict(r.result)})}
                for r in result.requests],
            'report': result.report.context(), 'reply': asdict(result.reply) if result.reply else None,
            'state': situation_state(game.flow.session), 'error': str(result.error) if result.error else None}


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_social_disposition(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_SOCIAL_ARTIFACTS', ROOT / 'logs/live/social')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    reserved = int(os.environ.get('TRAMA_SOCIAL_CALLS_RESERVED', '0'))
    if not 0 <= reserved <= case['max_sdk_calls']:
        raise ValueError('Reserva de chamadas inválida.')
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'] - reserved)
    evidence = {'case': case, 'situation': situation.data, 'scope': 'game_flow_from_prepared_situation',
                'session_id': uuid4().hex, 'runs': [], 'outcome': 'failed',
                'narrative_review': 'Conferir escuta com custódia, recusa sem ataque, recompensa sem transferência, nobreza como alegação e nenhuma informação privada revelada por onisciência.'}
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['initial'] = before = situation_state(game.flow.session)
            for index, prompt in enumerate(case['messages']):
                result = game.runner.submit(prompt)
                evidence['runs'].append(record(result, game))
                after = situation_state(game.flow.session)
                errors = evaluate(case, index, before, after, result)
                evidence['runs'][-1]['errors'] = errors
                assert not errors, '; '.join(errors)
                before = after
            assert not roller.pending and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        evidence['dice_used'], evidence['call_budget'] = roller.used, budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
