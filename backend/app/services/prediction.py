"""Predictive early-warning module (Objective O5).

Baseline models (logistic regression / decision tree) trained on anonymised historical CP–NCP
records. Features are CP-only so predictions are available *before* the semester-end exam.
Target: student failed the course (final below pass mark or NCP below minimum).
"""
import io
import random

import joblib
import numpy as np
from fastapi import HTTPException
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sqlalchemy.orm import Session

from ..models import Course, HistoricalRecord, ModelVersion, Prediction, utcnow
from . import settings_service
from .correlation import build_gradebook

FEATURES = ["quiz_pct", "assignment_pct", "practical_pct", "attendance_pct", "cp_pct"]
FEATURE_LABELS = {
    "quiz_pct": "Quiz average", "assignment_pct": "Assignment average",
    "practical_pct": "Practical average", "attendance_pct": "Attendance", "cp_pct": "Overall CP score",
}
MIN_SAMPLES = 40


def feature_vector(values: dict) -> list[float] | None:
    """Missing component scores are imputed with the overall CP score (no evidence of a gap)."""
    cp = values.get("cp_pct")
    if cp is None:
        return None
    return [float(values.get(f)) if values.get(f) is not None else float(cp) for f in FEATURES]


def _candidates():
    # no class re-weighting: we need calibrated probabilities because the risk levels are thresholds on them
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000)),
        "decision_tree": DecisionTreeClassifier(
            max_depth=4, min_samples_leaf=20, random_state=42),
    }


def train(db: Session, algorithm: str = "auto", user_id: int | None = None) -> ModelVersion:
    rows = db.query(HistoricalRecord).all()
    X, y = [], []
    for r in rows:
        v = feature_vector({f: getattr(r, f) for f in FEATURES})
        if v is not None:
            X.append(v)
            y.append(0 if r.passed else 1)
    if len(X) < MIN_SAMPLES:
        raise HTTPException(422, f"At least {MIN_SAMPLES} historical records are needed to train (have {len(X)})")
    X_arr, y_arr = np.array(X), np.array(y)
    n_pos = int(y_arr.sum())
    if n_pos < 5 or len(y_arr) - n_pos < 5:
        raise HTTPException(422, "Training data needs at least 5 passing and 5 failing records")

    cands = _candidates()
    if algorithm != "auto":
        if algorithm not in cands:
            raise HTTPException(422, "algorithm must be auto, logistic_regression or decision_tree")
        cands = {algorithm: cands[algorithm]}

    # Students are flagged from the "medium" threshold upwards, so evaluate at that operating point
    threshold = float(settings_service.get_all(db)["risk_medium"])
    folds = min(5, n_pos, len(y_arr) - n_pos)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    results = {}
    for name, est in cands.items():
        prob = cross_val_predict(est, X_arr, y_arr, cv=cv, method="predict_proba")[:, 1]
        results[name] = _metrics(y_arr, prob, threshold)
        results[name].pop("confusion_matrix")
    best = max(results, key=lambda k: (results[k]["f1"], results[k]["roc_auc"]))

    # hold-out evaluation for an interpretable confusion matrix
    X_tr, X_te, y_tr, y_te = train_test_split(X_arr, y_arr, test_size=0.25, stratify=y_arr, random_state=42)
    holdout_est = _candidates()[best].fit(X_tr, y_tr)
    holdout = _metrics(y_te, holdout_est.predict_proba(X_te)[:, 1], threshold)
    holdout["test_size"] = int(len(y_te))

    final = _candidates()[best].fit(X_arr, y_arr)
    explain = _explanation(best, final)

    buf = io.BytesIO()
    joblib.dump(final, buf)

    db.query(ModelVersion).update({ModelVersion.is_active: False})
    mv = ModelVersion(
        algorithm=best, n_samples=len(X), feature_names=FEATURES, model_blob=buf.getvalue(), is_active=True,
        trained_by=user_id,
        metrics={"cv": results, "cv_folds": folds, "threshold": threshold, "holdout": holdout, "selected": best,
                 "positive_rate": round(n_pos / len(y_arr), 4), "explain": explain},
    )
    db.add(mv)
    db.flush()
    _cache.clear()
    return mv


