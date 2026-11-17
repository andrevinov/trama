"""Mesmo fato, vários interesses: negociação real desde a abordagem da dungeon."""

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
CASES = json.loads((ROOT / 'tests/fixtures/social_memory_links/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Autorize a bateria focada descrita em vinculos-memoria-live.md.')]


def fact(claim):
    return tuple(claim[k] for k in ('subject_id', 'predicate', 'value'))


def snapshot(game, roller):
    return {**situation_state(game.flow.session), 'dice_used': list(roller.used)}


def evaluate(case, index, before, after, result):
    errors = []
    if result.status != RunStatus.COMPLETED or result.error or result.awaiting_reaction:
        errors.append('A interação falhou ou não concluiu pelo runner.')
    if not result.reply or not result.reply.on.strip():
        errors.append('Faltou narração do resultado validado.')
    if result.report.failures or any(r.stage == 'npc_turn' for r in result.requests):
        errors.append('A negociação gerou falha mecânica ou turno de combate.')
    for name in ('position', 'creatures', 'resources', 'budgets', 'passages', 'inventory', 'combat', 'mode', 'prisoner_free', 'escaped'):
        if after[name] != before[name]:
            errors.append(f'A conversa alterou {name}.')
    if index:
        if before['dice_used'] != after['dice_used'] or before['social'] != after['social'] or before['parley'] != after['parley']:
            errors.append('Repetir os mesmos fatos e pedido mudou a decisão ou rolou outro dado.')
    events = [e for e in result.report.world_events if e['operation'] == 'influence']
    if index and not events:
        return errors
    if len(events) != 1:
        return [*errors, 'Faltou uma resolução social única.']
    event = events[0]
    disposition = event['disposition']
    if disposition['goal'] != case['goal']:
        errors.append('O Mundo mudou o pedido de liberdade/escuta.')
    if index and not event['reused']:
        errors.append('Repetir o pedido não reutilizou a avaliação.')
    groups = disposition['memory_effects']
    identities = [fact(g['claim']) for g in groups]
    if len(identities) != len(set(identities)):
        errors.append('Um fato foi pontuado mais de uma vez.')
    if not any(g['claim']['subject_id'] == 'player' and g['claim']['predicate'] in {'parentage', 'identity'}
               and g['source']['kind'] == 'report' and g['source']['actor_id'] == 'player' for g in groups):
        errors.append('A alegação de nobreza não foi considerada como relato não confirmado do jogador.')
    for group in groups:
        if not group['impacts'] or len({i['interest_id'] for i in group['impacts']}) != len(group['impacts']):
            errors.append('Vínculos de interesses ausentes ou duplicados no agrupamento.')
        if abs(group['score']) > group['weight']:
            errors.append('Um fato contribuiu além do peso de sua fonte.')
        if group['weight'] != (2 if group['source']['kind'] in {'observation', 'habit'} else 1):
            errors.append('Alterou o peso da fonte ao agrupar interesses.')
    if not event['reused']:
        # Observar a proposta real: todos os vínculos válidos devem sobreviver.
        actions = [a for r in result.requests if r.stage == 'world' for reaction in r.result.reactions
                   for a in reaction.actions if a.operation == 'influence']
        if len(actions) != 1:
            errors.append('Não há uma proposta de Influence no pedido real do Mundo.')
        else:
            proposed = actions[0].influence.assessment.memory_effects
            for group in groups:
                links = [e for e in proposed if vars(e.claim) == group['claim']]
                if {(e.interest_id, e.effect, e.reason) for e in links} != {
                        (i['interest_id'], i['effect'], i['reason']) for i in group['impacts']}:
                    errors.append('Perdeu justificativas ou vínculos ao agrupar a evidência.')
    components = disposition['components']
    if components['memories'] != max(-3, min(3, sum(g['score'] for g in groups))):
        errors.append('A parcela de memória não corresponde aos fatos únicos.')
    total = disposition['total']
    expected = 'willing' if total >= 3 else 'unwilling' if total <= -3 else 'hesitant'
    if sum(components.values()) != total or event['willingness'] != expected:
        errors.append('A disposição não respeita a soma e os limiares declarados.')
    if expected == 'hesitant':
        if not event.get('dice') or event['passed'] != (event['total'] >= event['dc']):
            errors.append('Hesitação não aplicou o dado real e a CD.')
    elif 'dice' in event:
        errors.append('Rolou mesmo com disposição clara.')
    says = [e for e in result.report.world_events if e['operation'] == 'say' and e['actor_id'] == 'guard_1']
    if len(says) != 1 or says[0]['text'] != event['response_text'] or not says[0]['perceptible']:
        errors.append('A resposta escolhida não foi a fala audível executada.')
    return errors


def record(result, game, roller):
    return dict(status=result.status, interaction_id=game.flow.interaction_id,
        requests=[dict(request_id=r.request_id, stage=r.stage, prompt=r.prompt, applied=r.applied,
                       context=dict(r.context), **({'error': str(r.result)} if isinstance(r.result, Exception)
                                                   else {'result': asdict(r.result)})) for r in result.requests],
        report=result.report.context(), reply=asdict(result.reply) if result.reply else None,
        error=str(result.error) if result.error else None, state=snapshot(game, roller))


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_memory_evidence_links(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_MEMORY_LINKS_ARTIFACTS', ROOT / 'logs/live/memory-links')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    situation = load_situation(case['id'])
    roller, budget = situation.new_roller(), CallBudget(case['max_sdk_calls'])
    evidence = dict(case=case, situation=situation.data, scope='game_flow_from_prepared_situation',
        session_id=uuid4().hex, runs=[], outcome='failed',
        narrative_review='Conferir alegação incerta, múltiplas consequências sem evidência duplicada, promessa sem pagamento e resposta sem liberdade física inventada.')
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_situation(
                situation, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['initial'] = before = snapshot(game, roller)
            for index, prompt in enumerate(case['messages']):
                result = game.runner.submit(prompt)
                evidence['runs'].append(record(result, game, roller))
                after = snapshot(game, roller)
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
