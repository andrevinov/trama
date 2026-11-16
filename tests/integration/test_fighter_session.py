from conftest import scripted_responses, sourced_output, sourced_plan
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.actions import ActionBudget
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, RuleIntent
from trama.application.session import GameSession
from trama.characters import CharacterError, new_fighter, sheet_from_data
from trama.creatures import Creature, creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, InterpretationError, parse_plan
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position


@pytest.fixture
def session(dice):
    # Campeão rola dois d20; os três guardas idênticos usam uma rolagem de grupo.
    return GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                       creatures=(Creature("g1", "Guarda 1", Position(5, 4)),
                                  Creature("g2", "Guarda 2", Position(8, 4)),
                                  Creature("g3", "Guarda 3", Position(8, 5))),
                       roller=dice(15, 16, 10))


@pytest.fixture
def prison(dice):
    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    return GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                       creatures_from_data(data["creatures"]), roller=dice(15, 16, 10),
                       player_sheet=sheet_from_data(data["player"], id="player", name="Jogador"),
                       enemy_sheets=tuple(sheet_from_data(c["sheet"], id=c["id"], name=c["name"])
                                          for c in data["creatures"]))


def test_character_sheet_and_enemy_summaries_follow_visibility(prison):
    context = prison.interpreter_context()
    assert context["player_sheet"]["level"] == 3
    assert context["player_sheet"]["hp"] == 28
    assert context["player_sheet"]["subclass"] == "Campeão"
    assert context["visible_enemies"] == [] and context["combat"] is None
    assert len(context["world"]["npcs"]) == 3
    assert context["visible_creatures"] == []
    with pytest.raises(CharacterError, match="participantes"):
        prison.execute(RuleIntent("start_combat"))
    prison.execute(MovementIntent((), True, "", "guard_door"))
    prison.execute(DoorIntent("open", "guard_door"))
    visible = prison.visible_enemy_summaries()
    assert len(visible) == 3
    assert all(e["level"] == 1 and e["hp"] == 12 and e["armor_class"] == 17 for e in visible)
    assert prison.encounter.combat is None  # Ver inimigos não inicia combate por conta própria.
    prison.next_turn()
    prison.execute(DoorIntent("close", "guard_door"))
    assert prison.visible_enemy_summaries() == []


@pytest.mark.parametrize("hp", [0, 1, 12])
def test_sheet_hp_flag_does_not_describe_combat_status(session, hp):
    for actor in ("player", "g1"):
        session.encounter.states[actor] = replace(session.encounter.states[actor], hp=hp)
    context = session.interpreter_context()
    assert context["combat"] is None
    guard = next(enemy for enemy in context["visible_enemies"] if enemy["id"] == "g1")
    for summary in (context["player_sheet"], guard):
        assert summary["at_zero_hp"] is (hp == 0)
        assert "out_of_combat" not in summary


def test_guards_wait_without_automatic_attacks_and_turn_wraps(session):
    session.execute(RuleIntent("start_combat"))
    player = session.encounter.player_id
    states = session.encounter.states.copy()
    creatures = session.creatures
    order = []
    for _ in range(4):
        session.next_turn()
        order.append(session.encounter.combat.active_id)
        assert session.encounter.states == states
        assert session.creatures == creatures
    assert order == ["g1", "g2", "g3", player]
    assert session.encounter.combat.round == 2
    assert session.state.turn == 2


def test_guard_initiative_can_block_player_until_own_turn(dice):
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(2, 3, 20))
    session.execute(RuleIntent("start_combat"))
    old = session.state
    with pytest.raises(CharacterError, match="Aguarde"):
        session.execute(MovementIntent((MovementSegment("south", 1),), False, ""))
    assert session.state == old and session.budget == ActionBudget()
    session.next_turn()
    session.execute(MovementIntent((MovementSegment("south", 1),), False, ""))
    assert session.state.position == Position(4, 5)


