"""Jogador e Mundo independentes, com decisões fixas e rolagens controladas."""

import json
from conftest import sourced_plan
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.actions import ActionBudget
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, NarrativeIntent, RuleIntent
from trama.application.modes import GameMode, MODE_INSTRUCTIONS
from trama.application.session import GameSession
from trama.application.world import PerceptionCheck, WorldAction, WorldError, WorldPlan, WorldReaction
from trama.application.world_resolution import WorldExecutor
from trama.characters import CharacterError
from trama.creatures import Creature, creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_plan, PLAN_SCHEMA
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector, parse_world_plan
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position


@pytest.fixture
def prison(dice):
    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                       creatures_from_data(data["creatures"]), roller=dice())


def move_to(target):
    return MovementIntent((), False, "", target)


def test_narrated_walk_reaches_door_without_dash_turn_or_resource_use(prison):
    conversation = Conversation(prison)
    before = prison.encounter.states.copy()
    report = conversation.execute(ActionPlan((move_to("guard_door"), DoorIntent("open", "guard_door"), move_to("guard_room"))))
    assert report.stop_reason is None
    assert prison.state.position == Position(14, 5)
    assert sum(e.get("traveled_meters", 0) for e in report.events) == 16.5
    assert prison.state.spent_meters == 0 and prison.state.turn == 1
    assert prison.budget == ActionBudget() and prison.encounter.states == before
    assert prison.mode == GameMode.NARRATED
    for _ in range(5):
        prison.execute(DoorIntent("close", "guard_door"))
        prison.execute(DoorIntent("open", "guard_door"))
    assert prison.budget == ActionBudget()


def test_repeated_prompts_do_not_exhaust_narrated_movement(prison):
    prison.execute(move_to("guard_door"))
    prison.execute(move_to("cell_gate"))
    result = prison.execute(move_to("guard_door"))
    assert result.stop_reason is None
    assert prison.state.position == Position(12, 5)
    assert prison.interpreter_context()["character"]["remaining_meters"] is None


def test_closed_door_is_real_impediment_in_narrated_mode(prison):
    report = Conversation(prison).execute(ActionPlan((move_to("guard_room"), NarrativeIntent("Procuro uma cadeira."))))
    assert prison.state.position == Position(12, 5)
    assert "fechada" in report.stop_reason
    assert report.unperformed_steps == 1 and report.progress
    assert not prison.encounter.roller.sides


def test_world_context_contains_hidden_npcs_but_perception_does_not(prison):
    conversation = Conversation(prison)
    context = conversation.world_context(ActionPlan((move_to("guard_door"),)))
    assert len(context["world"]["npcs"]) == 3
    assert all(not npc["visible_to_player"] for npc in context["world"]["npcs"])
    assert context["player_plan"][0]["operation"] == "move"
    assert len(context["player_plan"][0]["proposed_path"]) == 9
    narration = conversation.narration_context(initial=True)
    assert narration["perception"]["visible_creatures"] == []
    assert len(narration["world"]["npcs"]) == 3


@pytest.mark.parametrize("roll,interrupted", [(1, False), (20, True)])
def test_uncertain_guard_hearing_rolls_and_only_success_interrupts(prison, dice, roll, interrupted, capture_logs):
    prison.encounter.roller = dice(roll)
    conversation = Conversation(prison)
    reaction = WorldReaction(0, 3, (WorldAction("guard_1", "say", "Pare aí! Há alguém no corredor!"),),
                             True, "Um guarda ouviu os passos e exige que você pare.",
                             PerceptionCheck("guard_1", 12, "Ouvir passos vindos do corredor através da porta."))
    with capture_logs() as stream:
        report = conversation.execute(ActionPlan((move_to("guard_door"), DoorIntent("open", "guard_door"))), WorldPlan((reaction,)))
    assert bool(report.stop_reason) is interrupted
    assert prison.state.position == Position(6 if interrupted else 12, 5)
    assert report.world_events[0]["passed"] is interrupted
    assert report.world_events[0]["dice"] == [roll]
    assert prison.scene.passages[1].is_open is (not interrupted)
    assert report.unperformed_steps == int(interrupted)
    assert len(prison.last_path) == (4 if interrupted else 10)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert any(r["event"] == "world.check_resolved" for r in records)


