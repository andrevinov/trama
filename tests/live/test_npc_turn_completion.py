"""Turnos de NPCs: aproximação limitada e ataque ao alcançar, pelo fluxo real."""

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
CASES = json.loads((ROOT / 'tests/fixtures/npc_turns/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Defina RUN_OPENAI_LIVE_TESTS=1; limites em turnos-npc-live.md.')]


def evaluate(case, before, after, report, requests):
    """Critérios geométricos e de recursos independentes do executor de movimento."""
    errors = []
    if not after['combat'] or after['combat']['active_id'] != 'player' or after['combat']['round'] != 2:
        errors.append('O controle não retornou ao jogador na rodada 2.')
    if after['position'] != before['position'] or after['pending_opportunity']:
        errors.append('Moveu o jogador ou terminou com escolha pendente.')
    if sum(r.stage == FlowStage.NPC_TURN for r in requests) != 1:
        errors.append('Não decidiu exatamente um turno do NPC.')
    moves = [e for e in report.world_events if e['operation'] == 'move']
    traveled = sum(e.get('cost_meters', 0) for e in moves)
    if not 0 < traveled <= 9:
        errors.append('O vigia não se aproximou ou ultrapassou os 9 m disponíveis.')
    origin, destination = before['creatures']['watcher'], after['creatures']['watcher']
    if max(abs(a - b) for a, b in zip(origin, destination)) * 1.5 > 9:
        errors.append('A posição final não respeita o limite geométrico de 9 m.')
    if abs(destination[0] - after['position'][0]) >= abs(origin[0] - before['position'][0]):
        errors.append('O vigia não reduziu a distância ao jogador.')
    ends = [e for e in report.world_events if e['operation'] == 'end_turn' and e.get('actor_id') == 'watcher']
    if len(ends) != 1:
        errors.append('O turno do vigia não foi encerrado exatamente uma vez.')
    attacks = [e for e in report.world_events if e['operation'] == 'attack']
    if after['resources']['watcher'] != before['resources']['watcher']:
        errors.append('Alterou PV ou poderes do vigia sem necessidade.')
    player = {**before['resources']['player'], 'hp': 25 if case['expected'] == 'attack' else 28}
    if after['resources']['player'] != player:
        errors.append('Dano ou poderes do jogador divergem dos efeitos permitidos.')
    if case['expected'] == 'attack':
        if len(attacks) != 1 or attacks[0].get('damage') != 3 or not after['budgets']['watcher']['action_used']:
            errors.append('Não executou exatamente um ataque legal ao alcançar o jogador.')
        if max(abs(a - b) for a, b in zip(destination, after['position'])) != 1:
            errors.append('Ataque sem alcançar uma casa adjacente.')
    elif attacks or after['budgets']['watcher']['action_used']:
        errors.append('Executou ataque ou gastou ação apesar da distância.')
    if after['inventory'] != before['inventory'] or after['passages'] != before['passages']:
        errors.append('Alterou inventário ou passagens durante a aproximação.')
    if report.failures or any(e.get('fallback') for e in ends):
        errors.append('O modelo produziu uma ação inválida; a recuperação não conta como plano legal aprovado.')
    return errors


def record(result, game):
    return {'status': result.status, 'interaction_id': game.flow.interaction_id,
            # AIContext é um dict tipado com construtor próprio; asdict(trace)
            # tenta reconstruí-lo sem o tipo da fase. Preservamos o payload real.
            'requests': [{'request_id': r.request_id, 'stage': r.stage, 'context': dict(r.context),
                'prompt': r.prompt, 'applied': r.applied,
                **({'error': str(r.result)} if isinstance(r.result, Exception) else {'result': asdict(r.result)})}
                for r in result.requests],
            'report': result.report.context(), 'reply': asdict(result.reply) if result.reply else None,
            'error': str(result.error) if result.error else None, 'state': situation_state(game.flow.session)}


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_npc_turn_completion(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_NPC_TURN_ARTIFACTS', ROOT / 'logs/live/npc_turns')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    # Permite reduzir o teto em uma retomada após falha de infraestrutura/harness.
    max_calls = min(case['max_sdk_calls'], int(os.environ.get('TRAMA_NPC_TURN_MAX_CALLS', case['max_sdk_calls'])))
    roller, budget = situation.new_roller(), CallBudget(max_calls)
    evidence = {'scope': 'game_flow_from_prepared_situation', 'case': case, 'situation': situation.data,
                'session_id': uuid4().hex, 'outcome': 'failed', 'runs': [],
                'narrative_review': 'Verificar aproximação de até 9 m, ataque somente ao alcançar, turno concluído e resposta off sem espera fictícia.'}
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['initial'] = before = situation_state(game.flow.session)
            # Recorte: interação a partir do combate preparado, sem pagar outra
            # abertura que não participa da conclusão do turno avaliado.
            result = game.runner.submit(case['prompt'])
            evidence['runs'].append(record(result, game))
            assert result.status == RunStatus.COMPLETED and not result.awaiting_reaction, 'Fluxo não concluiu.'
            after = situation_state(game.flow.session)
            errors = evaluate(case, before, after, result.report, result.requests)
            evidence['runs'][-1]['errors'] = errors
            assert not errors, '; '.join(errors)
            assert result.reply and result.reply.on.strip(), 'Faltou narração dos efeitos.'
            off = game.runner.submit('[É a vez de quem? O vigia ainda está agindo?]')
            evidence['runs'].append(record(off, game))
            assert off.status == RunStatus.COMPLETED and off.reply.off.strip() and not off.reply.on
            assert all(r.stage == FlowStage.NARRATE for r in off.requests)
            assert situation_state(game.flow.session) == after, 'Pergunta off alterou o estado.'
            assert not roller.pending and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        evidence['dice_used'], evidence['dice_pending'] = roller.used, list(roller.pending)
        evidence['call_budget'] = budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