def test_invalid_attack_requires_visible_target_and_melee_reach_before_starting_conflict(session, dice):
    for target in ("g2", "invented"):
        with pytest.raises(CharacterError):
            session.execute(RuleIntent("attack", target))
    assert session.budget == ActionBudget()
    session.execute(RuleIntent("start_combat"))
    roller = dice()
    session.encounter.roller = roller
    with pytest.raises(CharacterError, match="Aproxime"):
        session.execute(RuleIntent("attack", "g2"))
    with pytest.raises(CharacterError, match="visível"):
        session.execute(RuleIntent("attack", "invented"))
    assert roller.sides == [] and session.budget == ActionBudget()


def test_failed_hidden_attack_does_not_spend_action_or_inspiration(prison):
    old = prison.encounter.states.copy()
    with pytest.raises(CharacterError):
        prison.execute(RuleIntent("attack", "guard_1", use_inspiration=True))
    assert prison.encounter.states == old and prison.budget == ActionBudget()


def test_dash_can_repeat_only_with_action_surge(session):
    session.execute(RuleIntent("start_combat"))
    session.execute(MovementIntent((), True, ""))
    failed = session.execute(MovementIntent((), True, ""))
    assert failed.stop_reason and "Dash indisponível" in failed.stop_reason
    assert session.state.dash_uses == 1 and session.state.remaining_meters == 18
    session.execute(RuleIntent("action_surge"))
    session.execute(MovementIntent((), True, ""))
    assert session.state.dash_uses == 2 and session.state.remaining_meters == 27
    for _ in range(4):
        session.next_turn()
    assert session.state.dash_uses == 0 and session.state.remaining_meters == 9
    assert session.encounter.states["player"].action_surge_uses == 0


def test_immediate_champion_movement_has_separate_protected_allowance(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.roller = dice(19)
    session.execute(RuleIntent("attack", "g1", "unarmed"))
    assert session.state.free_meters == Decimal("4.5")
    assert session.state.remaining_meters == Decimal("13.5")
    moved = session.execute(MovementIntent((MovementSegment("south", 2),), False, ""))
    assert moved.protected_meters == 3
    assert session.state.spent_meters == 0 and session.state.free_meters == Decimal("1.5")
    session.execute(RuleIntent("action_surge"))
    assert session.state.free_meters == 0 and session.state.remaining_meters == 9


def test_invalid_action_preserves_pending_critical_movement(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.roller = dice(19)
    session.execute(RuleIntent("attack", "g1", "unarmed"))
    old = session.state
    with pytest.raises(CharacterError):
        session.execute(RuleIntent("attack", "invented"))
    assert session.state == old


def test_unavailable_dash_still_uses_critical_movement_when_possible(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.roller = dice(19)
    session.execute(RuleIntent("attack", "g1", "unarmed"))
    moved = session.execute(MovementIntent((MovementSegment("south", 1),), True, ""))
    assert moved.stop_reason and "Dash indisponível" in moved.stop_reason
    assert moved.protected_meters == Decimal("1.5")
    assert session.state.spent_meters == 0 and session.state.free_meters == 3


def test_sheet_speed_controls_chain_mail_strength_penalty(dice):
    from trama.characters import Abilities, FighterSheet
    sheet = FighterSheet("player", "Jogador", abilities=Abilities(strength=12))
    with pytest.raises(CharacterError, match="velocidade"):
        GameSession(Grid(10, 10), MovementState(Position(4, 4)), player_sheet=sheet, roller=dice())
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4), sheet.speed_meters),
                          player_sheet=sheet, roller=dice())
    assert session.state.remaining_meters == session.character_context()["speed_meters"] == 6


def test_second_wind_uses_bonus_action_while_normal_action_stays_available(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=12)
    session.encounter.roller = dice(4)
    report = Conversation(session).execute(ActionPlan((RuleIntent("second_wind"), RuleIntent("second_wind"))))
    assert report.progress and "bônus" in report.stop_reason
    assert report.events[0]["healing"] == 7
    assert session.encounter.states["player"].hp == 19
    assert session.budget.action_available and session.budget.bonus_action_used


