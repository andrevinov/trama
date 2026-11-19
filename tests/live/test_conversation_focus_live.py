"""Foco semântico pelo fluxo oficial: abertura, fala, resposta real e consulta off.

Uma tentativa por caso, teto de dez chamadas ao SDK por caso. Criação/coleta
não autoriza execução: docs/sistema/qualidade/foco-conversa-live.md.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from trama.application.situations import ScriptedRoller, situation_state
from trama.bootstrap import open_game
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / 'src/trama/scenarios/generals_council.json'
CASES = json.loads((ROOT / 'tests/fixtures/conversation_focus/cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
pytestmark = [pytest.mark.live, pytest.mark.skipif(
    os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
    reason='Requer autorização da bateria: docs/sistema/qualidade/foco-conversa-live.md.')]


def snapshot(session):
    return dict(state=situation_state(session), conversations={
        actor: session.conversations.view(actor) for actor in ('player', 'general_voss')})


def evaluate(case, before, after, result, *, off=False, initial=False):
    """Critérios independentes: erro, resposta executada, termos e efeitos físicos."""
    errors = []
    if result.status != 'completed' or result.error or result.awaiting_reaction:
        return ['Fluxo incompleto ou com erro: ' + str(result.error)]
    if result.report.failures or result.report.stop_reason:
        errors.append('A interação contém rejeição ou interrupção.')
    if not result.reply or not (result.reply.on or result.reply.off):
        errors.append('A interação não entregou resposta ao jogador.')
    if initial:
        if [r.stage for r in result.requests] != ['narrate'] or not result.reply or not result.reply.on:
            errors.append('Abertura não foi narrada pelo fluxo oficial.')
        return errors
    if off:
        if before != after or [r.stage for r in result.requests] != ['narrate']:
            errors.append('A consulta off alterou o estado ou avançou o Mundo.')
        if not result.reply or result.reply.on or not result.reply.off:
            errors.append('A consulta off não foi respondida exclusivamente em off.')
        return errors
    for key in ('position', 'resources', 'budgets', 'mode', 'combat', 'passages', 'inventory'):
        if before['state'][key] != after['state'][key]:
            errors.append('Efeito físico não solicitado: ' + key)
    if not {'interpret', 'world', 'narrate'} <= {r.stage for r in result.requests}:
        errors.append('A mensagem não passou pela composição completa.')
    spoken = [e for e in result.report.events if e['operation'] == 'speak']
    if not spoken or not any('general_voss' in e.get('heard_by', []) for e in spoken):
        errors.append('Voss não ouviu a fala do jogador.')
    answers = [e for e in result.report.world_events if e['operation'] == 'say'
               and e.get('actor_id') == 'general_voss' and 'player' in e.get('heard_by', [])]
    if not answers:
        errors.append('Nenhuma resposta falada de Voss foi executada e ouvida.')
    frames = after['conversations']['player']
    if not frames or not any(c['last_speaker'] == 'general_voss' for c in frames):
        errors.append('A conversa não registrou a contribuição de Voss.')
    proposals = [p for c in frames for p in c['proposals']]
    if case['proposal']:
        own = [p for p in proposals if p['actor_id'] == 'player']
        if not own:
            errors.append('A oferta explícita não foi registrada como proposta do jogador.')
        else:
            terms = ' '.join(t['text'].casefold() for p in own for v in p['versions'] for t in v['terms'])
            if not all(word in terms for word in ('trinta', 'dias', 'recuo', 'simultâneo')):
                errors.append('Os termos perderam duração ou simultaneidade da oferta.')
    elif proposals:
        errors.append('A saudação criou uma proposta não apresentada.')
    for request in result.requests:
        if request.stage == 'narrate':
            wire = json.dumps(request.context, ensure_ascii=False)
            if 'grain_reserves_may_not_last_winter' in wire or 'private-supply-report' in wire:
                errors.append('A narração recebeu o relatório reservado de Valdren.')
    return errors


def record(result, game):
    return dict(status=result.status, interaction_id=game.flow.interaction_id,
        requests=[dict(stage=r.stage, request_id=r.request_id, context=dict(r.context), prompt=r.prompt,
            result=str(r.result) if isinstance(r.result, Exception) else asdict(r.result), applied=r.applied)
            for r in result.requests], report=result.report.context(),
        reply=asdict(result.reply) if result.reply else None, error=str(result.error) if result.error else None)


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_live_conversation_focus(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_FOCUS_ARTIFACTS', ROOT / 'logs/live/conversation_focus')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    # Permite reduzir o teto para respeitar saldo autorizado após falha de ambiente.
    cap = min(case['max_sdk_calls'], int(os.environ.get('TRAMA_FOCUS_CALL_CAP', case['max_sdk_calls'])))
    budget, roller = CallBudget(cap), ScriptedRoller([])
    evidence = dict(case=case, scenario=str(SCENARIO.relative_to(ROOT)), session_id=uuid4().hex,
        outcome='failed', runs=[], narrative_review=(
            'Conferir reconhecimento e resposta coerente; ausência de contato físico a distância, '
            'segredos, acordo ou cumprimento inventados. O foco pode resumir, mas não criar fatos. '
            'Comparar narração e resposta off com as falas executadas; aprovação automática não certifica a prosa.'))
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_game(
                SCENARIO, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['scenario_sha256'] = sha256(SCENARIO.read_bytes()).hexdigest()
            before = snapshot(game.flow.session)
            evidence['initial'] = before
            for phase, prompt in (('initial', None), ('on', case['prompt']), ('off', case['off'])):
                result = game.runner.start() if phase == 'initial' else game.runner.submit(prompt)
                after = snapshot(game.flow.session)
                observed = dict(phase=phase, before=before, after=after, **record(result, game))
                evidence['runs'].append(observed)
                observed['errors'] = evaluate(case, before, after, result, off=phase == 'off', initial=phase == 'initial')
                assert not observed['errors'], '; '.join(observed['errors'])
                before = after
            assert not roller.used and not budget.context()['exceeded']
            evidence['outcome'] = 'passed'
    except BaseException as error:
        evidence['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        evidence['call_budget'], evidence['dice_used'] = budget.context(), roller.used
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')
