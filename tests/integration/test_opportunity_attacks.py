from conftest import world_actions
"""Oportunidades durante movimentos reais; dados fixos e nenhuma chamada à IA."""

from dataclasses import replace
from decimal import Decimal

import pytest

from trama.application.conversation import Conversation
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, RuleIntent
from trama.application.session import GameSession
from trama.application.travel import TravelExecutor
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.actions import ActionBudget
from trama.characters import CharacterError, FighterSheet
from trama.creatures import Creature
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position


def walking(direction, squares=1):
    return MovementIntent((MovementSegment(direction, squares),), False, "")


def encounter(dice, *, npc_turn=False, grid=None, player=None, enemies=None, enemy_sheets=None):
    session = GameSession(grid or Grid(8, 8), player or MovementState(Position(2, 3)),
                          creatures=enemies or (Creature("g1", "Guarda 1", Position(3, 3)),),
                          enemy_sheets=enemy_sheets, roller=dice(1, 2, 20) if npc_turn else dice(20, 19, 1))
    session.encounter.start(tuple(c.id for c in session.creatures))
    session.encounter.roller = dice()
    return session


def fleeing_plan():
    return WorldPlan((WorldReaction(0, 0, (
        WorldAction("g1", "move", "O guarda recua.", destination=Position(5, 3)),
        WorldAction("g1", "say", "Não vou me render!"),
    )),))


def test_guard_opportunity_uses_reaction_before_exit_not_normal_action(dice, capture_logs):
    session = encounter(dice)
    session.encounter.roller = dice(1)  # Graze no erro: 3 de dano, sem rolar dano.
    with capture_logs() as stream:
        report = Conversation(session).execute(ActionPlan((walking("west"),)))
    assert report.stop_reason is None
    assert session.state.position == Position(1, 3)
    assert session.encounter.states["player"].hp == 25
    assert session.encounter.budgets["g1"].reaction_used
    assert not session.encounter.budgets["g1"].action_used
    assert not session.budget.action_used and session.encounter.combat.active_id == "player"
    reaction = world_actions(report.world_events)[0]
    assert reaction["operation"] == "opportunity_attack"
    assert reaction["before_leaving"] == [3, 4] and reaction["destination"] == [2, 4]
    assert "reaction.opportunity_resolved" in stream.getvalue()
    session.execute(walking("east"))
    session.execute(walking("west"))  # Reentrar e sair de novo não concede outra reação.
    assert session.encounter.states["player"].hp == 25


def test_entering_and_circling_inside_reach_do_not_provoke(dice):
    session = encounter(dice, player=MovementState(Position(1, 2)))
    session.execute(walking("east"))
    session.execute(walking("south"))
    assert not session.encounter.roller.sides
    assert not session.encounter.budgets["g1"].reaction_used


@pytest.mark.parametrize("blocked,exhausted", [(True, False), (False, True)])
def test_impossible_step_does_not_provoke(dice, blocked, exhausted):
    grid = Grid(8, 8, blocked=frozenset({Position(1, 3)}) if blocked else frozenset())
    player = MovementState(Position(2, 3), spent_meters=9 if exhausted else 0)
    session = encounter(dice, grid=grid, player=player)
    result = session.execute(walking("west"))
    assert result.stop_reason and session.state.position == Position(2, 3)
    assert not session.encounter.budgets["g1"].reaction_used
    assert not session.encounter.roller.sides


def test_champion_protected_movement_does_not_provoke(dice):
    session = encounter(dice, player=MovementState(Position(2, 3), spent_meters=9, free_meters=Decimal("1.5")))
    result = session.execute(walking("west"))
    assert result.protected_meters == Decimal("1.5")
    assert session.state.position == Position(1, 3)
    assert not session.encounter.roller.sides


def test_invisible_mover_and_narrated_mode_do_not_trigger(dice):
    session = encounter(dice)
    session.scene = Scene(session.grid, (), (), dark=frozenset({session.state.position}))
    session.execute(walking("west"))
    assert not session.encounter.roller.sides
    session.scene = None
    session.encounter.combat = None
    session.execute(walking("east"))
    session.execute(walking("west"))
    assert not session.encounter.roller.sides


def test_opportunity_at_zero_hp_stops_before_exit(dice):
    session = encounter(dice)
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=3)
    session.encounter.roller = dice(1)
    report = Conversation(session).execute(ActionPlan((walking("west"), RuleIntent("second_wind"))))
    assert session.encounter.states["player"].hp == 0
    assert session.state.position == Position(2, 3) and session.state.spent_meters == 0
    assert report.stop_reason and report.unperformed_steps == 1
    assert world_actions(report.world_events)[0]["damage"] == 3


def test_slow_from_opportunity_recalculates_budget_before_exit(dice):
    sheet = FighterSheet("g1", "Guarda 1", level=1, subclass=None, weapons=("javelin",))
    session = encounter(dice, player=MovementState(Position(2, 3), spent_meters=Decimal("7.5")), enemy_sheets=(sheet,))
    session.encounter.roller = dice(15, 1, 2)
    result = session.execute(walking("west"))
    assert "Movimento insuficiente" in result.stop_reason
    assert session.state.position == Position(2, 3)
    assert session.state.speed_reduction_meters == 3 and session.state.remaining_meters == 0
    assert session.encounter.budgets["g1"].reaction_used


