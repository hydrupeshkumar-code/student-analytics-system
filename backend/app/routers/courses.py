from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import (
    audit, get_course_for_edit, get_course_for_view, get_current_user, require_admin, require_staff,
)
from ..models import (
    CoPoMapping, Course, CourseOutcome, Enrollment, NcpResult, Prediction, Program, ProgramOutcome, Role,
    StudentProfile, User,
)
from ..schemas import CoPoCell, CourseIn, CourseOut, CourseUpdate, EnrollIn, NcpBulkIn, OutcomeIn, OutcomeOut
from ..services import attainment, prediction, reports, settings_service
from ..services.correlation import build_gradebook, linear_fit, pearson
from ..utils import PDF, XLSX, csv_response, file_response, parse_float, read_csv_upload

router = APIRouter(prefix="/courses", tags=["courses"])

FACULTY_EDITABLE = {"cp_weight", "ncp_weight", "ncp_max_marks", "co_target_pct", "level1_pct",
                    "level2_pct", "level3_pct", "target_level", "ncp_published"}


def course_out(db: Session, c: Course) -> CourseOut:
    out = CourseOut.model_validate(c)
    out.faculty_name = c.faculty.name if c.faculty else None
    out.program_name = c.program.name if c.program else None
    out.student_count = db.query(func.count(Enrollment.id)).filter_by(course_id=c.id).scalar()
    return out


def _validate_config(c: Course):
    if abs(c.cp_weight + c.ncp_weight - 100) > 0.01:
        raise HTTPException(422, "CP and NCP weights must add up to 100")
    if not (c.level1_pct <= c.level2_pct <= c.level3_pct):
        raise HTTPException(422, "Attainment thresholds must satisfy level 1 ≤ level 2 ≤ level 3")


@router.get("", response_model=list[CourseOut])
def list_courses(include_archived: bool = False, academic_year: str | None = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Course).options(joinedload(Course.faculty), joinedload(Course.program))
    if user.role == Role.faculty.value:
        q = q.filter(Course.faculty_id == user.id)
    elif user.role == Role.student.value:
        q = q.join(Enrollment).filter(Enrollment.student_id == user.id)
    if not include_archived:
        q = q.filter(Course.is_archived.is_(False))
    if academic_year:
        q = q.filter(Course.academic_year == academic_year)
    return [course_out(db, c) for c in q.order_by(Course.academic_year.desc(), Course.code).all()]


