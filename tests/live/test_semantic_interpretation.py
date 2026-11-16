"""Frases reais: somente interpretação, uma chamada por caso, sem executar o plano."""

import json
import os
from pathlib import Path

import pytest
from openai import OpenAI

from trama.application.conversation import Conversation
from trama.application.interpretation_evaluation import evaluate_plan
from trama.application.intents import RuleIntent
from trama.application.session import GameSession
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Position

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("RUN_OPENAI_LIVE_TESTS") != "1",
                                                reason="Requer autorização explícita de chamadas pagas.")]


@pytest.mark.parametrize("prompt,expected", [
    ("Eu uso Surto de Ação para atacar novamente o guarda atacado anteriormente com a espada.",
     [{"operation": "action_surge"}, {"operation": "attack", "target_id": "guard_1", "weapon": "greatsword"}]),
    ("Eu volto para o primeiro quadrado antes da porta (14,6) e fico de frente pra sala.",
     [{"operation": "move", "segments": [{"direction": "west", "meters": 1.5}]}]),
    ("Eu retorno para (13,6) e fico de frente pra sala dos guardas.",
     [{"operation": "move", "segments": [{"direction": "west", "meters": 3}]}]),
    ("Posso usar Retomar o Fôlego?", []),
    ("Não uso Retomar o Fôlego.", []),
    ("Eu fico parado na mesma posição.", [{"operation": "end_turn"}]),
    ("Não faço nada.", [{"operation": "end_turn"}]),
    ("Não faço mais nada neste turno.", [{"operation": "end_turn"}]),
    ("Aguardo.", [{"operation": "end_turn"}]),
    ("Fico parado e uso Retomar o Fôlego.", [{"operation": "second_wind"}]),
    ("Não quero encerrar meu turno.", []),
])
def test_real_semantic_interpretation(prompt, expected, tmp_path, capture_logs, dice):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY não configurada")
    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data).with_passage("guard_door", True)
    session = GameSession(scene.grid, MovementState(Position(14, 5)), scene,
                          creatures_from_data(data["creatures"]), roller=dice(20, 19, 1, 1))
    session.execute(RuleIntent("start_combat"))
    session.execute(RuleIntent("attack", "guard_1"))
    resources, position = session.encounter.states.copy(), session.state
    with capture_logs(log_file=tmp_path / "trace.jsonl"), OpenAI(timeout=30, max_retries=0) as client:
        plan = OpenAIIntentInterpreter(client, max_corrections=0).interpret(prompt, Conversation(session).interpretation_context())
    result = evaluate_plan(expected, plan)
    (tmp_path / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert result["matches_expected"], f"Resultado divergente; evidências em {tmp_path}"
    assert session.encounter.states == resources and session.state == position
