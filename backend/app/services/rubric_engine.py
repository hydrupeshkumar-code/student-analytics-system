"""Rubric Engine (Objective O2).

Score = max_marks * sum_c( w_c * points(level_c) / max_points ) / sum_c( w_c )
"""
from fastapi import HTTPException

from ..models import Rubric


def compute_rubric_marks(rubric: Rubric, selections: dict[int, int], max_marks: float) -> float:
    """selections: criterion_id -> level_id. Every criterion must be scored."""
    if not rubric.levels or not rubric.criteria:
        raise HTTPException(422, "Rubric has no levels or criteria")
    level_points = {lvl.id: lvl.points for lvl in rubric.levels}
    max_points = max(level_points.values())
    if max_points <= 0:
        raise HTTPException(422, "Rubric levels must have a positive maximum")
    total_weight = sum(c.weight for c in rubric.criteria)
    if total_weight <= 0:
        raise HTTPException(422, "Rubric criteria weights must be positive")

    acc = 0.0
    for criterion in rubric.criteria:
        level_id = selections.get(criterion.id)
        if level_id is None:
            raise HTTPException(422, f"Criterion '{criterion.name}' has not been scored")
        if level_id not in level_points:
            raise HTTPException(422, f"Invalid performance level for '{criterion.name}'")
        acc += criterion.weight * (level_points[level_id] / max_points)
    return round(max_marks * acc / total_weight, 2)


def validate_rubric_payload(levels: list, criteria: list):
    if len(levels) < 2:
        raise HTTPException(422, "A rubric needs at least two performance levels")
    if len(criteria) < 1:
        raise HTTPException(422, "A rubric needs at least one criterion")
    labels = [lv.label.strip().lower() for lv in levels]
    if len(set(labels)) != len(labels):
        raise HTTPException(422, "Performance level labels must be unique")
    if any(lv.points < 0 for lv in levels) or max(lv.points for lv in levels) <= 0:
        raise HTTPException(422, "Level points must be non-negative with a positive maximum")
    if any(c.weight <= 0 for c in criteria):
        raise HTTPException(422, "Criterion weightage must be greater than zero")
