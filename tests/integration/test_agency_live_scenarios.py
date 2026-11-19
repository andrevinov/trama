"""Preparações/oráculos novos offline; respostas locais declaradas, sem rede."""
from copy import deepcopy
from pathlib import Path
import runpy
from types import SimpleNamespace
import pytest
from conftest import sourced_plan, judged_world
from trama.agency import IntentDecision
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.parley import InfluenceRequest
from trama.application.situations import load_situation,situation_state
from trama.application.world import WorldAction,WorldPlan,WorldReaction
from trama.bootstrap import open_situation
from trama.social import DispositionAssessment,PersonaEffect

LIVE=runpy.run_path(str(Path(__file__).resolve().parents[1]/'live/test_npc_agency_live.py'))

@pytest.mark.parametrize('case',LIVE['CASES'],ids=[c['id'] for c in LIVE['CASES']])
def test_new_live_preparations_and_oracles_offline(case,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    situation=load_situation(case['id']);roller=situation.new_roller()
    with open_situation(situation,roller=roller,allow_unconfigured=True) as game:
        assert not game.flow.session.agency._pending_events  # Preparação não reapresenta incidentes antigos.
        actor=case['actor'];speaker='prisoner' if actor=='guard_1' else 'companion'
        game.flow.interpreter=SimpleNamespace(interpret=lambda prompt,context:sourced_plan(ActionPlan((
            NarrativeIntent(prompt,'speak',volume='quiet' if case['marker'] in prompt else 'normal'),)),prompt))
        def decide(context):
            if context['phase']=='npc_review':
                return WorldPlan()  # A nova fase só calcula; este controle não muda avaliações.
            if context['phase']=='npc_agency':
                return judged_world(WorldPlan((WorldReaction(0,None,(WorldAction(actor,'say','Preciso da sua resposta. Quanto oferece?'),)),),
                    intent=IntentDecision(actor,'Concluir a negociação.','Cobrar a resposta.','Sua proposta.')),context)
            if case['expected']=='negotiation' and context['parley']['status']=='pending' and context['player_plan'][0]['volume']=='normal':
                profile=game.flow.session.social.profiles[actor]
                assessment=DispositionAssessment('listen','player','Ouvir por um momento.',0,0,'Pedido neutro.',
                    tuple(PersonaEffect(i.id,1,'Concessão de escuta limitada.') for i in profile.persona.interests),(),
                    'Está bem, vou ouvir.','Não aceito.',('Manter custódia.',))
                plan=WorldPlan((WorldReaction(0,None,(WorldAction(actor,'influence','Considera o pedido.',
                    influence=InfluenceRequest(skill='persuasion',assessment=assessment)),)),))
            else:plan=WorldPlan((WorldReaction(0,None,(WorldAction(speaker,'say','Estou bem.',volume='quiet'),)),))
            return judged_world(plan,context)
        game.flow.world_director=SimpleNamespace(decide=decide)
        game.flow.narrator=SimpleNamespace(narrate=lambda context:Speech(off='O vigia não ouviu os cochichos; não houve movimento nem ataque.')
            if not context['allow_on'] else Speech(on='A conversa e as respostas registradas são narradas.'))
        before=situation_state(game.flow.session)
        for index,prompt in enumerate(case['messages']):
            result=game.runner.submit(prompt);after=situation_state(game.flow.session)
            assert not LIVE['evaluate'](case,index,before,after,result)
            broken=deepcopy(after);broken['position']=[1,1]
            assert LIVE['evaluate'](case,index,before,broken,result)
            before=after
        assert not roller.pending

@pytest.mark.parametrize('text',[
 'O guarda continua ouvindo a conversa.',
 'Ele escutou o segredo contado em voz baixa.',
 'O vigia ouviu as palavras dos cochichos.'])
def test_hearing_oracle_rejects_the_known_fabrication(text):
    assert LIVE['unsupported_hearing'](text)

@pytest.mark.parametrize('text',[
 'O guarda não ouviu os cochichos.',
 'O vigia observa de longe, sem escutar as palavras.',
 'O guarda cobra uma resposta; vocês continuam no mesmo lugar.'])
def test_hearing_oracle_accepts_grounded_statements(text):
    assert not LIVE['unsupported_hearing'](text)
