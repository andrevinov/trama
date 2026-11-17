from conftest import world_actions
"""Falhas anteriores permanecem consultáveis sem repetir ações ou consumir recursos."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.actions import ActionBudget
from trama.application.conversation import Conversation, ExecutionReport
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, RequestPart, RuleIntent
from trama.application.session import GameSession
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position


@pytest.fixture
def blocked_guard(dice):
    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data).with_passage("guard_door", True)
    creatures = tuple(replace(c, position=Position(13, 5)) if c.id == "guard_2" else
                      replace(c, position=Position(14, 6)) if c.id == "guard_3" else c
                      for c in creatures_from_data(data["creatures"]))
    session = GameSession(scene.grid, MovementState(Position(12, 5)), scene, creatures, roller=dice(1, 2, 20))
    for id in ("guard_1", "guard_2"):
        session.encounter.states[id] = replace(session.encounter.states[id], hp=0)
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=7)
    session.encounter.start(("guard_3",))
    session.encounter.combat = replace(session.encounter.combat, round=2)
    session.budget = ActionBudget(action_used=True, bonus_action_used=True)
    session.encounter.roller = dice()
    return Conversation(session)


def failed_plan(*, prefix=False, extra_reaction=False):
    actions = ((WorldAction("guard_3", "move", "Avança pela sala.", destination=Position(14, 5)),) if prefix else ()) + (
        WorldAction("guard_3", "move", "Contorna o companheiro caído.", destination=Position(13, 4)),
        WorldAction("guard_3", "attack", "Ataca o Jogador.", "player"),
    )
    reactions = (WorldReaction(0, 0, actions),)
    if extra_reaction:
        reactions += (WorldReaction(0, 0, (WorldAction("guard_3", "wait", "Aguarda."),)),)
    return WorldPlan(reactions)


def test_original_failed_destination_is_structured_at_source(blocked_guard, capture_logs):
    conversation = blocked_guard
    with capture_logs() as stream:
        report = conversation.execute_npc_turn(failed_plan())
    assert report.stop_reason and len(report.failures) == 1
    failure = report.failures[0].context()
    assert failure["actor_id"] == "guard_3" and failure["actor_name"] == "Guarda 3"
    assert failure["operation"] == "move" and failure["code"] == "destination_blocked"
    assert failure["origin"] == failure["position_after"] == [15, 7]
    assert failure["destination"] == [14, 5]
    assert failure["obstacle"] == {"kind": "blocked_cell", "position": [14, 5]}
    assert "(14,5)" in failure["cause"] and "bloqueada" in failure["cause"]
    assert failure["skipped_actions"] == [{"actor_id": "guard_3", "operation": "attack", "target_id": "player", "destination": None}]
    assert [e['operation'] for e in world_actions(report.world_events)] == ['end_turn']
    assert report.world_events[-1]['fallback'] == 'end_turn'
    assert conversation.session.encounter.combat.active_id == "player"
    assert not conversation.session.encounter.roller.sides
    assert "destination_blocked" in stream.getvalue()
    assert "conversation.execution_recorded" in stream.getvalue()


def test_off_question_receives_failure_even_when_history_no_longer_contains_it(blocked_guard):
    conversation, session = blocked_guard, blocked_guard.session
    report = conversation.execute_npc_turn(failed_plan())
    conversation.finish(Speech(off="O destino foi rejeitado."), conversation.narration_context(report=report))
    before = (session.state, session.creatures, deepcopy(session.encounter.states),
              deepcopy(session.encounter.budgets), session.encounter.combat)
    for n in range(13):
        speech = conversation.prepare(f"[Pergunta off {n}]")
        conversation.narration_context(speech)  # Consultar não substitui o registro.
    speech = conversation.prepare("[Ele não me atacou por quê?]")
    context = conversation.narration_context(speech)
    assert context["execution"]["events"] == [] and context["execution"]["stop_reason"] is None
    previous = context["previous_execution"]
    assert previous["execution_id"] == report.execution_id
    assert previous["actor_id"] == "guard_3"
    assert previous["execution"]["failures"][0]["destination"] == [14, 5]
    assert previous["situation"]["combat"]["active_id"] == "player"
    assert not previous["situation"]["turn_pending"]
    assert "O destino foi rejeitado" not in json.dumps(context["history"], ensure_ascii=False)
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(status="completed", output=[], output_text=json.dumps({
        "on": "", "off": "O Guarda 3 tentou ir para (14,5), uma casa bloqueada. O movimento foi rejeitado, o ataque seguinte não aconteceu e o turno dele foi encerrado.",
    }))
    reply = OpenAINarrator(client).narrate(context)
    final = conversation.finish(reply, context)
    sent = json.loads(client.responses.create.call_args.kwargs["input"])
    assert sent["previous_execution"] == previous
    assert not final.on and "ataque seguinte não aconteceu" in final.off
    assert (session.state, session.creatures, session.encounter.states,
            session.encounter.budgets, session.encounter.combat) == before
    assert not session.encounter.roller.sides


def test_context_is_a_copy_and_new_attempt_replaces_failure(blocked_guard):
    conversation = blocked_guard
    first = conversation.execute_npc_turn(failed_plan())
    copied = conversation.narration_context()["previous_execution"]
    copied["execution"]["failures"][0]["cause"] = "Causa inventada"
    assert "Causa inventada" not in json.dumps(conversation.narration_context(), ensure_ascii=False)
    # No próximo turno real, o guarda aguarda sem repetir a falha anterior.
    conversation.session.execute(RuleIntent('end_turn'))
    second = conversation.execute_npc_turn(WorldPlan())
    current = conversation.narration_context(report=second)
    assert current["execution"]["execution_id"] == second.execution_id
    assert current["previous_execution"]["execution_id"] == first.execution_id
    question = conversation.prepare("[E agora?]")
    context = conversation.narration_context(question)
    assert context["previous_execution"]["execution_id"] == second.execution_id
    assert context["previous_execution"]["execution"]["failures"] == []
    assert not context["previous_execution"]["situation"]["turn_pending"]
    assert context["combat"]["active_id"] == "player"


def test_partial_world_progress_and_all_skipped_actions_are_preserved(blocked_guard):
    report = blocked_guard.execute_npc_turn(failed_plan(prefix=True, extra_reaction=True))
    assert len(world_actions(report.world_events)) == 2
    assert world_actions(report.world_events)[0]["traveled_meters"] == 1.5
    failure = report.failures[0].context()
    assert failure["origin"] == failure["position_after"] == [15, 6]
    assert [a["operation"] for a in failure["skipped_actions"]] == ["attack", "wait"]
    previous = blocked_guard.narration_context()["previous_execution"]
    assert previous["execution"]["reactions"][0]["changed"]
    assert previous["execution"]["player_movement"]["occurred"] is False
    assert blocked_guard.session.encounter.states["player"].hp == 7


def test_reset_clears_memory_even_when_conversation_is_reused(blocked_guard):
    blocked_guard.execute_npc_turn(failed_plan())
    blocked_guard.session.reset()
    assert blocked_guard.narration_context(initial=True)["previous_execution"] is None


def test_player_partial_failure_and_nonexecuting_question_do_not_lose_result():
    session = GameSession(Grid(8, 8, blocked=frozenset({Position(3, 1)})), MovementState(Position(1, 1)))
    conversation = Conversation(session)
    intent = MovementIntent((MovementSegment("east", 3),), False, "")
    report = conversation.execute(ActionPlan((intent, DoorIntent("open", "unknown"))))
    failure = report.failures[0].context()
    assert failure["origin"] == [2, 2] and failure["position_after"] == [3, 2]
    assert failure["destination"] == [4, 2] and failure["code"] == "blocked_cell"
    assert failure["skipped_actions"][0]["operation"] == "open"
    prompt = "Por que parei?"
    conversation.prepare(prompt)
    query_report = conversation.execute(ActionPlan((), (RequestPart(prompt, "question"),)))
    context = conversation.narration_context(report=query_report)
    assert context["previous_execution"]["execution_id"] == report.execution_id
    assert context["previous_execution"]["execution"]["player_movement"] == {
        "occurred": True, "traveled_meters": 1.5, "from": [2, 2], "to": [3, 2],
    }


def test_failure_is_kept_when_later_narration_fails(blocked_guard):
    report = blocked_guard.execute_npc_turn(failed_plan())
    blocked_guard.failure("O serviço de narração falhou.")
    context = blocked_guard.narration_context(blocked_guard.prepare("[O que aconteceu?]"))
    assert context["previous_execution"]["execution_id"] == report.execution_id
    assert context["previous_execution"]["execution"]["failures"][0]["code"] == "destination_blocked"


def test_merged_report_preserves_failure_and_identifies_latest_execution(blocked_guard):
    report = blocked_guard.execute_npc_turn(failed_plan())
    aggregate = ExecutionReport().merge(report)
    context = blocked_guard.narration_context(report=aggregate)
    assert context["execution"]["failures"] == [report.failures[0].context()]
    assert context["previous_execution"] is None  # A execução atual não aparece como anterior.


def test_blocked_body_is_reported_as_occupant_not_invented_wall(blocked_guard):
    action = WorldAction("guard_3", "move", "Tenta passar pela porta.", destination=Position(13, 5))
    report = blocked_guard.execute_npc_turn(WorldPlan((WorldReaction(0, 0, (action,)),)))
    failure = report.failures[0].context()
    assert failure["obstacle"]["kind"] == "occupied_cell"
    assert failure["obstacle"]["actor_id"] == "guard_2" and failure["obstacle"]["at_zero_hp"]
    assert "Guarda 2 (0 PV)" in failure["cause"]
