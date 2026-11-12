import pytest

from trama.actions import ActionBudget, ActionError, operate_door


def operate(operation, *, is_open=False, locked=False, in_reach=True, occupied=False,
            budget=ActionBudget()):
    return operate_door(operation, is_open=is_open, locked=locked, in_reach=in_reach,
                        occupied=occupied, budget=budget)


def test_first_interaction_is_free_second_uses_utilize_third_is_rejected():
    opened = operate("open")
    assert opened.is_open
    assert opened.budget.free_interaction_used
    assert not opened.budget.action_used
    closed = operate("close", is_open=True, budget=opened.budget)
    assert not closed.is_open
    assert closed.budget.action_used
    with pytest.raises(ActionError, match="já foi utilizada"):
        operate("open", budget=closed.budget)


def test_free_interaction_remains_available_after_dash():
    budget = ActionBudget(action_used=True)
    result = operate("open", budget=budget)
    assert result.is_open
    assert result.budget == ActionBudget(True, True)
    with pytest.raises(ActionError):
        operate("close", is_open=True, budget=result.budget)


@pytest.mark.parametrize("operation,is_open", [("open", True), ("close", False)])
def test_redundant_interaction_does_not_spend_resources(operation, is_open):
    budget = ActionBudget(True, True)
    result = operate(operation, is_open=is_open, budget=budget)
    assert not result.changed
    assert result.budget == budget


@pytest.mark.parametrize("operation,kwargs,message", [
    ("open", {"locked": True}, "trancada"),
    ("open", {"in_reach": False}, "Aproxime-se"),
    ("close", {"is_open": True, "in_reach": False}, "Aproxime-se"),
    ("close", {"is_open": True, "occupied": True}, "alguém ocupa"),
    ("unlock", {}, "desconhecida"),
])
def test_invalid_operations_do_not_spend_budget(operation, kwargs, message):
    budget = ActionBudget()
    with pytest.raises(ActionError, match=message):
        operate(operation, budget=budget, **kwargs)
    assert budget == ActionBudget()
