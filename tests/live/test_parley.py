"""Abordagem, conversa e escalada: fluxo completo desde situação da aplicação."""

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
CASES = json.loads((ROOT / 'tests/fixtures/parley/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar a bateria paga descrita em conversa-live.md.')]


def evaluate_detection(after, report, requests):
    """Expectativas externas ao algoritmo: coordenadas da sessão que revelou o erro."""
    errors = []
    if after['position'] != [8, 20] or after['creatures']['guard_1'] != [10, 6]:
        errors.append('A abordagem não preservou o primeiro ponto de detecção junto à porta.')
    if after['mode'] != 'narrated' or after['combat'] is not None:
        errors.append('Iniciou iniciativa antes de ouvir a resposta do jogador.')
    if not after['parley'] or after['parley']['status'] != 'pending':
        errors.append('Não ofereceu conversa antes do combate.')
    if after['resources']['player']['hp'] != 28 or any(b['action_used'] for b in after['budgets'].values()):
        errors.append('Causou dano ou gastou ação antes da iniciativa.')
    if not after['passages']['guard_door']['is_open'] or not after['prisoner_awake']:
        errors.append('Não preservou a cadeia de ruído, audição e abertura da porta.')
    if not report.stop_reason or not any(e['operation'] == 'parley' for e in report.world_events):
        errors.append('Não interrompeu a ação na abordagem.')
    if sum(e.get('traveled_meters', 0) for e in report.events if e['operation'] == 'move') != 3:
        errors.append('Deslocamento do jogador divergiu dos 3 m até a interrupção.')
    if any(r.stage == FlowStage.NPC_TURN for r in requests):
        errors.append('Executou turno de NPC antes da decisão de combate.')
    return errors


def evaluate_resolution(expected, before, after, report, requests):
    errors = []
    events = (*report.events, *report.world_events)
    influence = [e for e in report.world_events if e['operation'] == 'influence']
    actual_attacks = [e for e in events if e['operation'] == 'attack' and e.get('changed')]
    if after['resources'] != before['resources'] or actual_attacks:
        errors.append('Houve dano, golpe ou gasto de recurso incompatível com a distância inicial.')
    if after['inventory'] != before['inventory'] or after['passages'] != before['passages']:
        errors.append('Alterou inventário ou portas durante a conversa.')
    if expected in {'peaceful', 'failed'}:
        if len(influence) != 1 or influence[0].get('skill') != 'persuasion' or 'dice' not in influence[0]:
            errors.append('A tentativa clara de persuadir não recebeu um teste real de Persuasão.')
        elif influence[0]['accepted'] != (expected == 'peaceful'):
            errors.append('Não aplicou o resultado do teste controlado.')
    elif influence:
        errors.append('Impôs conversa/teste social apesar da escolha explícita de atacar.')
    if after['position'] != before['position']:
        errors.append('Concedeu aproximação ao jogador antes da iniciativa vencida pelo guarda.')
    if expected == 'peaceful':
        if after['mode'] != 'narrated' or after['combat'] is not None or after['parley']['status'] != 'peaceful':
            errors.append('Persuasão bem-sucedida não evitou o combate.')
        if after['creatures'] != before['creatures'] or report.stop_reason:
            errors.append('Aproximou o guarda ou impediu indevidamente a conversa bem-sucedida.')
        if any(r.stage == FlowStage.NPC_TURN for r in requests):
            errors.append('Gerou turno de NPC após solução pacífica.')
    else:
        turns = [r for r in requests if r.stage == FlowStage.NPC_TURN]
        if not after['combat'] or after['combat']['active_id'] != 'player':
            errors.append('Não resolveu iniciativa e primeiro turno do guarda até devolver o controle.')
        if not turns or turns[0].context['world']['npcs'][0]['column'] != 10 or turns[0].context['world']['npcs'][0]['row'] != 6:
            errors.append('O combate começou com o guarda fora da posição de detecção.')
        guard = after['creatures']['guard_1']
        if max(abs(guard[0] - 10), abs(guard[1] - 6)) > 6:
            errors.append('O guarda ultrapassou 9 m no primeiro turno.')
        if any(f.actor_id == 'guard_1' for f in report.failures):
            errors.append('O turno do guarda falhou em vez de concluir legalmente.')
    return errors


def record_run(result, game):
    return {'status': result.status, 'interaction_id': game.flow.interaction_id,
            'requests': [asdict(r) if not isinstance(r.result, Exception) else
                {'request_id': r.request_id, 'stage': r.stage, 'context': r.context, 'error': str(r.result)}
                for r in result.requests],
            'report': result.report.context(), 'reply': asdict(result.reply) if result.reply else None,
            'error': str(result.error) if result.error else None, 'state': situation_state(game.flow.session)}


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_parley(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_PARLEY_ARTIFACTS', ROOT / 'logs/live/parley')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    budget = CallBudget(case['max_sdk_calls'])
    evidence = {'case': case, 'scope': 'game_flow_from_prepared_situation', 'outcome': 'failed',
                'situation': situation.data, 'runs': [], 'session_id': uuid4().hex,
                'narrative_review': 'Conferir ordem audível à distância, espaço para responder, resultado social fiel e ausência de golpes/captura inventados.'}
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['initial'] = situation_state(game.flow.session)
            result = game.runner.start()
            evidence['runs'].append(record_run(result, game))
            assert result.status == RunStatus.COMPLETED and result.reply.on.strip()
            detected = None
            for index, prompt in enumerate(case['messages']):
                result = game.runner.submit(prompt)
                evidence['runs'].append(record_run(result, game))
                assert result.status == RunStatus.COMPLETED and not result.awaiting_reaction, 'Fluxo incompleto ou falhou.'
                assert result.reply and result.reply.on.strip(), 'Faltou a narração dos efeitos validados.'
                after = situation_state(game.flow.session)
                errors = (evaluate_detection(after, result.report, result.requests) if index == 0 else
                          evaluate_resolution(case['expected'], detected, after, result.report, result.requests))
                evidence['runs'][-1]['errors'] = errors
                assert not errors, '; '.join(errors)
                detected = after
            assert not roller.pending, 'O caso não executou as rolagens declaradas.'
            assert not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        evidence['dice_used'] = roller.used
        evidence['dice_pending'] = list(roller.pending)
        evidence['call_budget'] = budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
