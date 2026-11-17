"""Preparação, transporte das evidências e critérios live verificados sem rede."""

from copy import deepcopy
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, NarrativeIntent
from trama.application.situations import load_situation
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation
from trama.knowledge import Claim

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_npc_knowledge_live.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_preparation_and_criteria_through_shared_runner(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    with open_situation(situation, allow_unconfigured=True) as game:
        def interpret(prompt, context):
            claims = ((Claim('archive_key', 'location', 'position:18,3'),) if 'disseram-me' in prompt else ())
            return sourced_plan(ActionPlan((NarrativeIntent(prompt, 'speak', claims=claims),)), prompt)

        def decide(context):
            prompt = context['player_plan'][0]['text']
            candidates = next(a['memories'] for a in context['world']['knowledge']['actors'] if a['actor_id'] == 'archivist')
            ids = ()
            if case['expected'] == 'unknown':
                text = 'Não sei onde fica a chave; não a vi.'
            elif 'disseram-me' in prompt:
                text = 'Obrigado por me contar o que ouviu.'
            else:
                eligible = [m for m in candidates if m['claim']['subject_id'] == 'archive_key'
                            and (m['source']['kind'] == 'report' if 'mais recente' in prompt else m['source']['kind'] == 'observation')]
                chosen = max(eligible, key=lambda m: m['acquired_at'])
                ids, text = (chosen['id'],), chosen['text']
            return WorldPlan((WorldReaction(0, None, (WorldAction('archivist', 'say', text, memory_ids=ids),)),))

        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='O arquivista responde à conversa.'))
        original = before = LIVE['snapshot'](game.flow.session)
        for index, prompt in enumerate(case['messages']):
            result = game.runner.submit(prompt)
            after = LIVE['snapshot'](game.flow.session)
            assert not LIVE['evaluate'](case, index, before, after, result), result.error
            assert json.loads(json.dumps(LIVE['record'](result, game)))['requests']
            broken = deepcopy(after)
            broken['objects']['archive_key'] = [1, 1]
            assert LIVE['evaluate'](case, index, before, broken, result)
            before = after
        assert game.runner.reset().status == 'completed'
        assert LIVE['snapshot'](game.flow.session) == original
