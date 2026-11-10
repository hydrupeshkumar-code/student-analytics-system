"""Student Portal: per-CP breakdowns, rubric feedback, CO status and early-warning guidance."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_course_for_view, require_roles
from ..models import Course, Enrollment, Prediction, Role, Rubric, Score, User
from ..services import prediction, reports, settings_service
from ..services.attainment import student_co_scores
from ..services.correlation import build_gradebook
from ..services.student_guidance import (
    aggregate_internship_feedback, internship_feedback_for_course, student_risk_signals,
)
from ..utils import PDF, file_response

router = APIRouter(prefix="/me", tags=["student portal"])
require_student = require_roles(Role.student)


def _course_detail(db: Session, user: User, course: Course) -> dict:
    cfg = settings_service.get_all(db)
    gb = build_gradebook(db, course, student_ids=[user.id], student_view=True)
    if not gb["students"]:
        raise HTTPException(404, "Not enrolled")
    me = gb["students"][0]
    # Risk checks use currently recorded (non-draft) data, while report tables continue
    # to respect the student-visible assessment release workflow.
    live_gb = build_gradebook(db, course, student_ids=[user.id], student_view=False)
    live_components = live_gb["students"][0].get("components", {}) if live_gb["students"] else me["components"]

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

    signals = student_risk_signals(live_components, cfg)
    career_feedback = internship_feedback_for_course(course.code, course.name, live_components, signals["internals_pct"])

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
        "attendance_risk": signals["attendance"], "internal_risk": signals["internals"],
        "internals_pct": signals["internals_pct"], "internship_feedback": career_feedback,
        "result_pending": gb["result_pending"],
        "requirements": {"pass_mark_pct": cfg["pass_mark_pct"], "ncp_min_pct": cfg["ncp_min_pct"],
                         "attendance_min_pct": cfg["attendance_min_pct"]},
    }


def _academic_report_payload(db: Session, user: User) -> dict:
    """Build a private academic report for the authenticated student only."""
    cfg = settings_service.get_all(db)
    profile = user.student_profile
    course_items = []
    for course in _my_courses(db, user):
        detail = _course_detail(db, user, course)
        signals = {
            "attendance": detail["attendance_risk"],
            "internals": detail["internal_risk"],
            "internals_pct": detail["internals_pct"],
        }
        career_feedback = detail["internship_feedback"]
        overall_risk = detail.get("risk") or {}
        course_items.append({
            "id": course.id,
            "code": course.code,
            "name": course.name,
            "semester": course.semester,
            "academic_year": course.academic_year,
            "credits": course.credits,
            "faculty": detail["course"]["faculty"],
            "components": detail["components"],
            "cp_pct": detail["cp_pct"],
            "ncp_pct": detail["ncp_pct"],
            "ncp_published": detail["course"]["ncp_published"],
            "final_pct": detail["final_pct"],
            "grade": detail["grade"],
            "passed": detail["passed"],
            "attendance_pct": signals["attendance"].get("value_pct"),
            "internals_pct": signals["internals_pct"],
            "attendance_risk": signals["attendance"],
            "internal_risk": signals["internals"],
            "overall_risk": overall_risk.get("risk_level"),
            "assessments_released": len(detail["assessments"]),
            "flags": detail["flags"],
            "internship_feedback": career_feedback,
        })

    def average(key: str):
        values = [float(item[key]) for item in course_items if item.get(key) is not None]
        return round(sum(values) / len(values), 1) if values else None

    summary = {
        "courses_enrolled": len(course_items),
        "courses_completed": sum(1 for item in course_items if item["grade"] is not None),
        "average_internal_pct": average("internals_pct"),
        "average_attendance_pct": average("attendance_pct"),
        "average_final_pct": average("final_pct"),
        "attendance_at_risk": sum(1 for item in course_items if item["attendance_risk"]["risk_level"] in ("medium", "high")),
        "internals_at_risk": sum(1 for item in course_items if item["internal_risk"]["risk_level"] in ("medium", "high")),
        "overall_ml_at_risk": sum(1 for item in course_items if item["overall_risk"] in ("medium", "high")),
    }
    return {
        "student": {
            "name": user.name,
            "email": user.email,
            "roll_no": profile.roll_no if profile else None,
            "program": profile.program.name if profile and profile.program else None,
            "batch": profile.batch if profile else None,
            "semester": profile.semester if profile else None,
            "section": profile.section if profile else None,
        },
        "summary": summary,
        "courses": course_items,
        "internship_feedback": aggregate_internship_feedback(course_items),
        "attendance_min_pct": cfg["attendance_min_pct"],
        "internal_target_pct": 60.0,
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
    }


def _my_courses(db: Session, user: User) -> list[Course]:
    return (db.query(Course).join(Enrollment).filter(Enrollment.student_id == user.id)
            .order_by(Course.academic_year.desc(), Course.semester.desc(), Course.code).all())


@router.get("/courses")
def my_courses(user: User = Depends(require_student), db: Session = Depends(get_db)):
    out = []
    cfg = settings_service.get_all(db)
    for c in _my_courses(db, user):
        gb = build_gradebook(db, c, student_ids=[user.id], student_view=True)
        me = gb["students"][0] if gb["students"] else {}
        pred = db.query(Prediction).filter_by(course_id=c.id, student_id=user.id).first()
        component_values = me.get("components", {})
        live_gb = build_gradebook(db, c, student_ids=[user.id], student_view=False)
        live_components = live_gb["students"][0].get("components", {}) if live_gb["students"] else component_values
        signals = student_risk_signals(live_components, cfg)
        out.append({
            "id": c.id, "code": c.code, "name": c.name, "semester": c.semester, "academic_year": c.academic_year,
            "credits": c.credits, "faculty": c.faculty.name if c.faculty else None,
            "cp_pct": me.get("cp_pct"), "ncp_pct": me.get("ncp_pct"), "final_pct": me.get("final_pct"),
            "grade": me.get("grade"), "passed": me.get("passed"), "components": component_values,
            "assessments_released": len(gb["assessments"]), "flags": me.get("flags", []),
            "risk_level": pred.risk_level if pred else None,
            "attendance_risk": signals["attendance"], "internal_risk": signals["internals"],
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


@router.get("/academic-report")
def my_academic_report(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _academic_report_payload(db, user)


@router.get("/report.pdf")
def my_report(user: User = Depends(require_student), db: Session = Depends(get_db)):
    payload = _academic_report_payload(db, user)
    courses = []
    for c in _my_courses(db, user):
        d = _course_detail(db, user, c)
        report_course = next((item for item in payload["courses"] if item["id"] == c.id), {})
        courses.append({
            **d["course"], "assessments": d["assessments"], "cp_pct": d["cp_pct"],
            "ncp_pct": d["ncp_pct"], "final_pct": d["final_pct"], "grade": d["grade"],
            "risk": d["risk"], "attendance_pct": report_course.get("attendance_pct"),
            "internals_pct": report_course.get("internals_pct"),
            "attendance_risk": report_course.get("attendance_risk"),
            "internal_risk": report_course.get("internal_risk"),
            "components": report_course.get("components", {}),
            "internship_feedback": report_course.get("internship_feedback", []),
        })
    info = payload["student"]
    pdf = reports.student_report_pdf(info, courses, summary=payload["summary"],
                                     internship_feedback=payload["internship_feedback"])
    return file_response(pdf, PDF, f"academic_report_{info['roll_no'] or user.id}.pdf")
