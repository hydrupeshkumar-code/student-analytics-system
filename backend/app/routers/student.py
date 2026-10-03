"""Student Portal: per-CP breakdowns, rubric feedback, CO status and early-warning guidance."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_course_for_view, require_roles
from ..models import Course, Enrollment, Prediction, Role, Rubric, Score, User
from ..services import prediction, reports, settings_service
from ..services.attainment import student_co_scores
from ..services.correlation import build_gradebook
from ..utils import PDF, file_response

router = APIRouter(prefix="/me", tags=["student portal"])
require_student = require_roles(Role.student)


def _course_detail(db: Session, user: User, course: Course) -> dict:
    cfg = settings_service.get_all(db)
    gb = build_gradebook(db, course, student_ids=[user.id], student_view=True)
    if not gb["students"]:
        raise HTTPException(404, "Not enrolled")
    me = gb["students"][0]

    rubric_ids = {a["rubric_id"] for a in gb["assessments"] if a["rubric_id"]}
    rubrics = {r.id: r for r in db.query(Rubric).options(selectinload(Rubric.levels), selectinload(Rubric.criteria))
               .filter(Rubric.id.in_(rubric_ids)).all()} if rubric_ids else {}
    a_ids = [a["id"] for a in gb["assessments"]]
    my_scores = {s.assessment_id: s for s in db.query(Score).options(selectinload(Score.criteria))
                 .filter(Score.assessment_id.in_(a_ids), Score.student_id == user.id).all()} if a_ids else {}

    # class averages per assessment for context (aggregate only, never other students' marks)
    class_gb = build_gradebook(db, course, student_view=True)
    class_avg = {}
    for a in gb["assessments"]:
        vals = [s["assessments"][a["id"]]["pct"] for s in class_gb["students"]
                if s["assessments"][a["id"]]["pct"] is not None]
        class_avg[a["id"]] = round(sum(vals) / len(vals), 1) if vals else None
    cp_vals = [s["cp_pct"] for s in class_gb["students"] if s["cp_pct"] is not None]

    assessments = []
    for a in gb["assessments"]:
        cell = me["assessments"][a["id"]]
        item = {**a, **cell, "class_average": class_avg[a["id"]], "rubric": None}
        r = rubrics.get(a["rubric_id"])
        if r:
            sel = {sc.criterion_id: sc.level_id for sc in (my_scores[a["id"]].criteria if a["id"] in my_scores else [])}
            item["rubric"] = {
                "title": r.title,
                "levels": [{"id": l.id, "label": l.label, "points": l.points} for l in r.levels],
                "criteria": [{"id": c.id, "name": c.name, "description": c.description, "weight": c.weight,
                              "descriptors": c.descriptors, "selected_level_id": sel.get(c.id)} for c in r.criteria],
            }
        assessments.append(item)

    co_pct = student_co_scores(gb, course).get(user.id, {})
    cos = [{"code": co.code, "description": co.description, "pct": co_pct.get(co.id),
            "target": course.co_target_pct,
            "attained": None if co_pct.get(co.id) is None else co_pct[co.id] >= course.co_target_pct}
           for co in course.outcomes]

    pred = db.query(Prediction).filter_by(course_id=course.id, student_id=user.id).first()
    risk = None
    if pred:
        risk = {"risk_level": pred.risk_level, "reasons": pred.reasons,
                "suggestions": prediction.suggestions_for(pred.features, cfg), "generated_at": pred.generated_at}

    return {
        "course": {"id": course.id, "code": course.code, "name": course.name, "semester": course.semester,
                   "academic_year": course.academic_year, "credits": course.credits,
                   "faculty": course.faculty.name if course.faculty else None,
                   "cp_weight": course.cp_weight, "ncp_weight": course.ncp_weight,
                   "ncp_max_marks": course.ncp_max_marks, "ncp_published": course.ncp_published},
        "assessments": assessments,
        "components": me["components"],
        "cp_pct": me["cp_pct"], "cp_weight_covered": me["cp_weight_covered"],
        "class_cp_average": round(sum(cp_vals) / len(cp_vals), 1) if cp_vals else None,
        "ncp_marks": me["ncp_marks"], "ncp_pct": me["ncp_pct"], "ncp_absent": me["ncp_absent"],
        "final_pct": me["final_pct"], "grade": me["grade"], "grade_points": me["grade_points"],
        "passed": me["passed"], "flags": me["flags"], "cos": cos, "risk": risk,
        "result_pending": gb["result_pending"],
        "requirements": {"pass_mark_pct": cfg["pass_mark_pct"], "ncp_min_pct": cfg["ncp_min_pct"],
                         "attendance_min_pct": cfg["attendance_min_pct"]},
    }


def _my_courses(db: Session, user: User) -> list[Course]:
    return (db.query(Course).join(Enrollment).filter(Enrollment.student_id == user.id)
            .order_by(Course.academic_year.desc(), Course.semester.desc(), Course.code).all())


@router.get("/courses")
def my_courses(user: User = Depends(require_student), db: Session = Depends(get_db)):
    out = []
    for c in _my_courses(db, user):
        gb = build_gradebook(db, c, student_ids=[user.id], student_view=True)
        me = gb["students"][0] if gb["students"] else {}
        pred = db.query(Prediction).filter_by(course_id=c.id, student_id=user.id).first()
        out.append({
            "id": c.id, "code": c.code, "name": c.name, "semester": c.semester, "academic_year": c.academic_year,
            "credits": c.credits, "faculty": c.faculty.name if c.faculty else None,
            "cp_pct": me.get("cp_pct"), "ncp_pct": me.get("ncp_pct"), "final_pct": me.get("final_pct"),
            "grade": me.get("grade"), "passed": me.get("passed"), "components": me.get("components", {}),
            "assessments_released": len(gb["assessments"]), "flags": me.get("flags", []),
            "risk_level": pred.risk_level if pred else None,
        })
    graded = [c for c in out if c["grade"] is not None]
    sgpa = None
    if graded:
        cfg = settings_service.get_all(db)
        pts = {b["grade"]: b["points"] for b in cfg["grade_bands"]}
        credits = sum(c["credits"] for c in graded)
        sgpa = round(sum(pts.get(c["grade"], 0) * c["credits"] for c in graded) / credits, 2) if credits else None
    return {"courses": out, "gpa_estimate": sgpa}


@router.get("/courses/{course_id}")
def my_course(course_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _course_detail(db, user, get_course_for_view(course_id, db, user))


@router.get("/report.pdf")
def my_report(user: User = Depends(require_student), db: Session = Depends(get_db)):
    courses = []
    for c in _my_courses(db, user):
        d = _course_detail(db, user, c)
        courses.append({**d["course"], "assessments": d["assessments"], "cp_pct": d["cp_pct"],
                        "ncp_pct": d["ncp_pct"], "final_pct": d["final_pct"], "grade": d["grade"],
                        "risk": d["risk"]})
    sp = user.student_profile
    info = {"name": user.name, "roll_no": sp.roll_no if sp else None,
            "program": sp.program.name if sp and sp.program else None}
    return file_response(reports.student_report_pdf(info, courses), PDF, f"report_{info['roll_no'] or user.id}.pdf")
