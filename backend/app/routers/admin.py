"""Admin console (institution analytics, settings, audit, ML model management) and faculty overview."""
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import audit, get_current_user, require_admin, require_roles
from ..models import (
    Assessment, AuditLog, Course, Enrollment, HistoricalRecord, ModelVersion, Prediction, Program, Role,
    Score, StudentProfile, User,
)
from ..schemas import ModelVersionOut, SettingsIn, TrainIn
from ..services import prediction, settings_service
from ..services.correlation import build_gradebook
from ..utils import csv_response, parse_float, read_csv_upload

router = APIRouter(tags=["admin"])
require_faculty = require_roles(Role.faculty, Role.admin)


def _course_stats(db: Session, c: Course) -> dict:
    gb = build_gradebook(db, c)
    st = gb["students"]
    cps = [s["cp_pct"] for s in st if s["cp_pct"] is not None]
    finals = [s for s in st if s["passed"] is not None]
    risk = dict(db.query(Prediction.risk_level, func.count(Prediction.id))
                .filter(Prediction.course_id == c.id).group_by(Prediction.risk_level).all())
    pending = sum(1 for a in c.assessments if a.status == "in_progress")
    return {
        "id": c.id, "code": c.code, "name": c.name, "academic_year": c.academic_year, "semester": c.semester,
        "section": c.section, "faculty": c.faculty.name if c.faculty else None,
        "program": c.program.code if c.program else None, "students": len(st),
        "cp_average": round(sum(cps) / len(cps), 1) if cps else None,
        "pass_rate": round(100 * sum(1 for s in finals if s["passed"]) / len(finals), 1) if finals else None,
        "high_risk": risk.get("high", 0), "medium_risk": risk.get("medium", 0),
        "assessments": len(c.assessments), "marking_open": pending,
        "ncp_entered": sum(1 for s in st if s["ncp_pct"] is not None),
    }