@pytest.mark.parametrize("accept", [True, False])
def test_player_confirms_once_then_npc_resumes_without_repeating_actions(dice, accept):
    session = encounter(dice, npc_turn=True)
    conversation = Conversation(session)
    report = conversation.execute_npc_turn(fleeing_plan())
    assert session.pending_opportunity and conversation.pending_npc_turn
    assert session.creatures[0].position == Position(3, 3)
    assert len(world_actions(report.world_events)) == 1 and not world_actions(report.world_events)[0]["changed"]
    assert not session.budget.action_used and not session.budget.reaction_used
    assert not session.encounter.roller.sides
    session.encounter.roller = dice(1) if accept else dice()
    event = TravelExecutor(session).resolve(accept)
    assert event["operation"] == ("opportunity_attack" if accept else "opportunity_declined")
    assert session.budget.reaction_used is accept and not session.budget.action_used
    assert session.encounter.states["g1"].hp == (9 if accept else 12)
    continuation = conversation.pending_npc_turn
    report = conversation.execute_npc_turn(continuation)
    assert not report.stop_reason and session.pending_opportunity is None
    assert session.creatures[0].position == Position(5, 3)
    assert session.encounter.combat.active_id == "player"
    assert not session.budget.reaction_used  # Recuperada só ao começar o turno do Jogador.
    assert sum(e["operation"] == "say" for e in report.world_events) == 1
    with pytest.raises(CharacterError, match="aguardando"):
        TravelExecutor(session).resolve(accept)


def test_player_opportunity_can_end_conflict_without_executing_dead_npc_actions(dice):
    session = encounter(dice, npc_turn=True)
    session.encounter.states["g1"] = replace(session.encounter.states["g1"], hp=3)
    conversation = Conversation(session)
    conversation.execute_npc_turn(fleeing_plan())
    session.encounter.roller = dice(1)
    TravelExecutor(session).resolve(True)
    report = conversation.execute_npc_turn(conversation.pending_npc_turn)
    assert not report.stop_reason and session.encounter.combat is None
    assert session.creatures[0].position == Position(3, 3)
    assert not any(e["operation"] == "say" for e in report.world_events)


def test_explicit_automatic_policy_resolves_player_reaction_and_resumes_turn(dice):
    session = encounter(dice, npc_turn=True)
    session.auto_opportunity = True  # Autorização explícita do controlador, não decisão da IA.
    session.encounter.roller = dice(1)
    report = Conversation(session).execute_npc_turn(fleeing_plan())
    assert not report.stop_reason and session.pending_opportunity is None
    assert world_actions(report.world_events)[0]["reactions"][0]["operation"] == "opportunity_attack"
    assert session.creatures[0].position == Position(5, 3)


def test_reset_clears_pending_opportunity_and_reaction_budget(dice):
    session = encounter(dice, npc_turn=True)
    Conversation(session).execute_npc_turn(fleeing_plan())
    session.reset()
    assert session.pending_opportunity is None and session.suppressed_opportunity is None
    assert not session.budget.reaction_used


def test_spent_action_and_bonus_do_not_block_off_turn_reaction(dice):
    session = encounter(dice, npc_turn=True)
    session.budget = ActionBudget(action_used=True, bonus_action_used=True, extra_actions=1)
    conversation = Conversation(session)
    conversation.execute_npc_turn(fleeing_plan())
    session.encounter.roller = dice(1)
    TravelExecutor(session).resolve(True)
    assert session.budget == ActionBudget(action_used=True, bonus_action_used=True, extra_actions=1, reaction_used=True)


def test_multiple_opponents_each_have_a_reaction_in_scenario_order(dice):
    session = encounter(dice, enemies=(Creature("g1", "Guarda 1", Position(3, 2)),
                                       Creature("g2", "Guarda 2", Position(3, 4))))
    session.encounter.roller = dice(1, 1)
    report = Conversation(session).execute(ActionPlan((walking("west"),)))
    assert [r["actor_id"] for r in world_actions(report.world_events)] == ["g1", "g2"]
    assert session.encounter.states["player"].hp == 22
    assert all(session.encounter.budgets[g].reaction_used for g in ("g1", "g2"))


def test_resume_preserves_prior_move_and_declining_does_not_suppress_later_opportunity(dice):
    session = encounter(dice, npc_turn=True, enemies=(Creature("g1", "Guarda 1", Position(3, 2)),))
    plan = WorldPlan((WorldReaction(0, 0, (
        WorldAction("g1", "move", "O guarda dá um passo ao lado.", destination=Position(3, 3)),
        WorldAction("g1", "move", "O guarda recua.", destination=Position(5, 3)),
        WorldAction("g1", "move", "O guarda volta.", destination=Position(3, 3)),
        WorldAction("g1", "move", "O guarda recua de novo.", destination=Position(5, 3)),
    )),))
    conversation = Conversation(session)
    report = conversation.execute_npc_turn(plan)
    assert len(world_actions(report.world_events)) == 2
    assert session.creatures[0].position == Position(3, 3)
    assert session.npc_movement["g1"].spent_meters == Decimal("1.5")
    TravelExecutor(session).resolve(False)
    report = conversation.execute_npc_turn(conversation.pending_npc_turn)
    assert session.pending_opportunity is not None
    assert session.npc_movement["g1"].spent_meters == Decimal("7.5")
    assert not session.budget.reaction_used
    assert not session.encounter.roller.sides
