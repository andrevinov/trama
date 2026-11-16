"""Avaliação objetiva de intenções, independente do modelo e sem executar o jogo."""

from trama.application.intents import ActionPlan, MovementIntent, RuleIntent
from trama.distances import CELL_METERS


def summarize_plan(plan: ActionPlan) -> list[dict]:
    result = []
    for step in plan.steps:
        if isinstance(step, MovementIntent):
            result.append({"operation": "clarify" if step.clarification else "move", "target_id": step.target_id,
                           "dash": step.dash, "segments": [{"direction": s.direction,
                           "meters": float(s.squares * CELL_METERS + s.remainder_meters)} for s in step.segments]})
        else:
            value = {"operation": step.operation, "target_id": step.target_id}
            if isinstance(step, RuleIntent):
                value.update(weapon=step.weapon, use_inspiration=step.use_inspiration)
            result.append(value)
    return result


def evaluate_plan(expected: list[dict], plan: ActionPlan) -> dict:
    """O oráculo vem dos casos, não da checagem de autorização nem de outra IA."""
    actual = summarize_plan(plan)
    matched = len(expected) == len(actual) and all(
        all(actual_step.get(key) == value for key, value in expected_step.items())
        for expected_step, actual_step in zip(expected, actual)
    )
    return {"matches_expected": matched, "actual": actual}