@router.get("/admin/overview")
def admin_overview(academic_year: str | None = None, _: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    users = dict(db.query(User.role, func.count(User.id)).filter(User.is_active).group_by(User.role).all())
    q = db.query(Course).options(joinedload(Course.faculty), joinedload(Course.program)).filter(Course.is_archived.is_(False))
    if academic_year:
        q = q.filter(Course.academic_year == academic_year)
    courses = [_course_stats(db, c) for c in q.order_by(Course.code).all()]
    programs = []
    for p in db.query(Program).order_by(Program.code).all():
        pc = [c for c in courses if c["program"] == p.code]
        cps = [c["cp_average"] for c in pc if c["cp_average"] is not None]
        prs = [c["pass_rate"] for c in pc if c["pass_rate"] is not None]
        programs.append({"id": p.id, "code": p.code, "name": p.name, "courses": len(pc),
                         "students": db.query(func.count(StudentProfile.id)).filter_by(program_id=p.id).scalar(),
                         "cp_average": round(sum(cps) / len(cps), 1) if cps else None,
                         "pass_rate": round(sum(prs) / len(prs), 1) if prs else None,
                         "high_risk": sum(c["high_risk"] for c in pc)})
    mv, _m = prediction.active_model(db)
    years = [y for (y,) in db.query(Course.academic_year).distinct().order_by(Course.academic_year.desc()).all()]
    return {
        "users": {"admin": users.get("admin", 0), "faculty": users.get("faculty", 0),
                  "student": users.get("student", 0)},
        "courses": courses, "programs": programs, "academic_years": years,
        "totals": {"courses": len(courses), "enrollments": sum(c["students"] for c in courses),
                   "high_risk": sum(c["high_risk"] for c in courses),
                   "medium_risk": sum(c["medium_risk"] for c in courses),
                   "marking_open": sum(c["marking_open"] for c in courses)},
        "model": {"algorithm": mv.algorithm, "holdout": mv.metrics.get("holdout"), "trained_at": mv.created_at}
        if mv else None,
    }


@router.get("/faculty/overview")
def faculty_overview(user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    q = db.query(Course).options(joinedload(Course.faculty), joinedload(Course.program)).filter(Course.is_archived.is_(False))
    if user.role == Role.faculty.value:
        q = q.filter(Course.faculty_id == user.id)
    courses = q.order_by(Course.code).all()
    stats = [_course_stats(db, c) for c in courses]
    ids = [c.id for c in courses]
    at_risk = []
    if ids:
        rows = (db.query(Prediction, User, Course, StudentProfile.roll_no)
                .join(User, User.id == Prediction.student_id).join(Course, Course.id == Prediction.course_id)
                .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
                .filter(Prediction.course_id.in_(ids), Prediction.risk_level == "high")
                .order_by(Prediction.probability.desc()).limit(25).all())
        at_risk = [{"student_id": u.id, "name": u.name, "roll_no": roll, "course_id": c.id, "course": c.code,
                    "probability": p.probability, "reasons": p.reasons} for p, u, c, roll in rows]
    todo = []
    for c in courses:
        n_students = db.query(func.count(Enrollment.id)).filter_by(course_id=c.id).scalar()
        for a in c.assessments:
            if a.status == "in_progress":
                graded = db.query(func.count(Score.id)).filter(Score.assessment_id == a.id).scalar()
                todo.append({"course_id": c.id, "course": c.code, "assessment_id": a.id, "title": a.title,
                             "graded": graded, "students": n_students, "due_date": a.due_date})
    return {"courses": stats, "at_risk": at_risk, "marking": todo}


# ------------------------------------------------------------------ settings & audit

@router.get("/settings")
def get_settings(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return settings_service.get_all(db)


@router.put("/settings")
def put_settings(body: SettingsIn, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    if "grade_bands" in data:
        bands = sorted(data["grade_bands"], key=lambda b: -b["min"])
        if not bands or bands[-1]["min"] != 0:
            raise HTTPException(422, "Grade bands must include a band starting at 0")
        if len({b["grade"] for b in bands}) != len(bands):
            raise HTTPException(422, "Grade labels must be unique")
        data["grade_bands"] = bands
    merged = {**settings_service.get_all(db), **data}
    if merged["risk_medium"] >= merged["risk_high"]:
        raise HTTPException(422, "Medium risk threshold must be below the high risk threshold")
    out = settings_service.update(db, data)
    audit(db, admin, "settings_updated", None, None, str(sorted(data)), request)
    db.commit()
    return out


@router.get("/audit")
def audit_log(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), action: str | None = None,
              _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(AuditLog).options(joinedload(AuditLog.user))
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [
        {"id": r.id, "at": r.created_at, "user": r.user.email if r.user else None, "action": r.action,
         "entity": r.entity, "entity_id": r.entity_id, "detail": r.detail, "ip": r.ip} for r in rows]}


# ------------------------------------------------------------------ ML model management

@router.get("/ml/models", response_model=list[ModelVersionOut])
def list_models(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(ModelVersion).order_by(ModelVersion.id.desc()).limit(20).all()


@router.get("/ml/status")
def ml_status(_: User = Depends(require_faculty), db: Session = Depends(get_db)):
    mv, _m = prediction.active_model(db)
    counts = dict(db.query(HistoricalRecord.source, func.count(HistoricalRecord.id))
                  .group_by(HistoricalRecord.source).all())
    passed = db.query(func.count(HistoricalRecord.id)).filter(HistoricalRecord.passed).scalar()
    total = sum(counts.values())
    return {"active_model": ModelVersionOut.model_validate(mv) if mv else None,
            "history": {"total": total, "by_source": counts, "fail_rate": round(1 - passed / total, 3) if total else None},
            "features": prediction.FEATURES, "min_samples": prediction.MIN_SAMPLES}


@router.post("/ml/train", response_model=ModelVersionOut)
def train_model(body: TrainIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    mv = prediction.train(db, body.algorithm, admin.id)
    audit(db, admin, "model_trained", "model", mv.id, f"{mv.algorithm} f1={mv.metrics['holdout']['f1']}", request)
    db.commit()
    return mv


@router.post("/ml/models/{model_id}/activate", response_model=ModelVersionOut)
def activate_model(model_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    mv = db.get(ModelVersion, model_id)
    if not mv:
        raise HTTPException(404, "Model not found")
    db.query(ModelVersion).update({ModelVersion.is_active: False})
    mv.is_active = True
    audit(db, admin, "model_activated", "model", mv.id, request=request)
    db.commit()
    return mv


@router.post("/ml/recompute-all")
def recompute_all(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = 0
    for c in db.query(Course).filter(Course.is_archived.is_(False)).all():
        n += len(prediction.predict_course(db, c))
    audit(db, admin, "risk_recomputed_all", None, None, f"{n} predictions", request)
    db.commit()
    return {"predictions": n}


HIST_COLS = ["cohort", "course_code", "quiz_pct", "assignment_pct", "practical_pct", "attendance_pct",
             "cp_pct", "ncp_pct", "passed"]


@router.post("/ml/history/import")
async def import_history(request: Request, file: UploadFile = File(...), admin: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    rows = await read_csv_upload(file, {"cp_pct", "passed"})
    recs = []
    for i, r in enumerate(rows, start=2):
        passed = r["passed"].strip().lower()
        if passed not in ("1", "0", "true", "false", "yes", "no", "pass", "fail"):
            raise HTTPException(422, f"Line {i}: passed must be 1/0, true/false, yes/no or pass/fail")
        vals = {k: parse_float(r.get(k, ""), k, i) for k in
                ("quiz_pct", "assignment_pct", "practical_pct", "attendance_pct", "cp_pct", "ncp_pct")}
        if vals["cp_pct"] is None:
            raise HTTPException(422, f"Line {i}: cp_pct is required")
        if any(v is not None and not 0 <= v <= 100 for v in vals.values()):
            raise HTTPException(422, f"Line {i}: percentages must be between 0 and 100")
        recs.append(HistoricalRecord(source="import", cohort=r.get("cohort") or None,
                                     course_code=r.get("course_code") or None,
                                     passed=passed in ("1", "true", "yes", "pass"), **vals))
    db.add_all(recs)
    audit(db, admin, "history_imported", None, None, f"{len(recs)} records", request)
    db.commit()
    return {"imported": len(recs)}


@router.get("/ml/history/template")
def history_template(_: User = Depends(require_admin)):
    return csv_response([HIST_COLS, ["2023-24", "CS201", 62, 71, 68, 84, 67.5, 58, 1],
                         ["2023-24", "CS201", 31, 40, 45, 61, 38.2, 29, 0]], "history_template.csv")


@router.delete("/ml/history")
def clear_history(source: str = Query(..., pattern="^(import|harvest|synthetic)$"), request: Request = None,
                  admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = db.query(HistoricalRecord).filter_by(source=source).delete()
    audit(db, admin, "history_cleared", None, None, f"{source}: {n}", request)
    db.commit()
    return {"deleted": n}
