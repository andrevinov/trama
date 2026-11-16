from concurrent.futures import ThreadPoolExecutor

import pytest

from trama.infrastructure.call_budget import CallBudget, CallBudgetExceeded


@pytest.mark.parametrize('limit', [-1, True, 1.5, None])
def test_budget_rejects_invalid_limits(limit):
    with pytest.raises(ValueError):
        CallBudget(limit)


def test_budget_counts_reservations_and_rejects_before_overrun():
    budget = CallBudget(1)
    budget.reserve()
    assert budget.context() == {'max_calls': 1, 'used': 1, 'remaining': 0, 'exceeded': False}
    with pytest.raises(CallBudgetExceeded):
        budget.reserve()
    assert budget.context() == {'max_calls': 1, 'used': 1, 'remaining': 0, 'exceeded': True}


def test_budget_is_shared_safely_between_workers():
    budget = CallBudget(3)
    def attempt(_):
        try:
            budget.reserve()
            return True
        except CallBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(8))) == 3
    assert budget.context()['used'] == 3
