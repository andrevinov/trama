"""Mesmo carregamento/runner dos casos live, com decisões externas locais."""

from copy import deepcopy
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, MovementIntent, NarrativeIntent, RuleIntent
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_npc_perception.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_shared_sensory_situation_and_live_criteria(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        def interpret(prompt, context):
            expected = case['expected']
            if expected == 'vision':
                intent = MovementIntent((), False, '', 'east')
            elif expected in {'hidden', 'passive_found', 'hide_failed'} and prompt == case['messages'][0]:
                intent = RuleIntent('hide')
            else:
                operation = 'wait' if expected.startswith('search_') else 'look' if expected in {'blocked_sight', 'dark', 'darkvision'} else 'speak'
                volume = 'quiet' if expected in {'hidden', 'passive_found', 'hide_failed', 'asleep'} else 'loud' if expected == 'loud' else 'normal'
                intent = NarrativeIntent(prompt, operation, volume=volume)
            return sourced_plan(ActionPlan((intent,)), prompt)

        def decide(context):
            if case['expected'].startswith('search_') and not context['world']['perception']['last_search']:
                return WorldPlan((WorldReaction(0, None, (WorldAction('watcher', 'search', 'O vigia procura quem está escondido.', 'player'),)),))
            return WorldPlan()

        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='Os acontecimentos são narrados.'))
        assert game.runner.start().status == 'completed'
        for index, prompt in enumerate(case['messages']):
            before = situation_state(game.flow.session)
            result = game.runner.submit(prompt)
            assert result.status == 'completed', result.error
            after = situation_state(game.flow.session)
            errors = LIVE['evaluate'](case, index, before, after, result)
            assert not errors, errors
            if case['expected'] in {'hidden', 'blocked_sight', 'dark'}:
                broken = deepcopy(after)
                watcher = next(o for o in broken['sensing']['observers'] if o['id'] == 'watcher')
                watcher['awareness']['player'] = {'level': 'seen', 'visible': True, 'position': broken['position']}
                if case['expected'] != 'hidden' or index == 1:
                    assert LIVE['evaluate'](case, index, before, broken, result), 'O oráculo aceitou detecção indevida.'
        assert not roller.pending
        assert game.runner.reset().status == 'completed'
        state = situation_state(game.flow.session)
        assert not next(o for o in state['sensing']['observers'] if o['id'] == 'watcher')['awareness']
        assert state['parley'] is None and len(roller.used) == situation.data['preparation_rolls']
