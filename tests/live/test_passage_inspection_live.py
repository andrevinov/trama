"""Inspeções pelo fluxo oficial; somente a bateria nova, com autorização separada."""

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
CASES = json.loads((ROOT / 'tests/fixtures/passage_inspection/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Autorização e limites: docs/sistema/qualidade/inspecao-live.md.')]


def observe(session):
    return dict(state=situation_state(session),
                passages=session.interpreter_context()['map']['scene']['passages'],
                lock_labels=session.map_view()['passage_lock_labels'])


def evaluate(case, before, after, result):
    """Critérios definidos pelos casos, sem recalcular regras do executor."""
    errors = []
    if result.status != 'completed' or result.error or result.awaiting_reaction:
        return ['Fluxo incompleto ou com erro: ' + str(result.error)]
    for key in ('position', 'spent_meters', 'remaining_meters', 'dash_used', 'mode', 'combat', 'creatures',
                'resources', 'budgets', 'inventory', 'discovered', 'clothing', 'weapons', 'passages',
                'prisoner_awake', 'prisoner_free', 'escaped', 'disguise', 'guard_alert', 'sword_concealed'):
        if before['state'][key] != after['state'][key]:
            errors.append('Efeito físico não autorizado: ' + key)
    if before['state']['sensing']['stealth_total'] != after['state']['sensing']['stealth_total']:
        errors.append('A inspeção perdeu ou rerrolou a furtividade existente.')
    if any(e['operation'] in {'hide', 'check', 'search', 'start_conflict', 'open', 'unlocked', 'attack'}
           for e in (*result.report.events, *result.report.world_events)):
        errors.append('Houve operação ou teste não solicitado.')
    if result.report.world_events:
        errors.append('A inspeção isolada produziu resposta/detecção não prevista nas condições.')
    if not result.reply or not (result.reply.on or result.reply.off):
        errors.append('Faltou narração ou esclarecimento.')
    stages = [r.stage for r in result.requests]
    if case['target'] is None:
        if stages != ['interpret', 'narrate'] or result.report.events or result.report.progress:
            errors.append('O esclarecimento provocou avaliação do Mundo ou ação.')
        if before != after:
            errors.append('O esclarecimento alterou o estado ou o conhecimento.')
        if not result.report.failures or result.report.failures[0].code != 'clarification_required':
            errors.append('Faltou pedir a identificação da passagem.')
        return errors
    if result.report.failures or stages != ['interpret', 'world', 'narrate']:
        errors.append('A inspeção não percorreu o fluxo completo esperado.')
    events = result.report.events
    if len(events) != 1 or events[0]['operation'] != 'inspect_passage':
        errors.append('A inspeção foi omitida ou trocada por outra ação.')
    else:
        event = events[0]
        for key, expected in dict(target_id=case['target'], method=case['method'], locked=case['locked'],
                                  is_open=False, physical_change=False).items():
            if event.get(key) != expected:
                errors.append('Resultado de inspeção incorreto: ' + key)
        if event.get('volume') != ('quiet' if case['method'] == 'mechanism' else None):
            errors.append('A inspeção não respeitou a ausência de ruído/manipulação.')
    known = next(p['locked'] for p in after['passages'] if p['id'] == case['target'])
    if known is not case['locked']:
        errors.append('O conhecimento da fechadura não corresponde ao que foi conferido.')
    if case['method'] == 'visual' and before != after:
        errors.append('Olhar provocou alteração do estado ou revelou informação oculta.')
    narration = next((r.context for r in result.requests if r.stage == 'narrate'), {})
    if narration.get('execution', {}).get('events') != list(events):
        errors.append('O narrador não recebeu os fatos da inspeção executada.')
    return errors


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_passage_inspection(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_INSPECTION_ARTIFACTS', ROOT / 'logs/live/passage_inspection')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'])
    evidence = dict(case=case, situation=situation.data, session_id=uuid4().hex, outcome='failed',
        narrative_review='Conferir se a prosa informa o trancamento apenas quando conhecido; visual distingue fechada de trancada; nenhum abrir/destrancar, deslocamento, novo teste ou perda de furtividade inventados; esclarecimento pergunta qual passagem sem avanço do Mundo.')
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['before'] = before = observe(game.flow.session)
            evidence['dice_before'] = list(roller.used)
            result = game.runner.submit(case['prompt'])
            evidence['interaction_id'] = game.flow.interaction_id
            evidence['requests'] = [dict(stage=r.stage, request_id=r.request_id, prompt=r.prompt,
                context=dict(r.context), result=str(r.result) if isinstance(r.result, Exception) else asdict(r.result),
                applied=r.applied) for r in result.requests]
            evidence['report'] = result.report.context()
            evidence['reply'] = asdict(result.reply) if result.reply else None
            evidence['after'] = after = observe(game.flow.session)
            evidence['errors'] = evaluate(case, before, after, result)
            assert not evidence['errors'], '; '.join(evidence['errors'])
            assert roller.used == evidence['dice_before'], 'A inspeção consumiu dados novos.'
            assert not roller.pending and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        evidence['call_budget'], evidence['dice_used'] = budget.context(), roller.used
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