def test_partial_combat_plan_stops_at_first_impediment_and_narrates_only_facts(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.roller = dice(15, 1, 2)
    conversation = Conversation(session)
    report = conversation.execute(ActionPlan((RuleIntent("attack", "g1", "flail"),
                                              RuleIntent("attack", "g1", "flail"),
                                              MovementIntent((MovementSegment("south", 1),), False, ""))))
    assert report.progress and "ação" in report.stop_reason
    assert report.unperformed_steps == 1 and len(report.events) == 1
    assert session.encounter.states["g1"].hp == 7
    assert session.state.position == Position(4, 4)
    context = conversation.narration_context(Speech("Ataque duas vezes e ande."), report)
    assert context["execution"]["events"][0]["damage"] == 5
    assert context["execution"]["reactions"] == []
    assert context["player_sheet"]["hp"] == 28
    reply = conversation.finish(Speech("Você acertou o guarda."), context)
    assert reply.on and "Parei" in reply.off and "etapas seguintes" in reply.off


def test_zero_hp_skips_turns_and_combat_ends_without_restoring_class_resources(session):
    session.execute(RuleIntent("start_combat"))
    session.execute(RuleIntent("action_surge"))
    for id in ("g1", "g2", "g3"):
        session.encounter.states[id] = replace(session.encounter.states[id], hp=0)
    event = session.execute(RuleIntent("end_turn")).event
    assert event["operation"] == "end_combat"
    assert session.encounter.combat is None
    assert session.budget == ActionBudget() and session.state.remaining_meters == 9
    assert session.encounter.states["player"].action_surge_uses == 0


def test_reset_restores_sheets_resources_and_ends_combat(session, dice):
    session.execute(RuleIntent("start_combat"))
    session.encounter.roller = dice(15, 1, 2)
    session.execute(RuleIntent("attack", "g1", "flail"))
    session.execute(RuleIntent("action_surge"))
    session.reset()
    assert session.encounter.combat is None
    assert session.encounter.states["player"] == new_fighter(session.encounter.player_sheet)
    assert session.encounter.states["g1"].hp == 12
    assert session.state == session.initial_state


def test_mock_openai_combat_plan_cannot_supply_dice_or_damage(session, dice):
    payload = {"steps": [{"operation": "attack", "target_id": "g1",
                           "weapon": "unarmed", "use_inspiration": False}]}
    client = Mock()
    client.responses.create.side_effect = scripted_responses(SimpleNamespace(status="completed", output=[], output_text=json.dumps(payload)))
    plan = OpenAIIntentInterpreter(client).interpret("Soque o Guarda 1.", session.interpreter_context())
    # Troca o dado local, não a saída simulada da IA.
    session.encounter.roller = dice(15, 16, 10, 19)
    report = Conversation(session).execute(plan)
    assert report.events[-1]["critical"] and report.events[-1]["damage"] == 4
    assert client.responses.create.call_args.kwargs["text"]["format"]["strict"]
    for change in ({"damage": 99}, {"hp": 0}, {"dice": [20]}):
        invalid = {"steps": [{**payload["steps"][0], **change}]}
        with pytest.raises(InterpretationError):
            parse_plan(json.dumps(invalid))


@pytest.mark.parametrize("changes", [
    {"operation": "cast_spell"}, {"weapon": "unknown"}, {"target_id": None},
    {"use_inspiration": "true"}, {"operation": "second_wind", "target_id": "g1"},
    {"operation": "start_combat", "target_id": None, "use_inspiration": True},
])
def test_invalid_rule_intents_are_rejected(changes):
    payload = {"operation": "attack", "target_id": "g1", "weapon": "greatsword", "use_inspiration": False}
    with pytest.raises(InterpretationError):
        parse_plan(json.dumps({"steps": [{**payload, **changes}]}))