def test_unreached_checkpoint_never_rolls_or_runs_world_action(prison):
    reaction = WorldReaction(0, 11, (WorldAction("guard_1", "say", "Ouvi alguém!"),),
                             check=PerceptionCheck("guard_1", 12, "Passos na sala."))
    report = Conversation(prison).execute(ActionPlan((move_to("guard_room"),)), WorldPlan((reaction,)))
    assert "fechada" in report.stop_reason
    assert report.world_events == () and not prison.encounter.roller.sides


def test_nonblocking_world_reply_preserves_remaining_distance_and_fraction(prison):
    intent = MovementIntent((MovementSegment("east", 6, Decimal("0.5")),), False, "")
    world = WorldPlan((WorldReaction(0, 2, (WorldAction("world", "describe", "O corredor cheira a pedra úmida."),)),))
    report = Conversation(prison).execute(ActionPlan((intent,)), world)
    assert prison.state.position == Position(9, 5)
    assert sum(e["traveled_meters"] for e in report.events) == 9
    assert "0,5 m" in report.stop_reason
    assert len(prison.last_path) == 7


def test_world_checkpoint_at_reached_endpoint_still_fires_with_fractional_remainder(prison):
    intent = MovementIntent((MovementSegment("east", 6, Decimal("0.5")),), False, "")
    world = WorldPlan((WorldReaction(0, 6, (WorldAction("guard_1", "say", "Quem anda aí?"),)),))
    report = Conversation(prison).execute(ActionPlan((intent,)), world)
    assert prison.state.position == Position(9, 5)
    assert "0,5 m" in report.stop_reason
    assert report.world_events[0]["text"] == "Quem anda aí?"


def test_narrative_player_intent_receives_world_dialogue_without_mechanical_action(prison):
    conversation = Conversation(prison)
    speech = conversation.prepare("Pergunto se tem alguém aí.")
    world = WorldPlan((WorldReaction(0, None, (WorldAction("guard_1", "say", "Quem está aí?"),)),))
    before = prison.state
    report = conversation.execute(sourced_plan(ActionPlan((NarrativeIntent(speech.on, "speak"),)), speech.on), world)
    assert prison.state == before and prison.budget == ActionBudget()
    assert not report.progress and report.narrative_interaction
    assert report.world_events[0]["speaker"] == "Guarda 1"
    assert report.world_events[0]["perceptible"]
    reply = conversation.finish(Speech('Do outro lado da porta, você ouve: "Quem está aí?"'), conversation.narration_context(speech, report))
    assert reply.on


def test_world_cannot_move_player_or_teleport_guard_through_closed_door(prison):
    with pytest.raises(WorldError, match="NPC existente"):
        WorldExecutor(prison).execute(WorldAction("player", "move", "Movimento imposto", destination=Position(10, 5)))
    origin = prison.creatures[1].position
    result = WorldExecutor(prison).execute(WorldAction("guard_2", "move", "O guarda caminha até o corredor.", destination=Position(12, 5)))
    assert prison.creatures[1].position == Position(14, 5)
    assert result["stop_reason"] and prison.creatures[1].position != origin
    assert not result["perceptible"]
    prison.reset()
    assert prison.creatures[1].position == origin