def _metrics(y, prob, threshold: float) -> dict:
    pred = (prob >= threshold).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y, prob)), 4),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
    }


def _explanation(name: str, est) -> dict:
    if name == "logistic_regression":
        coefs = est.named_steps["logisticregression"].coef_[0]
        return {"type": "coefficients",
                "values": {f: round(float(c), 4) for f, c in zip(FEATURES, coefs)}}
    return {"type": "importance",
            "values": {f: round(float(v), 4) for f, v in zip(FEATURES, est.feature_importances_)}}


_cache: dict[int, object] = {}


def active_model(db: Session):
    mv = db.query(ModelVersion).filter_by(is_active=True).order_by(ModelVersion.id.desc()).first()
    if not mv:
        return None, None
    if mv.id not in _cache:
        try:
            if mv.model_blob:
                _cache[mv.id] = joblib.load(io.BytesIO(mv.model_blob))
            elif mv.file_path:  # models trained before blobs were stored in the database
                _cache[mv.id] = joblib.load(mv.file_path)
            else:
                return None, None
        except (FileNotFoundError, OSError, EOFError, ValueError):
            return None, None
    return mv, _cache[mv.id]


def _risk_level(p: float, cfg: dict) -> str:
    if p >= cfg["risk_high"]:
        return "high"
    if p >= cfg["risk_medium"]:
        return "medium"
    return "low"


def _rule_probability(feat: dict, cfg: dict) -> float:
    """Transparent fallback when no trained model is available."""
    cp = feat.get("cp_pct") or 0.0
    p = 1.0 / (1.0 + np.exp((cp - cfg["pass_mark_pct"] - 5) / 6.0))
    att = feat.get("attendance_pct")
    if att is not None and att < cfg["attendance_min_pct"]:
        p = min(1.0, p + 0.25 * (cfg["attendance_min_pct"] - att) / cfg["attendance_min_pct"] + 0.1)
    return float(p)


def _reasons(feat: dict, cfg: dict) -> list[str]:
    out = []
    att = feat.get("attendance_pct")
    if att is not None and att < cfg["attendance_min_pct"]:
        out.append(f"Attendance is {att:.0f}% (requirement {cfg['attendance_min_pct']:.0f}%)")
    for f in ("quiz_pct", "assignment_pct", "practical_pct"):
        v = feat.get(f)
        if v is not None and v < cfg["component_alert_pct"] + 10:
            out.append(f"{FEATURE_LABELS[f]} is low at {v:.0f}%")
    cp = feat.get("cp_pct")
    if cp is not None and cp < cfg["pass_mark_pct"] + 10:
        out.append(f"Overall CP score is {cp:.0f}%, close to or below the pass mark")
    return out


SUGGESTIONS = {
    "attendance_pct": "Attend all remaining classes; meet the faculty mentor about the attendance shortfall.",
    "quiz_pct": "Revise weekly topics and attempt practice quizzes before the next quiz.",
    "assignment_pct": "Submit assignments on time and use the rubric feedback to improve the weakest criteria.",
    "practical_pct": "Book extra lab time and review practical procedures with the lab instructor.",
    "cp_pct": "Prepare a study plan for the semester-end exam and attend remedial sessions.",
}


def suggestions_for(feat: dict, cfg: dict) -> list[str]:
    out = []
    att = feat.get("attendance_pct")
    if att is not None and att < cfg["attendance_min_pct"]:
        out.append(SUGGESTIONS["attendance_pct"])
    for f in ("quiz_pct", "assignment_pct", "practical_pct"):
        v = feat.get(f)
        if v is not None and v < cfg["component_alert_pct"] + 10:
            out.append(SUGGESTIONS[f])
    cp = feat.get("cp_pct")
    if cp is not None and cp < cfg["pass_mark_pct"] + 15:
        out.append(SUGGESTIONS["cp_pct"])
    return out


