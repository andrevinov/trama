"""Comunicação gestual pelo fluxo oficial; execução paga somente se autorizada."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from trama.application.situations import load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/gestures/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Requer autorização: docs/sistema/qualidade/gestos-live.md.')]


def evaluate(case, before, after, result):
    errors = []
    if result.status != 'completed' or result.error or result.awaiting_reaction:
        return ['Fluxo incompleto: ' + str(result.error)]
    for key in ('position', 'spent_meters', 'remaining_meters', 'combat', 'mode', 'creatures', 'resources',
                'budgets', 'inventory', 'discovered', 'weapons', 'passages', 'prisoner_free', 'escaped'):
        if before[key] != after[key]:
            errors.append('Alteração não autorizada: ' + key)
    if not result.reply or not (result.reply.on or result.reply.off):
        errors.append('Faltou explicar o resultado.')
    if case['blocked']:
        if result.report.events or result.report.world_events:
            errors.append('Sinal impossível provocou ação ou resposta de NPC.')
        if not result.report.failures or result.report.failures[0].code != 'gesture_not_visible':
            errors.append('Não registrou falta de contato visual.')
        if 'linha de visão' not in (result.report.stop_reason or ''):
            errors.append('Não explicou o impedimento geométrico.')
        return errors
    if result.report.failures:
        errors.append('A comunicação falhou mecanicamente.')
    gestures = [e for e in result.report.events if e['operation'] == 'gesture']
    if len(gestures) != 1 or len(result.report.events) != 1:
        return errors + ['Sinal omitido ou convertido em fala/movimento/detalhe narrativo.']
    event = gestures[0]
    if event['target_id'] != case['target'] or event['received'] is not case['received'] or event['subtle'] is not case['subtle']:
        errors.append('Destinatário ou recepção incorretos.')
    if event['heard_by'] or event['understood'] is not None:
        errors.append('O gesto virou som ou compreensão automática.')
    responses = [e for e in result.report.world_events if e.get('actor_id') == case['target'] and e['operation'] in {'say','wait'}]
    if case['received'] and not responses:
        errors.append('O destinatário percebido não teve decisão de resposta.')
    if not case['received'] and responses:
        errors.append('O NPC reagiu a uma piscadela que não percebeu.')
    for request in result.requests:
        if request.stage == 'npc_agency' and 'message' in json.dumps(request.context['observations']['communications']):
            errors.append('A intenção privada virou conhecimento do destinatário.')
    judgments = [j for r in result.requests if r.stage == 'world'
                 for j in r.context['world']['adjudication']['requests'] if j['kind'] == 'visual_signal']
    if bool(judgments) is not case['subtle']:
        errors.append('Avaliação contextual indevida ou ausente para o gesto sutil.')
    return errors


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_gestural_communication(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_GESTURE_ARTIFACTS', ROOT / 'logs/live/gestures')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'])
    evidence = dict(case=case, situation=situation.data, session_id=uuid4().hex, outcome='failed',
        narrative_review='Conferir impossibilidade visual explicitada, percepção sem audição do gesto, nenhum entendimento/segredo/cooperação inventado, fala ou silêncio realmente decidido pelo destinatário; piscadela distante não notada. Não basta JSON válido ou prosa não vazia.')
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['before'] = before = situation_state(game.flow.session)
            evidence['dice_before'] = list(roller.used)
            result = game.runner.submit(case['prompt'])
            evidence['interaction_id'] = game.flow.interaction_id
            evidence['requests'] = [dict(stage=r.stage, context=dict(r.context), prompt=r.prompt,
                request_id=r.request_id, result=str(r.result) if isinstance(r.result, Exception) else asdict(r.result)) for r in result.requests]
            evidence['report'] = result.report.context()
            evidence['reply'] = asdict(result.reply) if result.reply else None
            evidence['after'] = after = situation_state(game.flow.session)
            evidence['errors'] = evaluate(case, before, after, result)
            assert not evidence['errors'], '; '.join(evidence['errors'])
            assert not roller.pending and roller.used == evidence['dice_before']
            assert not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        evidence['call_budget'], evidence['dice_used'] = budget.context(), roller.used
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