def test_guard_contours_door_corner_and_attacks_in_original_scenario(prison, dice, capture_logs):
    prison.execute(move_to("guard_door"))
    prison.execute(DoorIntent("open", "guard_door"))
    prison.encounter.roller = dice(1, 2, 20)
    prison.encounter.start(tuple(c.id for c in prison.creatures))
    assert prison.encounter.combat.active_id == "guard_1"
    prison.encounter.roller = dice(1)  # Erro no ataque; a rolagem comprova que houve tentativa válida.
    world = WorldPlan((WorldReaction(0, 0, (
        WorldAction("guard_1", "move", "O guarda avança pela lateral.", destination=Position(14, 4)),
        WorldAction("guard_1", "move", "O guarda alcança a porta aberta.", destination=Position(13, 5)),
        WorldAction("guard_1", "attack", "O guarda ataca.", "player"),
    )),))
    with capture_logs() as stream:
        report = Conversation(prison).execute_npc_turn(world)
    assert report.stop_reason is None
    assert prison.creatures[0].position == Position(13, 5)
    assert sum(e.get("cost_meters", 0) for e in report.world_events) == 4.5
    assert report.world_events[2]["operation"] == "attack"
    assert report.world_events[2]["hit"] is False
    assert prison.encounter.budgets["guard_1"].action_used
    assert prison.encounter.combat.active_id == "guard_2"
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    movements = [r["data"] for r in records if r["event"] == "movement.resolved"]
    assert movements[1]["path"] == [{"x": 14, "y": 4}, {"x": 14, "y": 5}, {"x": 13, "y": 5}]


def test_incomplete_npc_move_keeps_progress_and_skips_attack_and_later_reactions(prison, dice, capture_logs):
    prison.execute(move_to("guard_door"))
    prison.execute(DoorIntent("open", "guard_door"))
    prison.creatures = tuple(replace(c, position=Position(14, 4)) if c.id == "guard_1" else c
                             for c in prison.creatures)
    prison.encounter.roller = dice(1, 2, 20)
    prison.encounter.start(tuple(c.id for c in prison.creatures))
    prison.encounter.roller = dice()
    prison.npc_movement["guard_1"] = MovementState(Position(14, 4), spent_meters=Decimal("7.5"))
    world = WorldPlan((WorldReaction(0, 0, (
        WorldAction("guard_1", "move", "O guarda tenta alcançar a porta.", destination=Position(13, 5)),
        WorldAction("guard_1", "attack", "O guarda ataca.", "player"),
    )), WorldReaction(0, 0, (WorldAction("guard_1", "say", "Essa fala não deve acontecer."),))))
    with capture_logs() as stream:
        report = Conversation(prison).execute_npc_turn(world)
    assert "Movimento insuficiente" in report.stop_reason
    assert len(report.world_events) == 1
    assert report.world_events[0]["changed"]
    assert report.world_events[0]["cost_meters"] == 1.5
    assert prison.creatures[0].position == Position(14, 5)
    assert prison.npc_movement["guard_1"].spent_meters == 9
    assert prison.encounter.combat.active_id == "guard_1"
    assert not prison.encounter.budgets["guard_1"].action_used
    assert prison.encounter.states["player"].hp == 28
    assert not prison.encounter.roller.sides
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert not any(r["event"] == "world.action_started" and r["data"]["operation"] == "attack" for r in records)
    interruption = next(r["data"] for r in records if r["event"] == "world.reaction_interrupted")
    assert interruption["unperformed_actions"] == 1


def test_npc_stops_at_closed_door_without_executing_next_action(prison):
    events, reason = WorldExecutor(prison).reaction(WorldReaction(0, 0, (
        WorldAction("guard_2", "move", "O guarda tenta sair da sala.", destination=Position(12, 5)),
        WorldAction("guard_2", "say", "Já estou no corredor."),
    )))
    assert reason and len(events) == 1
    assert events[0]["stop_reason"]
    assert events[0]["changed"] and events[0]["cost_meters"] == 1.5
    assert prison.creatures[1].position == Position(14, 5)
    assert not prison.scene.passages[1].is_open


@pytest.mark.parametrize("destination", [Position(15, 5), Position(3, 5), Position(0, 0), Position(-1, 0)])
def test_npc_unreachable_or_occupied_destination_skips_remaining_actions(prison, destination):
    before = prison.creatures
    events, reason = WorldExecutor(prison).reaction(WorldReaction(0, 0, (
        WorldAction("guard_1", "move", "O guarda tenta avançar.", destination=destination),
        WorldAction("guard_1", "say", "Cheguei."),
    )))
    assert "Não há caminho" in reason
    assert not events and prison.creatures == before
    assert not prison.encounter.roller.sides