@router.post("", response_model=CourseOut, status_code=201)
def create_course(body: CourseIn, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    c = Course(**data)
    if c.faculty_id:
        f = db.get(User, c.faculty_id)
        if not f or f.role != Role.faculty.value:
            raise HTTPException(422, "faculty_id must reference a faculty user")
    if c.program_id and not db.get(Program, c.program_id):
        raise HTTPException(422, "Program not found")
    for field, default in (("cp_weight", 50), ("ncp_weight", 50), ("level1_pct", 50), ("level2_pct", 60),
                           ("level3_pct", 70)):
        if getattr(c, field) is None:
            setattr(c, field, default)
    _validate_config(c)
    db.add(c)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A course with this code, year and section already exists")
    audit(db, admin, "course_created", "course", c.id, f"{c.code} {c.academic_year}", request)
    db.commit()
    return course_out(db, c)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return course_out(db, get_course_for_view(course_id, db, user))


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, body: CourseUpdate, request: Request, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    data = body.model_dump(exclude_unset=True)
    if user.role == Role.faculty.value:
        blocked = set(data) - FACULTY_EDITABLE
        if blocked:
            raise HTTPException(403, f"Only an administrator can change: {', '.join(sorted(blocked))}")
    if "faculty_id" in data and data["faculty_id"]:
        f = db.get(User, data["faculty_id"])
        if not f or f.role != Role.faculty.value:
            raise HTTPException(422, "faculty_id must reference a faculty user")
    for k, v in data.items():
        if v is not None or k in ("faculty_id", "program_id"):
            setattr(c, k, v)
    _validate_config(c)
    try:
        audit(db, user, "course_updated", "course", c.id, str(sorted(data)), request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A course with this code, year and section already exists")
    return course_out(db, c)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    audit(db, admin, "course_deleted", "course", c.id, f"{c.code} {c.academic_year}", request)
    db.delete(c)
    db.commit()


# ------------------------------------------------------------------ course outcomes & CO-PO

@router.get("/{course_id}/outcomes", response_model=list[OutcomeOut])
def list_cos(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_course_for_view(course_id, db, user).outcomes


@router.post("/{course_id}/outcomes", response_model=OutcomeOut, status_code=201)
def add_co(course_id: int, body: OutcomeIn, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    if any(co.code == body.code for co in c.outcomes):
        raise HTTPException(409, f"{body.code} already exists")
    co = CourseOutcome(course_id=c.id, **body.model_dump())
    db.add(co)
    db.commit()
    return co


@router.patch("/{course_id}/outcomes/{co_id}", response_model=OutcomeOut)
def update_co(course_id: int, co_id: int, body: OutcomeIn, user: User = Depends(require_staff),
              db: Session = Depends(get_db)):
    get_course_for_edit(course_id, db, user)
    co = db.get(CourseOutcome, co_id)
    if not co or co.course_id != course_id:
        raise HTTPException(404, "Course outcome not found")
    co.code, co.description = body.code, body.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"{body.code} already exists")
    return co


@router.delete("/{course_id}/outcomes/{co_id}", status_code=204)
def delete_co(course_id: int, co_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    get_course_for_edit(course_id, db, user)
    co = db.get(CourseOutcome, co_id)
    if not co or co.course_id != course_id:
        raise HTTPException(404, "Course outcome not found")
    db.delete(co)
    db.commit()


@router.get("/{course_id}/co-po")
def get_copo(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    pos = (db.query(ProgramOutcome).filter_by(program_id=c.program_id).order_by(ProgramOutcome.id).all()
           if c.program_id else [])
    links = (db.query(CoPoMapping).join(CourseOutcome).filter(CourseOutcome.course_id == c.id).all())
    return {
        "cos": [{"id": co.id, "code": co.code, "description": co.description} for co in c.outcomes],
        "pos": [{"id": p.id, "code": p.code, "description": p.description} for p in pos],
        "cells": [{"co_id": l.co_id, "po_id": l.po_id, "strength": l.strength} for l in links],
    }


@router.put("/{course_id}/co-po")
def put_copo(course_id: int, cells: list[CoPoCell], request: Request, user: User = Depends(require_staff),
             db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    co_ids = {co.id for co in c.outcomes}
    po_ids = {p.id for p in db.query(ProgramOutcome).filter_by(program_id=c.program_id).all()} if c.program_id else set()
    existing = {(l.co_id, l.po_id): l for l in
                db.query(CoPoMapping).filter(CoPoMapping.co_id.in_(co_ids)).all()} if co_ids else {}
    for cell in cells:
        if cell.co_id not in co_ids or cell.po_id not in po_ids:
            raise HTTPException(422, "CO/PO does not belong to this course/program")
        link = existing.get((cell.co_id, cell.po_id))
        if cell.strength is None:
            if link:
                db.delete(link)
        elif link:
            link.strength = cell.strength
        else:
            db.add(CoPoMapping(co_id=cell.co_id, po_id=cell.po_id, strength=cell.strength))
    audit(db, user, "copo_updated", "course", c.id, request=request)
    db.commit()
    return get_copo(course_id, user, db)


# ------------------------------------------------------------------ enrolment

@router.get("/{course_id}/students")
def list_students(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    rows = (db.query(User, StudentProfile)
            .join(Enrollment, Enrollment.student_id == User.id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .filter(Enrollment.course_id == c.id).order_by(StudentProfile.roll_no).all())
    return [{"id": u.id, "name": u.name, "email": u.email, "roll_no": sp.roll_no if sp else None,
             "section": sp.section if sp else None, "is_active": u.is_active} for u, sp in rows]


@router.post("/{course_id}/students")
def enroll(course_id: int, body: EnrollIn, request: Request, user: User = Depends(require_staff),
           db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    ids = set(body.student_ids)
    unknown = []
    if body.roll_nos:
        found = dict(db.query(StudentProfile.roll_no, StudentProfile.user_id)
                     .filter(StudentProfile.roll_no.in_(body.roll_nos)).all())
        unknown = [r for r in body.roll_nos if r not in found]
        ids |= set(found.values())
    students = db.query(User).filter(User.id.in_(ids), User.role == Role.student.value).all() if ids else []
    if len(students) != len(ids):
        raise HTTPException(422, "Some ids do not belong to student accounts")
    already = {sid for (sid,) in db.query(Enrollment.student_id).filter_by(course_id=c.id).all()}
    added = 0
    for s in students:
        if s.id not in already:
            db.add(Enrollment(course_id=c.id, student_id=s.id))
            added += 1
    audit(db, user, "students_enrolled", "course", c.id, f"{added} added", request)
    db.commit()
    return {"added": added, "unknown_roll_nos": unknown}


@router.post("/{course_id}/students/import")
async def enroll_csv(course_id: int, request: Request, file: UploadFile = File(...),
                     user: User = Depends(require_staff), db: Session = Depends(get_db)):
    rows = await read_csv_upload(file, {"roll_no"})
    return enroll(course_id, EnrollIn(roll_nos=[r["roll_no"] for r in rows if r["roll_no"]]), request, user, db)


@router.delete("/{course_id}/students/{student_id}", status_code=204)
def unenroll(course_id: int, student_id: int, request: Request, user: User = Depends(require_staff),
             db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    e = db.query(Enrollment).filter_by(course_id=c.id, student_id=student_id).first()
    if not e:
        raise HTTPException(404, "Student is not enrolled")
    db.delete(e)
    audit(db, user, "student_unenrolled", "course", c.id, str(student_id), request)
    db.commit()


# ------------------------------------------------------------------ NCP (semester-end)

@router.get("/{course_id}/ncp")
def get_ncp(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    res = {r.student_id: r for r in db.query(NcpResult).filter_by(course_id=c.id).all()}
    out = []
    for s in list_students(course_id, user, db):
        r = res.get(s["id"])
        out.append({**s, "marks": r.marks if r else None, "is_absent": r.is_absent if r else False})
    return {"max_marks": c.ncp_max_marks, "published": c.ncp_published, "students": out}


def _save_ncp(db: Session, c: Course, items: list[tuple[int, float | None, bool]]):
    enrolled = {sid for (sid,) in db.query(Enrollment.student_id).filter_by(course_id=c.id).all()}
    existing = {r.student_id: r for r in db.query(NcpResult).filter_by(course_id=c.id).all()}
    for sid, marks, absent in items:
        if sid not in enrolled:
            raise HTTPException(422, f"Student {sid} is not enrolled in this course")
        if marks is not None and marks > c.ncp_max_marks:
            raise HTTPException(422, f"Marks cannot exceed {c.ncp_max_marks:g}")
        r = existing.get(sid)
        if marks is None and not absent:
            if r:
                db.delete(r)
            continue
        if not r:
            r = NcpResult(course_id=c.id, student_id=sid)
            db.add(r)
        r.marks, r.is_absent = (None if absent else marks), absent


@router.put("/{course_id}/ncp")
def put_ncp(course_id: int, body: NcpBulkIn, request: Request, user: User = Depends(require_staff),
            db: Session = Depends(get_db)):
    c = get_course_for_edit(course_id, db, user)
    _save_ncp(db, c, [(r.student_id, r.marks, r.is_absent) for r in body.results])
    audit(db, user, "ncp_saved", "course", c.id, f"{len(body.results)} rows", request)
    db.commit()
    return get_ncp(course_id, user, db)


@router.post("/{course_id}/ncp/import")
async def import_ncp(course_id: int, request: Request, file: UploadFile = File(...),
                     user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """CSV columns: roll_no,marks (use AB for absent)"""
    c = get_course_for_edit(course_id, db, user)
    rows = await read_csv_upload(file, {"roll_no", "marks"})
    rolls = dict(db.query(StudentProfile.roll_no, StudentProfile.user_id).all())
    items = []
    for i, r in enumerate(rows, start=2):
        sid = rolls.get(r["roll_no"])
        if not sid:
            raise HTTPException(422, f"Line {i}: unknown roll number {r['roll_no']}")
        absent = r["marks"].upper() == "AB"
        items.append((sid, None if absent else parse_float(r["marks"], "marks", i), absent))
    _save_ncp(db, c, items)
    audit(db, user, "ncp_imported", "course", c.id, f"{len(items)} rows", request)
    db.commit()
    return {"saved": len(items)}


@router.get("/{course_id}/ncp/template")
def ncp_template(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    get_course_for_view(course_id, db, user)
    rows = [["roll_no", "name", "marks"]] + [[s["roll_no"], s["name"], ""] for s in list_students(course_id, user, db)]
    return csv_response(rows, f"ncp_{course_id}.csv")


# ------------------------------------------------------------------ consolidated views

@router.get("/{course_id}/gradebook")
def gradebook(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    return build_gradebook(db, c)


@router.get("/{course_id}/gradebook.xlsx")
def gradebook_xlsx(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    return file_response(reports.gradebook_xlsx(c, build_gradebook(db, c)), XLSX,
                         f"{c.code}_{c.academic_year}_consolidated.xlsx")


@router.get("/{course_id}/analytics")
def analytics(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    cfg = settings_service.get_all(db)
    gb = build_gradebook(db, c)
    students = gb["students"]

    def avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    comps = {k: avg([s["components"].get(k) for s in students])
             for k in ("quiz", "assignment", "practical", "attendance", "other")}
    per_assessment = []
    for a in gb["assessments"]:
        vals = [s["assessments"][a["id"]]["pct"] for s in students if s["assessments"][a["id"]]["pct"] is not None]
        per_assessment.append({
            "id": a["id"], "title": a["title"], "component": a["component"], "status": a["status"],
            "graded": len(vals), "average": avg(vals),
            "min": round(min(vals), 1) if vals else None, "max": round(max(vals), 1) if vals else None,
            "below_pass": sum(1 for v in vals if v < cfg["pass_mark_pct"]),
        })

    bins = [(0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
    basis = "final_pct" if any(s["final_pct"] is not None for s in students) else "cp_pct"
    dist = [{"band": f"{lo}–{min(hi, 100)}", "count": sum(1 for s in students if s[basis] is not None
                                                          and lo <= s[basis] < hi)} for lo, hi in bins]
    pairs = [(s["cp_pct"], s["ncp_pct"]) for s in students if s["cp_pct"] is not None and s["ncp_pct"] is not None]
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    grades: dict[str, int] = {}
    for s in students:
        if s["grade"]:
            grades[s["grade"]] = grades.get(s["grade"], 0) + 1
    finals = [s for s in students if s["passed"] is not None]
    risk = {p.student_id: p for p in db.query(Prediction).filter_by(course_id=c.id).all()}
    return {
        "students": len(students),
        "cp_average": avg([s["cp_pct"] for s in students]),
        "ncp_average": avg([s["ncp_pct"] for s in students]),
        "final_average": avg([s["final_pct"] for s in students]),
        "pass_rate": round(100 * sum(1 for s in finals if s["passed"]) / len(finals), 1) if finals else None,
        "components": comps,
        "assessments": per_assessment,
        "distribution": {"basis": basis, "bins": dist},
        "grades": [{"grade": b["grade"], "count": grades.get(b["grade"], 0)} for b in cfg["grade_bands"]],
        "correlation": {
            "pearson_r": pearson(xs, ys), "fit": linear_fit(xs, ys), "n": len(pairs),
            "points": [{"student_id": s["student_id"], "name": s["name"], "cp": s["cp_pct"], "ncp": s["ncp_pct"]}
                       for s in students if s["cp_pct"] is not None and s["ncp_pct"] is not None],
        },
        "risk_counts": {lvl: sum(1 for p in risk.values() if p.risk_level == lvl) for lvl in ("high", "medium", "low")},
        "leaderboard": sorted(
            [{"student_id": s["student_id"], "name": s["name"], "roll_no": s["roll_no"],
              "score": s["final_pct"] if s["final_pct"] is not None else s["cp_pct"]}
             for s in students if (s["final_pct"] if s["final_pct"] is not None else s["cp_pct"]) is not None],
            key=lambda r: -r["score"])[:10],
    }


@router.get("/{course_id}/attainment")
def course_attainment(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    return attainment.course_attainment(db, get_course_for_view(course_id, db, user))


@router.get("/{course_id}/attainment.pdf")
def attainment_pdf(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    return file_response(reports.attainment_pdf(attainment.course_attainment(db, c)), PDF,
                         f"CO_PO_attainment_{c.code}_{c.academic_year}.pdf")


@router.get("/{course_id}/attainment.xlsx")
def attainment_xlsx(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    return file_response(reports.attainment_xlsx(attainment.course_attainment(db, c)), XLSX,
                         f"CO_PO_attainment_{c.code}_{c.academic_year}.xlsx")


# ------------------------------------------------------------------ early warning

def _risk_rows(db: Session, c: Course):
    names = {u.id: (u.name, sp.roll_no if sp else None) for u, sp in
             db.query(User, StudentProfile).outerjoin(StudentProfile, StudentProfile.user_id == User.id)
             .join(Enrollment, Enrollment.student_id == User.id).filter(Enrollment.course_id == c.id).all()}
    order = {"high": 0, "medium": 1, "low": 2}
    preds = db.query(Prediction).filter_by(course_id=c.id).all()
    rows = [{"student_id": p.student_id, "name": names.get(p.student_id, ("?", None))[0],
             "roll_no": names.get(p.student_id, ("?", None))[1], "probability": p.probability,
             "risk_level": p.risk_level, "method": p.method, "features": p.features, "reasons": p.reasons,
             "generated_at": p.generated_at} for p in preds if p.student_id in names]
    return sorted(rows, key=lambda r: (order[r["risk_level"]], -r["probability"]))


@router.get("/{course_id}/risk")
def risk(course_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    mv, _ = prediction.active_model(db)
    return {"model": {"id": mv.id, "algorithm": mv.algorithm, "metrics": mv.metrics.get("holdout"),
                      "trained_at": mv.created_at} if mv else None,
            "students": _risk_rows(db, c)}


@router.post("/{course_id}/risk/recompute")
def recompute_risk(course_id: int, request: Request, user: User = Depends(require_staff),
                   db: Session = Depends(get_db)):
    c = get_course_for_view(course_id, db, user)
    prediction.predict_course(db, c)
    audit(db, user, "risk_recomputed", "course", c.id, request=request)
    db.commit()
    return risk(course_id, user, db)


@router.post("/{course_id}/harvest")
def harvest(course_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    n = prediction.harvest_course(db, c)
    audit(db, admin, "history_harvested", "course", c.id, f"{n} records", request)
    db.commit()
    return {"added": n}
