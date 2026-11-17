"""Sentidos dos NPCs: fluxo real, dados fixos e critérios independentes."""

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
CASES = json.loads((ROOT / 'tests/fixtures/perception/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='A bateria paga exige RUN_OPENAI_LIVE_TESTS=1 e autorização descrita em percepcao-live.md.')]


def evaluate(case, index, before, after, result):
    """Não recalcula visão, alcance, rota ou testes com as funções do motor."""
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    expected = case['expected']
    observer = next(o for o in after['sensing']['observers'] if o['id'] == 'watcher')
    sleeper = next(o for o in after['sensing']['observers'] if o['id'] == 'sleeper')
    knowledge = observer['awareness'].get('player')
    events = (*result.report.events, *result.report.world_events)
    searches = [e for e in result.report.world_events if e['operation'] == 'search']
    check(after['resources'] == before['resources'], 'Alterou PV ou recursos de classe.')
    check(after['creatures'] == before['creatures'], 'Concedeu aproximação ao NPC durante a avaliação de percepção.')
    check(after['combat'] is None and after['mode'] == 'narrated', 'Detecção iniciou combate sem escolha hostil.')
    check(not any(e['operation'] == 'attack' and e.get('changed') for e in events), 'Inventou golpe durante detecção.')
    check(after['passages'] == before['passages'], 'Alterou uma porta sem pedido.')
    check(not any(r.stage == FlowStage.NPC_TURN for r in result.requests), 'Criou turnos artificiais de NPC.')
    if expected == 'vision':
        check(after['position'] == [10, 3] and observer['column'] == 12, 'Não parou na primeira casa dentro do alcance visual de 3 m.')
        check(after['parley'] and after['parley']['status'] == 'pending', 'Não permitiu responder à abordagem na distância de detecção.')
        check(result.report.stop_reason is not None, 'Continuou o movimento após a abordagem.')
    else:
        check(after['position'] == before['position'], 'Moveu o jogador sem autorização.')
        check(not result.report.stop_reason, 'Ação simples falhou ou recebeu impedimento indevido.')
    if expected in {'blocked_sight', 'dark', 'inaudible', 'asleep'}:
        check(not knowledge, 'O NPC detectou o jogador sem um sentido que o alcançasse.')
    if expected == 'darkvision':
        check(knowledge and knowledge['level'] == 'seen', 'Visão no escuro de 6 m não detectou o alvo a 4,5 m.')
    if expected == 'loud':
        check(knowledge and knowledge['level'] == 'heard' and knowledge['position'] is None,
              'O grito não foi ouvido ou revelou uma localização visual inexistente.')
    if expected in {'hidden', 'passive_found', 'hide_failed'}:
        if index == 0:
            hides = [e for e in result.report.events if e['operation'] == 'hide']
            check(len(hides) == 1 and hides[0].get('dc') == 15, 'Não executou Hide real contra CD 15.')
            check(after['sensing']['hidden'] == (expected != 'hide_failed'), 'O resultado de Hide divergiu do dado fixado.')
        elif expected == 'hidden':
            check(after['sensing']['hidden'] and after['sensing']['stealth_total'] == 21 and not knowledge,
                  'Percepção passiva 13 encontrou ocultação 21 ou furtividade não foi preservada.')
        elif expected == 'passive_found':
            check(not after['sensing']['hidden'] and knowledge and knowledge['level'] == 'located' and not knowledge['visible'],
                  'Percepção passiva 22 não localizou o alvo oculto por som, ou enxergou através da porta.')
        else:
            check(not after['sensing']['hidden'] and knowledge and knowledge['level'] == 'heard',
                  'Furtividade falha continuou protegendo contra a audição.')
        check(not searches, 'Concedeu Search ou rolagem extra em lugar da percepção passiva.')
    if expected in {'search_found', 'search_failed'}:
        if index == 0:
            check(len(searches) == 1 and searches[0].get('dc') == 21 and not searches[0].get('automatic'),
                  'A busca não usou o total real de Furtividade como CD.')
            if searches:
                check(searches[0]['found'] == (expected == 'search_found'), 'Não aplicou o resultado da busca controlada.')
        else:
            check(not searches, 'Repetiu a mesma busca sem mudança relevante ou nova ação de combate.')
        check(after['sensing']['hidden'] == (expected == 'search_failed'), 'Ocultação após Search está incorreta.')
        if expected == 'search_found':
            check(knowledge and knowledge['level'] == 'located' and not knowledge['visible'],
                  'Search deveria localizar por som, sem visão através da porta.')
    if expected in {'awake', 'asleep'}:
        check(sleeper['sleeping'] == (expected == 'asleep'), 'O despertar ignorou volume/distância do som.')
        check('sleeper' not in after['resources'], 'Criou ficha de Guerreiro para o NPC não combatente.')
    return errors


def record(result, game):
    return {'status': result.status, 'interaction_id': game.flow.interaction_id,
        'requests': [asdict(r) if not isinstance(r.result, Exception) else
                     {'stage': r.stage, 'context': r.context, 'error': str(r.result)} for r in result.requests],
        'execution': result.report.context(), 'state': situation_state(game.flow.session),
        'reply': asdict(result.reply) if result.reply else None,
        'error': str(result.error) if result.error else None}


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_npc_perception(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_PERCEPTION_ARTIFACTS', ROOT / 'logs/live/perception')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    budget = CallBudget(case['max_sdk_calls'])
    evidence = {'scope': 'game_flow_from_prepared_situation', 'case': case, 'situation': situation.data,
        'session_id': uuid4().hex, 'outcome': 'failed', 'runs': [],
        'narrative_review': 'Distinguir ouvido/localizado/visto; preservar segredos dos NPCs; conferir luz, sono, dados e ausência de aproximação inventada.'}
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            result = game.runner.start()
            evidence['runs'].append(record(result, game))
            assert result.status == RunStatus.COMPLETED and result.reply.on.strip()
            for index, prompt in enumerate(case['messages']):
                before = situation_state(game.flow.session)
                result = game.runner.submit(prompt)
                evidence['runs'].append(record(result, game))
                assert result.status == RunStatus.COMPLETED and not result.awaiting_reaction, 'Fluxo não concluído.'
                assert result.reply and result.reply.on.strip(), 'Faltou narração dos acontecimentos.'
                errors = evaluate(case, index, before, situation_state(game.flow.session), result)
                evidence['runs'][-1]['errors'] = errors
                assert not errors, '; '.join(errors)
            assert not roller.pending, 'Dados previstos não foram usados pelo fluxo real.'
            assert not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        evidence['dice_used'] = roller.used
        evidence['dice_pending'] = list(roller.pending)
        evidence['budget'] = budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