def test_explicit_attack_enters_turn_mode_and_respects_initiative(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(1, 2, 20))
    report = Conversation(session).execute(ActionPlan((RuleIntent("attack", "g1"),)))
    assert session.mode == GameMode.TURN_BASED and session.encounter.combat.active_id == "g1"
    assert session.encounter.states["g1"].hp == 12 and not session.budget.action_used
    assert "iniciativa" in report.stop_reason
    session.encounter.roller = dice(15, 1, 2)
    world = WorldPlan((WorldReaction(0, 0, (WorldAction("g1", "attack", "O guarda ataca com o mangual.", "player", weapon="flail"),)),))
    report = Conversation(session).execute_npc_turn(world)
    assert report.stop_reason is None
    assert session.encounter.states["player"].hp == 23
    assert session.encounter.combat.active_id == "player"
    assert session.encounter.states["player"].second_wind_uses == 2


def test_player_winning_initiative_executes_requested_attack(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1, 15, 1, 2))
    report = Conversation(session).execute(ActionPlan((RuleIntent("attack", "g1", "flail"),)))
    assert report.stop_reason is None
    assert report.events[0]["conflict_started"]["initiative"]
    assert session.encounter.states["g1"].hp == 7 and session.budget.action_used


def test_last_enemy_at_zero_hp_returns_to_narrated_mode_without_healing(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1, 15, 1, 2))
    session.encounter.states["g1"] = replace(session.encounter.states["g1"], hp=4)
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=10, second_wind_uses=1)
    report = Conversation(session).execute(ActionPlan((RuleIntent("attack", "g1", "flail"),)))
    assert session.mode == GameMode.NARRATED
    assert report.events[0]["conflict_ended"]["operation"] == "end_combat"
    assert session.encounter.states["player"].hp == 10
    assert session.encounter.states["player"].second_wind_uses == 1


def test_invalid_weapon_does_not_start_conflict_or_roll_dice(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice())
    report = Conversation(session).execute(ActionPlan((RuleIntent("attack", "g1", "longsword"),)))
    assert report.stop_reason and session.mode == GameMode.NARRATED
    assert not session.encounter.roller.sides


def test_partial_world_failure_keeps_completed_attack_in_report(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(1, 2, 20))
    WorldExecutor(session).execute(WorldAction("g1", "start_conflict", "O guarda inicia um confronto."))
    session.encounter.roller = dice(15, 1, 2)
    attack = WorldAction("g1", "attack", "O guarda ataca.", "player", weapon="flail")
    world = WorldPlan((WorldReaction(0, 0, (attack, attack)),))
    report = Conversation(session).execute_npc_turn(world)
    assert "já foi utilizada" in report.stop_reason
    assert len(report.world_events) == 1 and report.world_events[0]["damage"] == 5
    assert session.encounter.states["player"].hp == 23
    assert session.encounter.combat.active_id == "g1"  # Sem repetição nem avanço silencioso após erro.


def test_world_initiates_and_ends_conflict_without_buttons(prison, dice):
    conversation = Conversation(prison)
    prison.encounter.roller = dice(20, 19, 1)
    world = WorldPlan((WorldReaction(0, 3, (WorldAction("guard_1", "start_conflict", "Um guarda ordena que você pare e inicia um confronto."),)),))
    report = conversation.execute(ActionPlan((move_to("guard_door"),)), world)
    assert prison.state.position == Position(6, 5) and report.stop_reason
    assert prison.mode == GameMode.TURN_BASED
    prison.encounter.states["player"] = replace(prison.encounter.states["player"], second_wind_uses=1)
    WorldExecutor(prison).execute(WorldAction("guard_1", "end_conflict", "Os guardas aceitam uma trégua."))
    assert prison.mode == GameMode.NARRATED
    assert prison.encounter.states["player"].second_wind_uses == 1
    assert prison.budget == ActionBudget()


