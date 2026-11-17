"""Preparações e oráculos dos sete casos novos, com adaptadores locais explícitos."""
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, NarrativeIntent, ScenarioIntent
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldPlan
from trama.bootstrap import open_situation
from trama.difficulty import Adjudication

LIVE=runpy.run_path(str(Path(__file__).resolve().parents[1]/'live/test_contextual_difficulty_live.py'))
CASES=[c for c in LIVE['CASES'] if c['id'].startswith('dificuldade-')]

@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_new_situation_and_live_oracle_offline(case,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    situation=load_situation(case['situation'])
    roller=situation.new_roller()
    with open_situation(situation,roller=roller,allow_unconfigured=True) as game:
        expected=case['expected']
        if expected in {'muffled','loud'}:
            intent=NarrativeIntent(case['prompt'],'speak',volume='loud' if expected=='loud' else 'normal')
        elif expected.startswith('listen_'):
            intent=ScenarioIntent('listen','guard_door')
        elif expected=='detect_sword': intent=DoorIntent('open','guard_door')
        else: intent=ScenarioIntent('investigate' if expected=='find_uniform' else 'take',
                                   'cell_4' if expected=='find_uniform' else 'cell_key')
        game.flow.interpreter=SimpleNamespace(interpret=lambda prompt,context:sourced_plan(ActionPlan((intent,)),prompt))
        def decide(context):
            choices=[]
            for r in context['world']['adjudication']['requests']:
                loud=r['kind']=='hearing' and r['facts']['sound:volume']=='loud'
                choices.append(Adjudication(r['id'],'automatic' if loud else 'check',None if loud else 'easy',
                    False,not loud and r['kind'] in {'hearing','listen'},tuple(r['facts'])[:1],
                    'Julgamento local explícito para verificar o fluxo e o oráculo.'))
            return WorldPlan(adjudications=tuple(choices))
        game.flow.world_director=SimpleNamespace(decide=decide)
        game.flow.narrator=SimpleNamespace(narrate=lambda context:Speech(on='Resultado mecânico registrado.'))
        before=situation_state(game.flow.session)
        result=game.runner.submit(case['prompt'])
        after=situation_state(game.flow.session)
        errors=LIVE['evaluate'](case,before,after,result)
        assert not errors,errors
        assert not roller.pending
        after['position']=[1,1]
        assert LIVE['evaluate'](case,before,after,result), 'O oráculo deve rejeitar movimento indevido.'
