from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import audit, get_assessment_for_edit, get_course_for_edit, get_course_for_view, require_staff
from ..models import (
    Assessment, AssessmentStatus, CourseOutcome, Enrollment, Role, Rubric, Score, ScoreCriterion,
    StudentProfile, User,
)
from ..schemas import AssessmentIn, AssessmentOut, AssessmentUpdate, ScoresIn, StatusIn
from ..services.rubric_engine import compute_rubric_marks
from ..utils import csv_response, parse_float, read_csv_upload

router = APIRouter(tags=["assessments"])

S = AssessmentStatus
TRANSITIONS = {
    (S.draft.value, S.in_progress.value),
    (S.in_progress.value, S.draft.value),       # only while nothing is marked
    (S.in_progress.value, S.completed.value),
    (S.completed.value, S.in_progress.value),   # reopen for corrections
    (S.completed.value, S.finalized.value),
    (S.finalized.value, S.in_progress.value),   # admin only
}


def _out(db: Session, a: Assessment) -> AssessmentOut:
    o = AssessmentOut.model_validate(a)
    o.co_ids = [co.id for co in a.cos]
    o.graded_count = db.query(func.count(Score.id)).filter(
        Score.assessment_id == a.id, (Score.marks.isnot(None)) | Score.is_absent | Score.attended.isnot(None)
    ).scalar()
    return o


def _has_scores(db: Session, a: Assessment) -> bool:
    return db.query(Score.id).filter_by(assessment_id=a.id).first() is not None


def _check_weightage(db: Session, course_id: int, weightage: float, exclude_id: int | None = None):
    q = db.query(func.coalesce(func.sum(Assessment.weightage), 0)).filter(Assessment.course_id == course_id)
    if exclude_id:
        q = q.filter(Assessment.id != exclude_id)
    total = float(q.scalar()) + weightage
    if total > 100.0001:
        raise HTTPException(422, f"Total CP weightage would be {total:g}% — it cannot exceed 100%")


def _resolve_cos(db: Session, course_id: int, co_ids: list[int]) -> list[CourseOutcome]:
    if not co_ids:
        return []
    cos = db.query(CourseOutcome).filter(CourseOutcome.id.in_(co_ids), CourseOutcome.course_id == course_id).all()
    if len(cos) != len(set(co_ids)):
        raise HTTPException(422, "Some course outcomes do not belong to this course")
    return cos


