"""Fluxo real: referências de memória e adjudicação contextual, uma interação/caso."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from trama.application.game_runner import RunStatus
from trama.application.situations import load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'tests/fixtures/adjudication/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Bateria focada: docs/sistema/qualidade/dificuldade-live.md.')]


def evaluate(case, before, after, result):
    errors = []
    if result.status != RunStatus.COMPLETED or result.error or result.awaiting_reaction:
        return ['O fluxo não concluiu: ' + str(result.error)]
    if result.report.failures or not result.reply or not result.reply.on.strip():
        errors.append('Falha mecânica ou ausência de narração.')
    legal_position = (max(abs(after['position'][0]-12), abs(after['position'][1]-3)) <= 1
                      if case['expected'] == 'steal_key' else after['position'] == before['position'])
    if not legal_position or after['resources']['player']['hp'] != before['resources']['player']['hp']:
        errors.append('Movimento ou dano ao jogador não solicitado.')
    events = result.report.world_events
    worlds = [r for r in result.requests if r.stage in {'world', 'npc_turn'}]
    for trace in worlds:
        requests = trace.context['world']['adjudication']['requests']
        decisions = trace.result.adjudications
        if {d.request_id for d in decisions} != {r['id'] for r in requests}:
            errors.append('Pedidos contextuais não foram resolvidos exatamente uma vez.')
        for reaction in trace.result.reactions:
            if any(a.memory_ids and a.operation != 'say' for a in reaction.actions):
                errors.append('O modelo ainda preenche memory_ids em ação não verbal.')
    expected = case['expected']
    if expected == 'influence':
        if len([e for e in events if e['operation'] == 'influence']) != 1:
            errors.append('A negociação com memórias não foi resolvida.')
        for name in ('position','creatures','passages','inventory','combat'):
            if before[name] != after[name]:
                errors.append('Negociação concedeu efeito material: ' + name)
    elif expected == 'share':
        if not any(e['operation'] == 'say' and e['actor_id'] == 'archivist'
                   and e.get('shared_memories') for e in events):
            errors.append('O arquivista não transmitiu seu conhecimento da chave.')
        if any(a.memory_ids and a.actor_id != 'archivist' for t in worlds for r in t.result.reactions for a in r.actions):
            errors.append('Compartilhou memória de outro NPC.')
    elif expected in {'muffled','loud'}:
        hearings = [e for e in events if e['operation'] == 'hearing_check' and e['actor_id'] == 'guard_1'
                    and e['purpose'] == 'notice_noise']
        if not hearings:
            errors.append('Não avaliou a audição real do guarda através da porta.')
        if expected == 'muffled':
            if any(e['passed'] for e in hearings) or after['guard_alert'] or after['parley']:
                errors.append('Fala normal abafada causou detecção indevida.')
            if not all(e['total'] == 8 and e['disadvantage'] for e in hearings):
                errors.append('A passiva não refletiu desvantagem através da porta grossa.')
        elif not any(e['passed'] for e in hearings) or not after['parley']:
            errors.append('O grito através das frestas não provocou abordagem.')
    else:
        id = 'listen:guard_door' if expected.startswith('listen_') else expected
        checks = [e for e in events if e['operation'] == 'check' and e.get('adjudication_id') == id]
        if len(checks) != 1:
            return [*errors, 'Faltou a resolução contextual única: ' + id]
        check = checks[0]
        if check['automatic'] or check['dc'] not in {5,10,15,20,25,30} or not check['dice']:
            errors.append('A tarefa incerta não usou dado e CD contextual típica.')
        if expected.startswith('listen_'):
            passed = expected == 'listen_pass'
            if check['passed'] != passed or not check['disadvantage']:
                errors.append('Escuta não respeitou porta grossa e dados fixados.')
            if any(e['operation'] == 'heard' for e in events) != passed:
                errors.append('Revelou/omitiu o som em desacordo com o teste.')
        elif expected == 'find_uniform':
            if check['skill'] != 'perception' or ('cleaner_uniform' in after['discovered']) != check['passed']:
                errors.append('Busca não aplicou Search/Percepção à descoberta.')
            if after['inventory'] != before['inventory']:
                errors.append('Buscar concedeu um item sem pegá-lo.')
        elif expected == 'steal_key':
            if check['skill'] != 'sleight_of_hand' or ('cell_key' in after['inventory']) != check['passed']:
                errors.append('O furto não respeitou o teste real.')
        elif expected == 'detect_sword':
            if check['passed'] or after['disguise'] != 'accepted' or after['combat']:
                errors.append('A inspeção ignorou o dado baixo ou mudou a CD fixa do disfarce.')
    return errors


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_contextual_difficulty(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_DIFFICULTY_ARTIFACTS', ROOT/'logs/live/difficulty'))/RUN_ID/case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['situation'])
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'])
    evidence = dict(case=case, situation=situation.data, session_id=uuid4().hex, outcome='failed',
        scope='game_flow_from_prepared_situation', narrative_review='Conferir somente fatos percebidos, sem sucesso antecipado, pagamento, liberdade ou conteúdo inaudível inventado.')
    try:
        with capture_logs(log_file=output/'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['before'] = situation_state(game.flow.session)
            result = game.runner.submit(case['prompt'])
            evidence['after'] = situation_state(game.flow.session)
            evidence['requests'] = [dict(stage=r.stage, request_id=r.request_id, context=dict(r.context), prompt=r.prompt,
                applied=r.applied, result=asdict(r.result) if not isinstance(r.result,Exception) else str(r.result)) for r in result.requests]
            evidence['report'] = result.report.context()
            evidence['reply'] = asdict(result.reply) if result.reply else None
            evidence['errors'] = evaluate(case,evidence['before'],evidence['after'],result)
            assert not evidence['errors'], '; '.join(evidence['errors'])
            assert not roller.pending and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        evidence['dice_used'],evidence['call_budget'] = roller.used,budget.context()
        (output/'result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str)+'\n')
