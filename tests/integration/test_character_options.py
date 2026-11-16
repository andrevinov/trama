"""A ficha consulta os recursos reais sem executar ações ou rolagens."""

from dataclasses import replace
from decimal import Decimal

import pytest

from trama.actions import ActionBudget
from trama.application.intents import MovementIntent, RuleIntent
from trama.application.session import GameSession
from trama.characters import finish_long_rest, finish_short_rest
from trama.creatures import Creature
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position


def options(session):
    return {item["id"]: item for section in session.character_options() for item in section["items"]}


@pytest.fixture
def session(dice):
    return GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                       creatures=(Creature("g1", "Guarda 1", Position(5, 4)),), roller=dice())


def start(session, dice):
    session.encounter.roller = dice(20, 19, 1)
    session.execute(RuleIntent("start_combat"))


def test_narrated_options_distinguish_exploration_and_unimplemented_commands(session):
    rows = options(session)
    assert rows["move"]["status"] == "available"
    assert rows["move"]["summary"] == "Sem limite de turno"
    assert rows["attack"]["status"] == "conditional"
    assert "Iniciativa" in rows["attack"]["reason"]
    assert rows["action_surge"]["status"] == "unavailable"
    assert rows["end_turn"]["status"] == "unavailable"
    for id in ("ready", "tactical_mind", "recovery", "magic_items"):
        assert rows[id]["status"] == "not_implemented"
    assert rows["reaction"]["status"] == "conditional"
    assert "Nenhum efeito" in rows["magic_items"]["summary"]


def test_attack_and_action_surge_options_follow_real_action_budget(session, dice):
    start(session, dice)
    assert options(session)["attack"]["status"] == "available"
    session.encounter.roller = dice(1, 1)
    session.execute(RuleIntent("attack", "g1", "flail"))
    assert options(session)["attack"]["status"] == "unavailable"
    assert options(session)["action_surge"]["status"] == "available"
    session.execute(RuleIntent("action_surge"))
    assert options(session)["attack"]["status"] == "available"
    assert options(session)["action_surge"]["status"] == "unavailable"
    session.execute(RuleIntent("attack", "g1", "flail"))
    assert options(session)["attack"]["status"] == "unavailable"
    session.execute(RuleIntent("end_turn"))
    rows = options(session)
    for id in ("move", "attack", "second_wind", "doors", "dash", "end_turn"):
        assert rows[id]["status"] == "unavailable"
        assert rows[id]["reason"] == "Aguarde seu turno."


def test_bonus_action_and_recoverable_uses_are_distinct(session, dice):
    start(session, dice)
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=20)
    assert options(session)["second_wind"]["status"] == "available"
    session.encounter.roller = dice(1)
    session.execute(RuleIntent("second_wind"))
    rows = options(session)
    assert rows["second_wind"]["summary"] == "Bônus · 1/2 usos"
    assert rows["second_wind"]["reason"] == "Ação bônus já utilizada."
    assert "Fôlego 1/2" in rows["recovery"]["summary"]
    session.budget = ActionBudget()
    session.encounter.states["player"] = replace(session.encounter.states["player"], second_wind_uses=0)
    assert options(session)["second_wind"]["reason"] == "Sem usos restantes."


def test_movement_and_dash_use_remaining_movement_and_extra_action(session, dice):
    start(session, dice)
    session.state = replace(session.state, spent_meters=Decimal("9"))
    rows = options(session)
    assert rows["move"]["status"] == "unavailable"
    assert rows["dash"]["status"] == "available"
    session.budget = ActionBudget(action_used=True)
    assert options(session)["dash"]["status"] == "unavailable"
    session.budget = ActionBudget(action_used=True, extra_actions=1)
    assert options(session)["dash"]["status"] == "available"


def test_fiche_does_not_offer_unreachable_or_hidden_attack_targets(session):
    session.creatures = (replace(session.creatures[0], position=Position(8, 4)),)
    assert options(session)["attack"]["reason"] == "Sem alvo ao alcance."
    session.creatures = (replace(session.creatures[0], position=Position(5, 4)),)
    session.scene = Scene(session.grid, (), (), dark=frozenset({Position(5, 4)}))
    assert options(session)["attack"]["reason"] == "Sem alvo ao alcance."
    assert not session.encounter.roller.sides


def test_dead_character_options_and_read_only_queries(session):
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=0, heroic_inspiration=False)
    before = (session.state, session.budget, session.encounter.states.copy(), session.creatures)
    rows = options(session)
    for id in ("move", "attack", "second_wind", "action_surge", "doors", "dash", "end_turn"):
        assert rows[id]["status"] == "unavailable"
        assert rows[id]["reason"] == "Personagem com 0 PV."
    assert rows["inspiration"]["status"] == "unavailable"
    assert (session.state, session.budget, session.encounter.states, session.creatures) == before
    assert not session.encounter.roller.sides


def test_resource_counters_follow_rest_rules_without_claiming_a_rest_command(session):
    state = replace(session.encounter.states["player"], second_wind_uses=0, action_surge_uses=0,
                    heroic_inspiration=False, hit_dice_available=1)
    session.encounter.states["player"] = finish_short_rest(session.encounter.player_sheet, state, session.encounter.roller)
    rows = options(session)
    assert "Fôlego 1/2 · Surto 1/1" in rows["recovery"]["summary"]
    assert rows["inspiration"]["status"] == "unavailable"
    assert rows["recovery"]["status"] == "not_implemented"
    session.encounter.states["player"] = finish_long_rest(session.encounter.player_sheet, session.encounter.states["player"])
    rows = options(session)
    assert "Fôlego 2/2 · Surto 1/1" in rows["recovery"]["summary"]
    assert rows["inspiration"]["status"] == "conditional"
    assert rows["tactical_mind"]["status"] == "not_implemented"
    assert not session.encounter.roller.sides


def test_door_options_follow_reach_and_interaction_budget(dice):
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                          creatures=(Creature("g1", "Guarda", Position(15, 4)),), roller=dice())
    assert options(session)["doors"]["status"] == "conditional"
    session.execute(MovementIntent((), False, "", "guard_door"))
    assert options(session)["doors"]["status"] == "available"
    session.encounter.roller = dice(20, 19, 1)
    session.encounter.start(("g1",))
    session.budget = ActionBudget(free_interaction_used=True, action_used=True)
    assert options(session)["doors"]["reason"] == "Interação e ação já utilizadas."
    session.budget = ActionBudget(free_interaction_used=True, action_used=True, extra_actions=1)
    row = options(session)["doors"]
    assert row["status"] == "available" and row["summary"] == "Consome ação"