def test_world_npc_cannot_ignore_initiative_or_attack_twice(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1))
    WorldExecutor(session).execute(WorldAction("g1", "start_conflict", "O guarda se prepara para atacar."))
    with pytest.raises(CharacterError, match="Aguarde"):
        WorldExecutor(session).execute(WorldAction("g1", "attack", "O guarda ataca.", "player", weapon="flail"))
    session.execute(RuleIntent("end_turn"))
    session.encounter.roller = dice(15, 1, 2)
    attack = WorldAction("g1", "attack", "O guarda ataca.", "player", weapon="flail")
    WorldExecutor(session).execute(attack)
    with pytest.raises(ValueError, match="já foi utilizada"):
        WorldExecutor(session).execute(attack)


def test_all_ai_stages_receive_fixed_mode_logic_and_world_context(prison):
    from trama.infrastructure import openai_intent_interpreter, openai_narrator, openai_world_director
    for module in (openai_intent_interpreter, openai_narrator, openai_world_director):
        assert module.INSTRUCTIONS.startswith(MODE_INSTRUCTIONS)
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(status="completed", output=[], output_text='{"reactions":[]}')
    context = Conversation(prison).world_context(ActionPlan((move_to("guard_door"),)))
    assert OpenAIWorldDirector(client).decide(context) == WorldPlan()
    request = client.responses.create.call_args.kwargs
    assert request["text"]["format"]["name"] == "world_response"
    assert json.loads(request["input"])["world"]["npcs"][0]["id"] == "guard_1"
    assert request["store"] is False


@pytest.mark.parametrize("raw", ['{}', '{"reactions":null}', '{"reactions":[{}]}', '[]'])
def test_invalid_world_output_is_rejected(raw):
    with pytest.raises(WorldError):
        parse_world_plan(raw)


def test_attack_schema_requires_target_and_nonmechanical_actions_have_specific_names():
    branches = PLAN_SCHEMA["properties"]["steps"]["items"]["anyOf"]
    attack = next(b for b in branches if b["properties"]["operation"].get("enum") == ["attack"])
    assert attack["properties"]["target_id"]["type"] == "string"
    operations = {operation for branch in branches for operation in branch["properties"]["operation"]["enum"]}
    assert "narrative" not in operations
    assert {"look", "speak", "wait", "challenge"} <= operations
    assert parse_plan('{"steps":[{"operation":"look","text":"Observo o corredor."}]}').steps == (NarrativeIntent("Observo o corredor."),)


def test_original_text_only_walk_response_cannot_masquerade_as_executed_movement(prison):
    from trama.application.intents import InterpretationError

    # Resposta real de 15/11: a caminhada foi indevidamente reduzida a texto.
    raw = '{"steps":[{"operation":"narrative","text":"O Jogador pretende caminhar na direção da porta da Sala dos Guardas."}]}'
    with pytest.raises(InterpretationError):
        parse_plan(raw)
    assert prison.state == prison.initial_state


def test_looking_enables_narration_without_claiming_state_progress_or_movement(prison):
    conversation = Conversation(prison)
    speech = conversation.prepare("Observo o corredor.")
    report = conversation.execute(sourced_plan(ActionPlan((NarrativeIntent(speech.on, "look"),)), speech.on))
    context = conversation.narration_context(speech, report)
    assert not report.progress and report.narrative_interaction
    assert context["allow_on"]
    assert context["execution"]["player_movement"] == {
        "occurred": False, "traveled_meters": 0, "from": [4, 6], "to": [4, 6],
    }
    reply = conversation.finish(Speech("Da cela, você vê a grade aberta e o corredor."), context)
    assert reply.on and prison.state == prison.initial_state


def test_move_then_speak_keeps_physical_progress_separate_from_interaction(prison):
    conversation = Conversation(prison)
    report = conversation.execute(ActionPlan((move_to("guard_door"), NarrativeIntent("Chamo um guarda.", "speak"))))
    assert report.progress and report.narrative_interaction
    context = conversation.narration_context(report=report)
    assert context["execution"]["player_movement"] == {
        "occurred": True, "traveled_meters": 13.5, "from": [4, 6], "to": [13, 6],
    }
