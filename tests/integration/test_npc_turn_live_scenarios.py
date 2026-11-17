"""Preparação e oráculos da bateria live, com adaptadores locais e sem rede."""

from copy import deepcopy
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import with_judgments, sourced_plan
from trama.application.dialogue import Speech
from trama.application.game_runner import RunStatus
from trama.application.intents import ActionPlan, RuleIntent
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation
from trama.spatial import Position

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_npc_turn_completion.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_preparation_criteria_and_reset(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        @with_judgments
        def decide(context):
            if context['phase'] != 'npc_turn':
                return WorldPlan()
            # Destino deliberadamente além dos 9 m: força o ramo do bug original.
            actions = (WorldAction('watcher', 'move', 'O vigia avança.', destination=Position(3, 2)),)
            if case['expected'] == 'attack':
                actions += (WorldAction('watcher', 'attack', 'O vigia ataca.', 'player', weapon='greatsword'),)
            return WorldPlan((WorldReaction(0, 0, actions),))

        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, context:
            sourced_plan(ActionPlan((RuleIntent('end_turn'),)), prompt))
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda context:
            Speech(on='O turno se conclui.') if context['allow_on'] else Speech(off='É seu turno.'))
        before = situation_state(game.flow.session)
        assert game.runner.start().status == RunStatus.COMPLETED
        result = game.runner.submit(case['prompt'])
        assert result.status == RunStatus.COMPLETED, result.error
        recorded = LIVE['record'](result, game)
        assert json.loads(json.dumps(recorded))['requests'][0]['context']['mode'] == 'turn_based'
        after = situation_state(game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result.report, result.requests)
        assert any(e.get('status') == 'movement_limited' for e in result.report.world_events)
        # Os critérios devem reprovar tanto o turno preso quanto movimento gratuito.
        for change in ('turn', 'movement'):
            broken = deepcopy(after)
            if change == 'turn':
                broken['combat']['active_id'] = 'watcher'
            else:
                broken['creatures']['watcher'] = [14, 3]
            assert LIVE['evaluate'](case, before, broken, result.report, result.requests)
        assert game.runner.submit('[É a vez de quem?]').status == RunStatus.COMPLETED
        assert situation_state(game.flow.session) == after
        assert game.runner.reset().status == RunStatus.COMPLETED
        assert situation_state(game.flow.session) == before

