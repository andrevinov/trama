"""Preparação e critérios da bateria social pelo runner, com adaptadores locais."""

from copy import deepcopy
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.parley import InfluenceRequest
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.agency import IntentDecision
from trama.bootstrap import open_situation
from trama.knowledge import Claim
from trama.social import DispositionAssessment, MemoryEffect, PersonaEffect

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_social_disposition_live.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_social_live_preparation_runner_and_independent_criteria(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with open_situation(load_situation(case['id']), allow_unconfigured=True) as game:
        current = {'index': 0}
        reward = Claim('player', 'offer_reward', 'gold')
        noble = Claim('player', 'identity', 'noble_heir')

        def interpret(prompt, context):
            claims = (reward,) if 'recompensa' in prompt else (noble,) if 'informação nova' in prompt else ()
            return sourced_plan(ActionPlan((NarrativeIntent(prompt, 'speak', claims=claims),)), prompt)

        def decide(context):
            kind, index = case['expected'], current['index']
            profile = game.flow.session.social.profiles['guard_1']
            impacts = {'compassion': 1, 'cruelty': -1, 'custody': 0, 'understanding': 1}
            impacts.update(duty=0, livelihood=0, safety=1, profit=int(kind == 'reward' and index > 0))
            evidence = ((MemoryEffect(reward, 'profit', 1, 'Promessa ouvida de recompensa.'),)
                        if kind == 'reward' and index > 0 else
                        (MemoryEffect(noble, 'safety', 1, 'Alegação nova de identidade.'),)
                        if kind == 'relevance' and index == 3 else ())
            assessment = DispositionAssessment('listen', 'player', 'Ouvir sem conceder liberdade.',
                int(kind in {'lawful', 'chaotic'}), int(kind == 'unwilling'), 'Pedido concreto.',
                tuple(PersonaEffect(i.id, impacts[i.id], 'Impacto classificado pelo adaptador local.')
                      for i in profile.persona.interests), evidence,
                'Fique onde está. Vou ouvir, mantendo a custódia.', 'Não. Volte à cela.', ('Manter posição e custódia.',))
            return WorldPlan((WorldReaction(0, None, (WorldAction('guard_1', 'influence', 'Avaliação privada.',
                influence=InfluenceRequest(skill='persuasion', assessment=assessment)),)),))

        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='O guarda responde à distância.'))
        original = before = situation_state(game.flow.session)
        for index, prompt in enumerate(case['messages']):
            current['index'] = index
            result = game.runner.submit(prompt)
            after = situation_state(game.flow.session)
            assert not LIVE['evaluate'](case, index, before, after, result), result.report.context()
            assert json.loads(json.dumps(LIVE['record'](result, game)))['requests']
            broken = deepcopy(after)
            broken['creatures']['guard_1'] = [4, 3]
            assert LIVE['evaluate'](case, index, before, broken, result)
            narration = result.requests[-1].context
            assert 'Avaliação privada' not in json.dumps(narration)
            assert 'disposition' not in json.dumps(narration)
            before = after
        assert game.runner.reset().status == 'completed'
        assert situation_state(game.flow.session) == original


def test_irrelevant_reply_can_leave_social_decision_unchanged_without_influence_event(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    case=next(c for c in LIVE['CASES'] if c['expected']=='relevance')
    with open_situation(load_situation(case['id']),allow_unconfigured=True) as game:
        game.flow.interpreter=SimpleNamespace(interpret=lambda prompt,context: sourced_plan(
            ActionPlan((NarrativeIntent(prompt,'speak'),)),prompt))
        game.flow.narrator=SimpleNamespace(narrate=lambda context: Speech(on='O guarda aguarda.'))
        profile=game.flow.session.social.profiles['guard_1']
        assessment=DispositionAssessment('listen','player','Ouvir mantendo custódia.',0,0,'Neutro.',
            tuple(PersonaEffect(i.id,0,'Neutro.') for i in profile.persona.interests),(),
            'Vou ouvir; fique aí.','Não.',('Manter posição.',))
        game.flow.world_director=SimpleNamespace(decide=lambda context: WorldPlan((WorldReaction(0,None,(
            WorldAction('guard_1','influence','Avalia.',influence=InfluenceRequest(skill='persuasion',assessment=assessment)),)),)))
        assert game.runner.submit(case['messages'][0]).status=='completed'
        game.flow.world_director=SimpleNamespace(decide=lambda context: WorldPlan((WorldReaction(0,None,(
            WorldAction('guard_1','wait','O guarda aguarda a explicação prometida.'),)),),
            intent=IntentDecision('guard_1','Ouvir a explicação.','Aguardar brevemente.','A explicação prometida.'))
            if context['phase']=='npc_agency' else WorldPlan())
        before=situation_state(game.flow.session)
        result=game.runner.submit(case['messages'][2])
        after=situation_state(game.flow.session)
        assert not LIVE['evaluate'](case,2,before,after,result)
        assert any(r.stage=='npc_agency' for r in result.requests)
        assert not any(e['operation']=='influence' for e in result.report.world_events)
        mutated=deepcopy(after)
        mutated['social']['decisions'].append({'accepted':True})
        assert LIVE['evaluate'](case,2,before,mutated,result)
