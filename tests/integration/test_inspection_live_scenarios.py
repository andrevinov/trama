"""Preparação e critérios dos quatro lives; adaptadores locais declarados."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan, judged_world
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, InspectionIntent, MovementIntent
from trama.application.situations import load_situation
from trama.application.world import WorldPlan
from trama.bootstrap import open_situation

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_passage_inspection_live.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_preparations_and_independent_oracles_offline(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        def interpret(prompt, context):
            if case['target'] is None:
                return sourced_plan(ActionPlan((MovementIntent((), False, 'Qual grade deseja conferir?'),)),
                                    prompt, kind='unclear')
            return sourced_plan(ActionPlan((InspectionIntent(case['target'], case['method'], case['volume'], False),)), prompt)
        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=lambda ctx: judged_world(WorldPlan(), ctx))
        game.flow.narrator = SimpleNamespace(narrate=lambda ctx: Speech(on='A passagem continua fechada.')
            if ctx['allow_on'] else Speech(off='Qual passagem deseja conferir?'))
        before = LIVE['observe'](game.flow.session)
        assert all(p['locked'] is None for p in before['passages'] if p['id'] == case['target'])
        rolls_before = list(roller.used)
        result = game.runner.submit(case['prompt'])
        after = LIVE['observe'](game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result)
        assert roller.used == rolls_before and not roller.pending
        # Controles negativos: critérios rejeitam passagem aberta ou movimento inventado.
        broken = deepcopy(after)
        broken['state']['position'] = [100, 100]
        assert LIVE['evaluate'](case, before, broken, result)
        if case['target']:
            broken = deepcopy(after)
            broken['state']['passages'][case['target']]['is_open'] = True
            assert LIVE['evaluate'](case, before, broken, result)
            events = tuple({**e, 'locked': not case['locked']} for e in result.report.events)
            assert LIVE['evaluate'](case, before, after, replace(result, report=replace(result.report, events=events)))
        else:
            world = replace(result.requests[0], stage='world')
            assert LIVE['evaluate'](case, before, after, replace(result, requests=(*result.requests, world)))
        # O reinício usa a mesma preparação e volta a ocultar a fechadura.
        game.flow.reset()
        restarted = LIVE['observe'](game.flow.session)
        assert restarted['state']['position'] == before['state']['position']
        assert restarted['state']['sensing']['stealth_total'] == before['state']['sensing']['stealth_total']
        assert restarted['lock_labels'] == before['lock_labels']
