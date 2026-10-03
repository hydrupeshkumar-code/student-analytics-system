"""CP–NCP Correlation Service.

Aggregates CP components (quizzes, assignments, practicals, attendance) with the NCP
(semester-end) result into one consolidated performance record per student.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from ..models import (
    Assessment, AssessmentStatus, Component, Course, Enrollment, NcpResult, Score, StudentProfile, User,
)
from . import settings_service

COUNTED = {AssessmentStatus.in_progress.value, AssessmentStatus.completed.value, AssessmentStatus.finalized.value}
CLOSED = {AssessmentStatus.completed.value, AssessmentStatus.finalized.value}
COMPONENTS = [c.value for c in Component]


@dataclass
class StudentRecord:
    student_id: int
    name: str
    email: str
    roll_no: str | None
    assessments: dict = field(default_factory=dict)  # assessment_id -> {marks, pct, absent, attended, feedback}
    components: dict = field(default_factory=dict)   # component -> pct | None
    cp_pct: float | None = None
    cp_weight_covered: float = 0.0
    ncp_marks: float | None = None
    ncp_pct: float | None = None
    ncp_absent: bool = False
    final_pct: float | None = None
    grade: str | None = None
    grade_points: float | None = None
    passed: bool | None = None
    flags: list = field(default_factory=list)

    def as_dict(self):
        return self.__dict__.copy()


def _r(x: float | None, nd: int = 2):
    return None if x is None else round(x, nd)


def assessment_pct(a: Assessment, s: Score | None) -> tuple[float | None, float | None]:
    """Returns (marks, pct) for one score, or (None, None) when there is nothing to count."""
    if s is None:
        if a.status in CLOSED:
            return 0.0, 0.0  # not submitted after marking closed
        return None, None
    if s.is_absent:
        return 0.0, 0.0
    if a.component == Component.attendance.value and a.sessions_held:
        if s.attended is None:
            return None, None
        pct = min(100.0, 100.0 * s.attended / a.sessions_held)
        return a.max_marks * pct / 100.0, pct
    if s.marks is None:
        return None, None
    return s.marks, (100.0 * s.marks / a.max_marks) if a.max_marks else 0.0


def build_gradebook(db: Session, course: Course, student_ids: list[int] | None = None,
                    student_view: bool = False) -> dict:
    cfg = settings_service.get_all(db)
    visible = CLOSED if student_view else COUNTED

    q = (db.query(User, StudentProfile.roll_no)
         .join(Enrollment, Enrollment.student_id == User.id)
         .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
         .filter(Enrollment.course_id == course.id))
    if student_ids is not None:
        q = q.filter(User.id.in_(student_ids))
    students = q.order_by(StudentProfile.roll_no, User.name).all()

    assessments = [a for a in (db.query(Assessment).options(joinedload(Assessment.cos))
                               .filter(Assessment.course_id == course.id).order_by(Assessment.id).all())
                   if a.status in visible]
    # students only get a final result once every CP assessment has been closed
    marking_open = student_view and any(
        a.status not in CLOSED for a in db.query(Assessment.status).filter(Assessment.course_id == course.id,
                                                                           Assessment.status != "draft"))
    a_ids = [a.id for a in assessments]
    ids = [u.id for u, _ in students]

    scores: dict[tuple[int, int], Score] = {}
    if a_ids and ids:
        for s in db.query(Score).filter(Score.assessment_id.in_(a_ids), Score.student_id.in_(ids)).all():
            scores[(s.assessment_id, s.student_id)] = s

    ncp: dict[int, NcpResult] = {}
    show_ncp = (not student_view) or course.ncp_published
    if show_ncp and ids:
        for r in db.query(NcpResult).filter(NcpResult.course_id == course.id, NcpResult.student_id.in_(ids)).all():
            ncp[r.student_id] = r

    records: list[StudentRecord] = []
    for user, roll in students:
        rec = StudentRecord(student_id=user.id, name=user.name, email=user.email, roll_no=roll)
        comp_marks: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        w_sum = 0.0
        w_acc = 0.0
        for a in assessments:
            s = scores.get((a.id, user.id))
            marks, pct = assessment_pct(a, s)
            rec.assessments[a.id] = {
                "marks": _r(marks), "pct": _r(pct, 1),
                "absent": bool(s and s.is_absent),
                "attended": s.attended if s else None,
                "feedback": s.feedback if s else None,
            }
            if pct is None:
                continue
            w_sum += a.weightage
            w_acc += a.weightage * pct
            if a.component == Component.attendance.value and a.sessions_held:
                comp_marks[a.component][0] += (s.attended or 0) if s and not s.is_absent else 0
                comp_marks[a.component][1] += a.sessions_held
            else:
                comp_marks[a.component][0] += marks
                comp_marks[a.component][1] += a.max_marks

        rec.components = {c: (_r(100.0 * comp_marks[c][0] / comp_marks[c][1], 1)
                              if c in comp_marks and comp_marks[c][1] else None) for c in COMPONENTS}
        rec.cp_pct = _r(w_acc / w_sum, 2) if w_sum else None
        rec.cp_weight_covered = round(w_sum, 2)

        r = ncp.get(user.id)
        if r is not None and (r.marks is not None or r.is_absent):
            rec.ncp_absent = r.is_absent
            rec.ncp_marks = 0.0 if r.is_absent else r.marks
            rec.ncp_pct = _r(100.0 * rec.ncp_marks / course.ncp_max_marks, 2) if course.ncp_max_marks else None

        if rec.ncp_pct is not None and not marking_open:
            cp = rec.cp_pct or 0.0
            rec.final_pct = _r((cp * course.cp_weight + rec.ncp_pct * course.ncp_weight) / 100.0, 2)
            rec.passed = rec.final_pct >= cfg["pass_mark_pct"] and rec.ncp_pct >= cfg["ncp_min_pct"]
            rec.grade, rec.grade_points = settings_service.grade_for(rec.final_pct, cfg["grade_bands"])
            if not rec.passed:
                rec.grade, rec.grade_points = "F", 0

        att = rec.components.get(Component.attendance.value)
        if att is not None and att < cfg["attendance_min_pct"]:
            rec.flags.append(f"Attendance {att:.0f}% is below the {cfg['attendance_min_pct']:.0f}% requirement")
        for c in (Component.quiz.value, Component.assignment.value, Component.practical.value):
            v = rec.components.get(c)
            if v is not None and v < cfg["component_alert_pct"]:
                rec.flags.append(f"{c.capitalize()} average {v:.0f}% is below {cfg['component_alert_pct']:.0f}%")
        if rec.ncp_absent:
            rec.flags.append("Absent for the semester-end examination")
        records.append(rec)

    return {
        "course_id": course.id,
        "assessments": [
            {"id": a.id, "title": a.title, "component": a.component, "max_marks": a.max_marks,
             "weightage": a.weightage, "status": a.status, "rubric_id": a.rubric_id,
             "sessions_held": a.sessions_held, "co_ids": [co.id for co in a.cos],
             "due_date": a.due_date.isoformat() if a.due_date else None}
            for a in assessments
        ],
        "students": [r.as_dict() for r in records],
        "cp_weight": course.cp_weight,
        "ncp_weight": course.ncp_weight,
        "ncp_max_marks": course.ncp_max_marks,
        "ncp_published": course.ncp_published,
        "result_pending": marking_open,
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(sxy / math.sqrt(sxx * syy), 3)


def linear_fit(xs: list[float], ys: list[float]) -> dict | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return {"slope": round(slope, 4), "intercept": round(my - slope * mx, 4)}
