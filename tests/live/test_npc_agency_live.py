"""Intenções em exploração e fidelidade da narração pelo fluxo oficial."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

import pytest

from trama.application.situations import load_situation, situation_state
from trama.bootstrap import open_situation
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT=Path(__file__).resolve().parents[2]
CASES=json.loads((ROOT/'tests/fixtures/agency/cases.json').read_text())
RUN_ID=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]
pytestmark=[pytest.mark.live,pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS')!='1',
    reason='Bateria e autorização: docs/sistema/qualidade/agencia-live.md.')]


def unsupported_hearing(text):
    """Sentinela para a regressão conhecida; não substitui revisão semântica."""
    for sentence in re.split(r'[.!?\n]',text.casefold()):
        if re.search(r'\b(não|nem|sem|inaudív\w*)\b',sentence):
            continue
        if (re.search(r'\b(guarda|vigia|ele)\b',sentence)
                and re.search(r'\b(ouviu|ouve|ouvindo|escuta|escutou|escutando)\b',sentence)
                and re.search(r'cochicho|conversa|segredo|palavras|disseram',sentence)):
            return True
    return False


def evaluate(case,index,before,after,result):
    errors=[]
    if result.status!='completed' or result.error or result.awaiting_reaction:
        return ['Fluxo incompleto ou com erro: '+str(result.error)]
    if result.report.failures:
        errors.append('A execução registrou uma falha mecânica.')
    for name in ('position','creatures','inventory','passages','resources','prisoner_free','escaped'):
        if after[name]!=before[name]:errors.append('Efeito físico não autorizado: '+name)
    off=case['messages'][index].startswith('[')
    if off:
        if before!=after or [r.stage for r in result.requests]!=['narrate']:
            errors.append('Uma consulta off avançou o Mundo ou alterou a intenção.')
        if not result.reply or not result.reply.off or result.reply.on:
            errors.append('A consulta off não foi respondida somente em off.')
        elif unsupported_hearing(result.reply.off):
            errors.append('A narração afirmou que o NPC ouviu o cochicho inaudível.')
        if result.reply and re.search(r'\b(heard_by|actor_id|npc_agency)\b',result.reply.off):
            errors.append('A resposta usou nomes internos em vez de linguagem de mesa.')
        return errors
    if case['expected']=='negotiation' and index==0:
        influence=[e for e in result.report.world_events if e['operation']=='influence']
        if not influence or not influence[0]['accepted'] or not after['parley'] or after['parley']['status']!='listening':
            errors.append('A negociação inicial não estabeleceu a conversa reproduzida.')
        return errors
    speeches=[e for e in result.report.events if e['operation']=='speak']
    if not speeches or any(e['volume']!='quiet' or case['actor'] in e['heard_by'] for e in speeches):
        errors.append('O cochicho não permaneceu privado na resolução real.')
    for trace in result.requests:
        if trace.stage=='npc_agency':
            if case['marker'] in json.dumps(dict(trace.context),ensure_ascii=False):
                errors.append('A decisão do NPC recebeu palavras inaudíveis.')
            if trace.context['actor']['id']!=case['actor'] or trace.result.intent is None:
                errors.append('A decisão não pertence ao NPC solicitado ou não manteve intenção.')
    if case['actor'] in before['intentions'] and before['mode']=='narrated':
        if not any(r.stage=='npc_agency' for r in result.requests):
            errors.append('O NPC envolvido não recebeu acompanhamento após o diálogo paralelo.')
    for event in result.report.world_events:
        if event.get('actor_id')==case['actor'] and case['marker'] in event.get('text',''):
            errors.append('O NPC revelou conhecimento de palavras que não ouviu.')
    return errors


def record(result,game):
    return dict(status=result.status,interaction_id=game.flow.interaction_id,
        requests=[dict(stage=r.stage,request_id=r.request_id,context=dict(r.context),prompt=r.prompt,
            result=str(r.result) if isinstance(r.result,Exception) else asdict(r.result),applied=r.applied)
            for r in result.requests],report=result.report.context(),
        reply=asdict(result.reply) if result.reply else None,error=str(result.error) if result.error else None)


@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_live_npc_agency(case,capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):pytest.skip('OPENAI_API_KEY não configurada')
    output=Path(os.environ.get('TRAMA_AGENCY_ARTIFACTS',ROOT/'logs/live/agency'))/RUN_ID/case['id']
    output.mkdir(parents=True,exist_ok=False)
    situation=load_situation(case['id'])
    roller,budget=situation.new_roller(),CallBudget(case['max_sdk_calls'])
    evidence=dict(case=case,situation=situation.data,session_id=uuid4().hex,outcome='failed',runs=[],
        narrative_review='Conferir quem ouviu cada fala, iniciativa verbal devida, nenhuma leitura de pensamentos, movimento, ataque, itens ou liberdade sem execução correspondente. A sentinela lexical não substitui esta revisão.')
    try:
        with capture_logs(log_file=output/'trace.jsonl'),log_context(session_id=evidence['session_id']),open_situation(
                situation,roller=roller,budget=budget) as game:
            evidence['configuration']=game.services.metadata
            before=situation_state(game.flow.session)
            evidence['initial']=before
            own_actions=[]
            for index,prompt in enumerate(case['messages']):
                result=game.runner.submit(prompt)
                observed=record(result,game)
                observed['before']=before
                observed['after']=after=situation_state(game.flow.session)
                evidence['runs'].append(observed)
                errors=evaluate(case,index,before,after,result)
                observed['errors']=errors
                assert not errors,'; '.join(errors)
                if case['marker'] in prompt:
                    own_actions.extend(e['operation'] for e in result.report.world_events if e.get('actor_id')==case['actor'])
                before=after
            if case['expected']!='off':
                assert any(op in {'say','start_conflict','resume_activity'} for op in own_actions), 'O NPC renovou a espera sem tomar iniciativa.'
            assert not roller.pending and not budget.context()['exceeded']
            evidence['outcome']='passed'
    except BaseException as error:
        evidence['error']=dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        evidence['call_budget'],evidence['dice_used']=budget.context(),roller.used
        (output/'result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str)+'\n')
