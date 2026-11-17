"""Memórias e relatos por NPC: interação completa desde situação preparada."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import pytest

from trama.application.game_flow import FlowStage
from trama.application.game_runner import RunStatus
from trama.application.situations import load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/knowledge/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Autorize a bateria focada descrita em conhecimento-live.md.')]


def snapshot(session):
    return {**situation_state(session), 'objects': {
        o.id: [o.position.x + 1, o.position.y + 1] for o in session.scene.objects}}


def memories(state, owner):
    return [m for m in state['knowledge']['memories'] if m['owner_id'] == owner
            and m['claim']['subject_id'] == 'archive_key' and m['claim']['predicate'] == 'location']


def evaluate(case, index, before, after, result):
    errors = []
    if result.status != RunStatus.COMPLETED or result.awaiting_reaction or result.error:
        errors.append('A interação não concluiu pelo runner.')
    for field in ('position', 'objects', 'resources', 'budgets', 'passages', 'combat', 'parley'):
        if after[field] != before[field]:
            errors.append(f'A conversa alterou {field}.')
    if any(r.stage == FlowStage.NPC_TURN for r in result.requests) or result.report.failures:
        errors.append('Criou turno de combate ou falha na conversa.')
    events = [e for e in result.report.world_events if e['operation'] == 'say' and e['actor_id'] == 'archivist']
    if not events:
        errors.append('O arquivista não respondeu à pergunta/fala.')
    shared = [m for e in events for m in e.get('shared_memories', []) if m['claim']['subject_id'] == 'archive_key']
    mode = case['expected']
    if mode == 'unknown':
        if shared or memories(after, 'player') or memories(after, 'archivist'):
            errors.append('Concedeu conhecimento da chave ao NPC desinformado ou ao jogador.')
        text = ' '.join(e['text'] for e in events).casefold()
        if not re.search(r'não (sei|vi|tenho|conheço|lembro|posso afirmar)|desconheço|nunca vi|sem (informação|certeza)', text):
            errors.append('A resposta não reconheceu a falta de informação; revisar texto.')
    elif index == 0:
        if not any(m['id'] == 'archivist:key-on-desk' and m['source']['kind'] == 'observation'
                   and m['claim']['value'] == 'position:13,3' for m in shared):
            errors.append('Não fundamentou a resposta na observação inicial do próprio NPC.')
        if not any(m['source']['kind'] == 'report' and m['source']['actor_id'] == 'archivist'
                   and m['source']['memory_id'] == 'archivist:key-on-desk' for m in memories(after, 'player')):
            errors.append('O jogador não aprendeu um relato com origem no arquivista.')
        if not any(m['source']['actor_id'] == 'archivist' for m in memories(after, 'apprentice')):
            errors.append('O aprendiz ao alcance não recebeu o relato ouvido.')
        if mode == 'stale':
            if after['objects']['archive_key'] != [18, 3] or any(m['claim']['value'] == 'position:18,3' for m in memories(after, 'archivist')):
                errors.append('Atualizou memória pela localização oculta atual do objeto.')
    elif index == 1:
        if not any(m['source']['kind'] == 'report' and m['source']['actor_id'] == 'player'
                   and m['claim']['value'] == 'position:18,3' for m in memories(after, 'archivist')):
            errors.append('A afirmação comunicada pelo jogador não virou relato atribuído a ele.')
        if not any(m['id'] == 'archivist:key-on-desk' for m in memories(after, 'archivist')):
            errors.append('O relato apagou a observação anterior.')
    else:
        if not any(m['source']['kind'] == 'report' and m['source']['actor_id'] == 'player'
                   and m['claim']['value'] == 'position:18,3' for m in shared):
            errors.append('Não usou o relato recente atribuído ao jogador na resposta seguinte.')
    if not result.reply or not result.reply.on.strip():
        errors.append('Faltou a narração da conversa executada.')
    return errors


def record(result, game):
    return {'status': result.status, 'interaction_id': game.flow.interaction_id,
            'requests': [{'request_id': r.request_id, 'stage': r.stage, 'context': dict(r.context),
                'prompt': r.prompt, 'applied': r.applied,
                **({'error': str(r.result)} if isinstance(r.result, Exception) else {'result': asdict(r.result)})}
                for r in result.requests],
            'report': result.report.context(), 'reply': asdict(result.reply) if result.reply else None,
            'error': str(result.error) if result.error else None, 'state': snapshot(game.flow.session)}


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_npc_knowledge(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_KNOWLEDGE_ARTIFACTS', ROOT / 'logs/live/knowledge')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    reserved = int(os.environ.get('TRAMA_KNOWLEDGE_CALLS_RESERVED', '0'))
    if not 0 <= reserved <= case['max_sdk_calls']:
        raise ValueError('Reserva de chamadas inválida.')
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'] - reserved)
    evidence = {'scope': 'game_flow_from_prepared_situation', 'case': case, 'situation': situation.data,
                'session_id': uuid4().hex, 'outcome': 'failed', 'runs': [],
                'narrative_review': 'Revisar desconhecimento, ocasião passada, atribuição de relatos e ausência de informação oculta inventada; referências não provam toda a prosa.'}
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['initial'] = before = snapshot(game.flow.session)
            # Avalia as mensagens a partir da situação, sem pagar abertura extra.
            for index, prompt in enumerate(case['messages']):
                result = game.runner.submit(prompt)
                evidence['runs'].append(record(result, game))
                after = snapshot(game.flow.session)
                errors = evaluate(case, index, before, after, result)
                evidence['runs'][-1]['errors'] = errors
                assert not errors, '; '.join(errors)
                before = after
            assert not roller.used and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        evidence['dice_used'], evidence['call_budget'] = roller.used, budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
