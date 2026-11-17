"""Preparação e critérios live com adaptadores locais; nenhuma chamada paga."""

from copy import deepcopy
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import with_judgments, sourced_plan
from trama.application.dialogue import Speech
from trama.application.game_runner import RunStatus
from trama.application.intents import ActionPlan, MovementIntent, NarrativeIntent, RuleIntent
from trama.application.parley import InfluenceRequest
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation
from trama.spatial import Position
from trama.social import DispositionAssessment, PersonaEffect

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_parley.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_situation_and_independent_criteria_through_real_runner(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        def interpret(prompt, context):
            intent = (MovementIntent((), False, '', 'cell_4') if prompt == case['messages'][0] else
                RuleIntent('attack', 'guard_1', 'unarmed') if case['expected'] == 'attack' else NarrativeIntent(prompt, 'speak', volume='loud'))
            return sourced_plan(ActionPlan((intent,)), prompt)

        @with_judgments
        def decide(context):
            if context['phase'] == 'npc_turn':
                return WorldPlan((WorldReaction(0, 0, (WorldAction('guard_1', 'move', 'O guarda avança 9 m.', destination=Position(8, 10)),)),))
            if context['parley'] and context['parley']['status'] == 'pending' and case['expected'] != 'attack':
                return WorldPlan((WorldReaction(0, None, (WorldAction('guard_1', 'influence', 'O guarda considera ouvir a explicação.',
                    influence=InfluenceRequest(skill='persuasion', assessment=DispositionAssessment(
                        'listen','player','Ouvir brevemente mantendo a custódia.',0,0,'Pedido neutro.',
                        tuple(PersonaEffect(i.id,0,'Pedido neutro.') for i in game.flow.session.social.profiles['guard_1'].persona.interests),(),
                        'Fique onde está. Vou ouvir.','Não. Volte à cela.',('Manter custódia e posição.',)))),)),))
            return WorldPlan()

        game.flow.interpreter = SimpleNamespace(interpret=interpret)
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda context: Speech(on='Os acontecimentos são narrados.'))
        assert game.runner.start().status == RunStatus.COMPLETED
        detected = None
        for index, prompt in enumerate(case['messages']):
            result = game.runner.submit(prompt)
            assert result.status == RunStatus.COMPLETED, result.error
            after = situation_state(game.flow.session)
            errors = (LIVE['evaluate_detection'](after, result.report, result.requests) if index == 0 else
                LIVE['evaluate_resolution'](case['expected'], detected, after, result.report, result.requests))
            assert not errors, errors
            if index == 0:
                # O oráculo independente precisa reprovar a posição do bug original.
                mutated = deepcopy(after)
                mutated['creatures']['guard_1'] = [9, 16]
                assert LIVE['evaluate_detection'](mutated, result.report, result.requests)
            detected = after
        assert not roller.pending
        assert game.runner.reset().status == RunStatus.COMPLETED
        reset = situation_state(game.flow.session)
        assert reset['parley'] is None and reset['creatures']['guard_1'] == [11, 4]
        assert reset['position'] == [8, 22] and not roller.used
