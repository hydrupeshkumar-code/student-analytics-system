from copy import deepcopy

from sqlalchemy.orm import Session

from ..models import AppSetting

DEFAULTS: dict = {
    # 10-point scale; a student gets the first band whose `min` they reach
    "grade_bands": [
        {"grade": "O", "min": 90, "points": 10},
        {"grade": "A+", "min": 80, "points": 9},
        {"grade": "A", "min": 70, "points": 8},
        {"grade": "B+", "min": 60, "points": 7},
        {"grade": "B", "min": 50, "points": 6},
        {"grade": "C", "min": 45, "points": 5},
        {"grade": "P", "min": 40, "points": 4},
        {"grade": "F", "min": 0, "points": 0},
    ],
    "pass_mark_pct": 40.0,        # minimum final (CP+NCP) percentage
    "ncp_min_pct": 35.0,          # minimum semester-end exam percentage
    "attendance_min_pct": 75.0,   # attendance requirement
    "component_alert_pct": 40.0,  # CP component below this is flagged
    "risk_high": 0.6,             # predicted failure probability thresholds
    "risk_medium": 0.35,
}


def get_all(db: Session) -> dict:
    values = deepcopy(DEFAULTS)
    for row in db.query(AppSetting).all():
        if row.key in values:
            values[row.key] = row.value
    return values


def update(db: Session, changes: dict) -> dict:
    for key, value in changes.items():
        if key not in DEFAULTS:
            continue
        row = db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.flush()
    return get_all(db)


def grade_for(pct: float | None, bands: list[dict]) -> tuple[str | None, float | None]:
    if pct is None:
        return None, None
    for band in sorted(bands, key=lambda b: b["min"], reverse=True):
        if pct >= band["min"]:
            return band["grade"], band["points"]
    return bands[-1]["grade"], bands[-1]["points"]