def predict_course(db: Session, course: Course) -> list[Prediction]:
    cfg = settings_service.get_all(db)
    gb = build_gradebook(db, course)
    mv, model = active_model(db)
    existing = {p.student_id: p for p in db.query(Prediction).filter_by(course_id=course.id).all()}
    out = []
    seen = set()
    for s in gb["students"]:
        feat = dict(s["components"])
        feat = {"quiz_pct": feat.get("quiz"), "assignment_pct": feat.get("assignment"),
                "practical_pct": feat.get("practical"), "attendance_pct": feat.get("attendance"),
                "cp_pct": s["cp_pct"]}
        vec = feature_vector(feat)
        if vec is None:
            continue  # nothing graded yet
        if model is not None:
            prob = float(model.predict_proba(np.array([vec]))[0, 1])
            method, mv_id = "ml", mv.id
        else:
            prob = _rule_probability(feat, cfg)
            method, mv_id = "rules", None
        pred = existing.get(s["student_id"]) or Prediction(course_id=course.id, student_id=s["student_id"])
        pred.probability = round(prob, 4)
        pred.risk_level = _risk_level(prob, cfg)
        pred.method = method
        pred.model_version_id = mv_id
        pred.features = feat
        pred.reasons = _reasons(feat, cfg)
        pred.generated_at = utcnow()
        if pred.id is None:
            db.add(pred)
        seen.add(s["student_id"])
        out.append(pred)
    for sid, p in existing.items():
        if sid not in seen:
            db.delete(p)
    db.flush()
    return out


def synthetic_history(n: int = 1200, seed: int = 7) -> list[HistoricalRecord]:
    """Clearly-labelled synthetic records so the platform works before real history is imported."""
    rng = random.Random(seed)
    clip = lambda v: max(0.0, min(100.0, v))
    rows = []
    for i in range(n):
        ability = rng.gauss(0, 1)
        engagement = rng.gauss(0, 1)
        att = clip(82 + 9 * engagement + 3 * ability + rng.gauss(0, 5))
        quiz = clip(62 + 15 * ability + 4 * engagement + rng.gauss(0, 9))
        assign = clip(70 + 10 * ability + 8 * engagement + rng.gauss(0, 9))
        prac = clip(68 + 11 * ability + 5 * engagement + rng.gauss(0, 8))
        cp = 0.3 * quiz + 0.3 * assign + 0.3 * prac + 0.1 * att
        ncp = clip(52 + 15 * ability + 5 * engagement + 0.3 * (att - 80) + rng.gauss(0, 10))
        final = 0.5 * cp + 0.5 * ncp
        rows.append(HistoricalRecord(
            source="synthetic", cohort=f"SYN-{2020 + i % 5}", course_code=None,
            quiz_pct=round(quiz, 1), assignment_pct=round(assign, 1), practical_pct=round(prac, 1),
            attendance_pct=round(att, 1), cp_pct=round(cp, 1), ncp_pct=round(ncp, 1),
            passed=bool(final >= 40 and ncp >= 35),
        ))
    return rows


def harvest_course(db: Session, course: Course) -> int:
    """Copy anonymised CP–NCP outcomes of a completed course into the training set."""
    gb = build_gradebook(db, course)
    # idempotent: re-harvesting a course replaces its earlier records
    cohort = f"{course.academic_year}/{course.section}"
    db.query(HistoricalRecord).filter_by(source="harvest", cohort=cohort, course_code=course.code).delete()
    n = 0
    for s in gb["students"]:
        if s["cp_pct"] is None or s["passed"] is None:
            continue
        c = s["components"]
        db.add(HistoricalRecord(
            source="harvest", cohort=cohort, course_code=course.code,
            quiz_pct=c.get("quiz"), assignment_pct=c.get("assignment"), practical_pct=c.get("practical"),
            attendance_pct=c.get("attendance"), cp_pct=s["cp_pct"], ncp_pct=s["ncp_pct"], passed=s["passed"],
        ))
        n += 1
    db.flush()
    return n