@router.get("/courses/{course_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    return [_out(db, a) for a in c.assessments]


@router.post("/courses/{course_id}/assessments", response_model=AssessmentOut, status_code=201)
def create_assessment(course_id: int, body: AssessmentIn, request: Request, user: User = Depends(require_staff),
                      db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    _check_weightage(db, c.id, body.weightage)
    if body.rubric_id and not db.get(Rubric, body.rubric_id):
        raise HTTPException(422, "Rubric not found")
    a = Assessment(course_id=c.id, **body.model_dump(exclude={"co_ids"}))
    a.cos = _resolve_cos(db, c.id, body.co_ids)
    db.add(a)
    db.flush()
    audit(db, user, "assessment_created", "assessment", a.id, a.title, request)
    db.commit()
    return _out(db, a)


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    get_course_for_view(a.course_id, db, user)
    return _out(db, a)


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
def update_assessment(assessment_id: int, body: AssessmentUpdate, request: Request,
                      user: User = Depends(require_staff), db: Session = Depends(get_db)):
    a = get_assessment_for_edit(assessment_id, db, user)
    if a.status == S.finalized.value:
        raise HTTPException(409, "Finalized assessments are locked")
    data = body.model_dump(exclude_unset=True)
    scored = _has_scores(db, a)
    for locked in ("max_marks", "rubric_id", "sessions_held"):
        if locked in data and data[locked] != getattr(a, locked) and scored:
            raise HTTPException(409, f"Cannot change {locked.replace('_', ' ')} after marks have been entered")
    if "weightage" in data:
        _check_weightage(db, a.course_id, data["weightage"], exclude_id=a.id)
    if data.get("rubric_id") and not db.get(Rubric, data["rubric_id"]):
        raise HTTPException(422, "Rubric not found")
    if "co_ids" in data:
        a.cos = _resolve_cos(db, a.course_id, data.pop("co_ids") or [])
    for k, v in data.items():
        setattr(a, k, v)
    audit(db, user, "assessment_updated", "assessment", a.id, str(sorted(data)), request)
    db.commit()
    return _out(db, a)


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: int, request: Request, user: User = Depends(require_staff),
                      db: Session = Depends(get_db)):
    a = get_assessment_for_edit(assessment_id, db, user)
    if a.status == S.finalized.value:
        raise HTTPException(409, "Finalized assessments cannot be deleted")
    audit(db, user, "assessment_deleted", "assessment", a.id, a.title, request)
    db.delete(a)
    db.commit()


@router.post("/assessments/{assessment_id}/status", response_model=AssessmentOut)
def change_status(assessment_id: int, body: StatusIn, request: Request, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    a = get_assessment_for_edit(assessment_id, db, user)
    if a.status == body.status:
        return _out(db, a)
    if (a.status, body.status) not in TRANSITIONS:
        raise HTTPException(409, f"Cannot move from {a.status.replace('_', ' ')} to {body.status.replace('_', ' ')}")
    if a.status == S.finalized.value and user.role != Role.admin.value:
        raise HTTPException(403, "Only an administrator can reopen a finalized assessment")
    if body.status == S.draft.value and _has_scores(db, a):
        raise HTTPException(409, "Marks have been entered; it can no longer go back to draft")
    audit(db, user, "assessment_status", "assessment", a.id, f"{a.status} -> {body.status}", request)
    a.status = body.status
    db.commit()
    return _out(db, a)


# ------------------------------------------------------------------ marks entry

def _enrolled(db: Session, course_id: int):
    return (db.query(User, StudentProfile)
            .join(Enrollment, Enrollment.student_id == User.id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .filter(Enrollment.course_id == course_id)
            .order_by(StudentProfile.roll_no, User.name).all())


@router.get("/assessments/{assessment_id}/scores")
def get_scores(assessment_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    get_course_for_view(a.course_id, db, user)
    scores = {s.student_id: s for s in
              db.query(Score).options(selectinload(Score.criteria)).filter_by(assessment_id=a.id).all()}
    rows = []
    for u, sp in _enrolled(db, a.course_id):
        s = scores.get(u.id)
        rows.append({
            "student_id": u.id, "name": u.name, "roll_no": sp.roll_no if sp else None,
            "marks": s.marks if s else None, "attended": s.attended if s else None,
            "is_absent": s.is_absent if s else False, "feedback": s.feedback if s else None,
            "criteria": {sc.criterion_id: sc.level_id for sc in s.criteria} if s else {},
            "updated_at": s.updated_at if s else None,
        })
    return {"assessment": _out(db, a), "editable": a.status == S.in_progress.value, "rows": rows}


def _save_scores(db: Session, a: Assessment, items, user: User):
    if a.status != S.in_progress.value:
        raise HTTPException(409, "Marks can only be entered while the assessment is in progress")
    enrolled = {sid for (sid,) in db.query(Enrollment.student_id).filter_by(course_id=a.course_id).all()}
    rubric = (db.get(Rubric, a.rubric_id, options=[selectinload(Rubric.levels), selectinload(Rubric.criteria)])
              if a.rubric_id else None)
    existing = {s.student_id: s for s in
                db.query(Score).options(selectinload(Score.criteria)).filter_by(assessment_id=a.id).all()}
    saved = 0
    for it in items:
        if it.student_id not in enrolled:
            raise HTTPException(422, f"Student {it.student_id} is not enrolled in this course")
        s = existing.get(it.student_id)
        empty = (not it.is_absent and it.marks is None and it.attended is None and not it.criteria
                 and not (it.feedback or "").strip())
        if empty:
            if s:
                db.delete(s)
            continue
        if not s:
            s = Score(assessment_id=a.id, student_id=it.student_id)
            db.add(s)
            existing[it.student_id] = s
        s.is_absent = it.is_absent
        s.feedback = (it.feedback or "").strip() or None
        s.graded_by = user.id
        if it.is_absent:
            s.marks, s.attended = None, None
            s.criteria = []
        elif a.component == "attendance":
            if it.attended is not None and it.attended > (a.sessions_held or 0):
                raise HTTPException(422, f"Attended sessions cannot exceed {a.sessions_held}")
            s.attended = it.attended
            s.marks = None if it.attended is None else round(a.max_marks * it.attended / a.sessions_held, 2)
        elif rubric:
            if it.criteria:
                s.marks = compute_rubric_marks(rubric, it.criteria, a.max_marks)
                s.criteria = [ScoreCriterion(criterion_id=cid, level_id=lid) for cid, lid in it.criteria.items()]
            else:
                s.marks, s.criteria = None, []
        else:
            if it.marks is not None and it.marks > a.max_marks:
                raise HTTPException(422, f"Marks cannot exceed {a.max_marks:g}")
            s.marks = it.marks
        saved += 1
    return saved


@router.put("/assessments/{assessment_id}/scores")
def put_scores(assessment_id: int, body: ScoresIn, request: Request, user: User = Depends(require_staff),
               db: Session = Depends(get_db)):
    a = get_assessment_for_edit(assessment_id, db, user)
    n = _save_scores(db, a, body.scores, user)
    audit(db, user, "scores_saved", "assessment", a.id, f"{n} rows", request)
    db.commit()
    return get_scores(assessment_id, user, db)


@router.get("/assessments/{assessment_id}/scores/template")
def scores_template(assessment_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    get_course_for_view(a.course_id, db, user)
    col = "attended" if a.component == "attendance" else "marks"
    data = get_scores(assessment_id, user, db)["rows"]
    rows = [["roll_no", "name", col, "feedback"]]
    for r in data:
        val = "AB" if r["is_absent"] else (r["attended"] if col == "attended" else r["marks"])
        rows.append([r["roll_no"], r["name"], val, r["feedback"]])
    return csv_response(rows, f"assessment_{a.id}_{col}.csv")


@router.post("/assessments/{assessment_id}/scores/import")
async def import_scores(assessment_id: int, request: Request, file: UploadFile = File(...),
                        user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """CSV columns: roll_no, marks (or attended for attendance), optional feedback. AB = absent."""
    a = get_assessment_for_edit(assessment_id, db, user)
    if a.rubric_id:
        raise HTTPException(422, "Rubric-scored assessments are marked criterion by criterion in the grid")
    col = "attended" if a.component == "attendance" else "marks"
    rows = await read_csv_upload(file, {"roll_no", col})
    rolls = dict(db.query(StudentProfile.roll_no, StudentProfile.user_id).all())
    from ..schemas import ScoreIn
    items = []
    for i, r in enumerate(rows, start=2):
        sid = rolls.get(r["roll_no"])
        if not sid:
            raise HTTPException(422, f"Line {i}: unknown roll number {r['roll_no']}")
        absent = r[col].upper() == "AB"
        val = None if absent else parse_float(r[col], col, i)
        if col == "attended":
            items.append(ScoreIn(student_id=sid, attended=int(val) if val is not None else None,
                                 is_absent=absent, feedback=r.get("feedback")))
        else:
            items.append(ScoreIn(student_id=sid, marks=val, is_absent=absent, feedback=r.get("feedback")))
    n = _save_scores(db, a, items, user)
    audit(db, user, "scores_imported", "assessment", a.id, f"{n} rows", request)
    db.commit()
    return {"saved": n}
