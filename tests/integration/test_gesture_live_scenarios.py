"""Preparação e controles negativos dos novos lives, sem rede."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from conftest import sourced_plan, judged_world
from trama.agency import IntentDecision
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, GestureIntent
from trama.application.situations import load_situation, situation_state
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.bootstrap import open_situation
from trama.difficulty import Adjudication

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_gestural_communication_live.py'))


@pytest.mark.parametrize('case', LIVE['CASES'], ids=[c['id'] for c in LIVE['CASES']])
def test_live_gesture_preparations_and_oracles(case, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    situation = load_situation(case['id'])
    roller = situation.new_roller()
    with open_situation(situation, roller=roller, allow_unconfigured=True) as game:
        game.flow.interpreter = SimpleNamespace(interpret=lambda prompt, ctx: sourced_plan(ActionPlan((
            GestureIntent(case['target'], 'Pisco um olho.' if case['subtle'] else 'Aceno com a mão.',
                          'Quero que confirme minha história.' if case['blocked'] else 'Quero que aguarde.', case['subtle']),)), prompt))
        def decide(ctx):
            if ctx['phase'] == 'npc_agency':
                return judged_world(WorldPlan((WorldReaction(0, None, (WorldAction(case['target'], 'wait',
                    'Observa o gesto e aguarda.'),)),), intent=IntentDecision(case['target'],
                        'Avaliar o sinal.', 'Aguarda uma explicação.', 'Explicação do jogador.')), ctx)
            judgments = tuple(Adjudication(r['id'],
                'automatic' if r['kind'] != 'visual_signal' or case['received'] else 'impossible', None,
                False, False, (next(iter(r['facts'])),), 'Condições explícitas do arranjo local.')
                for r in ctx['world']['adjudication']['requests'])
            return WorldPlan(adjudications=judgments)
        game.flow.world_director = SimpleNamespace(decide=decide)
        game.flow.narrator = SimpleNamespace(narrate=lambda ctx: Speech(on='Você faz o gesto, sem falar.')
            if ctx['allow_on'] else Speech(off='Não há linha de visão para o sinal.'))
        before = situation_state(game.flow.session)
        result = game.runner.submit(case['prompt'])
        after = situation_state(game.flow.session)
        assert not LIVE['evaluate'](case, before, after, result)
        bad = deepcopy(after)
        bad['position'] = [99, 99]
        assert LIVE['evaluate'](case, before, bad, result)
        broken = replace(result, report=replace(result.report, events=(), failures=()))
        assert LIVE['evaluate'](case, before, after, broken)
        assert not roller.pending and not roller.used
