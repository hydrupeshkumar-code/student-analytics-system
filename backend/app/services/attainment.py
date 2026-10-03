"""CO/PO attainment (Objective O4), following the common NBA direct-attainment method.

1. For each CO, a student's CO score in CP = marks / max over the CP assessments mapped to that CO.
   The NCP (semester-end) score applies to every CO of the course.
2. % of students reaching the course target (co_target_pct) -> attainment level 0..3
   using the course thresholds (level1_pct / level2_pct / level3_pct).
3. CO attainment = (cp_weight * level_CP + ncp_weight * level_NCP) / (cp_weight + ncp_weight)
4. PO attainment = sum(CO attainment * mapping strength) / sum(mapping strength)
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models import CoPoMapping, Course, CourseOutcome, ProgramOutcome
from .correlation import build_gradebook


def level_for(pct_students: float | None, course: Course) -> int | None:
    if pct_students is None:
        return None
    if pct_students >= course.level3_pct:
        return 3
    if pct_students >= course.level2_pct:
        return 2
    if pct_students >= course.level1_pct:
        return 1
    return 0


def _summary(values: list[float], course: Course) -> dict:
    n = len(values)
    attained = sum(1 for v in values if v >= course.co_target_pct)
    pct = round(100.0 * attained / n, 1) if n else None
    return {"evaluated": n, "attained": attained, "pct_students": pct, "level": level_for(pct, course)}


def student_co_scores(gradebook: dict, course: Course) -> dict[int, dict[int, float | None]]:
    """student_id -> co_id -> CP percentage on the assessments mapped to that CO."""
    by_co: dict[int, list[dict]] = defaultdict(list)
    for a in gradebook["assessments"]:
        for co_id in a["co_ids"]:
            by_co[co_id].append(a)
    out: dict[int, dict[int, float | None]] = {}
    for s in gradebook["students"]:
        row: dict[int, float | None] = {}
        for co in course.outcomes:
            got = mx = 0.0
            for a in by_co.get(co.id, []):
                cell = s["assessments"].get(a["id"])
                if cell and cell["marks"] is not None:
                    got += cell["marks"]
                    mx += a["max_marks"]
            row[co.id] = round(100.0 * got / mx, 1) if mx else None
        out[s["student_id"]] = row
    return out


def course_attainment(db: Session, course: Course) -> dict:
    gb = build_gradebook(db, course)
    co_scores = student_co_scores(gb, course)
    ncp_values = [s["ncp_pct"] for s in gb["students"] if s["ncp_pct"] is not None]
    ncp_summary = _summary(ncp_values, course)

    cos_out = []
    co_values: dict[int, float | None] = {}
    wsum = course.cp_weight + course.ncp_weight
    for co in course.outcomes:
        cp_vals = [row[co.id] for row in co_scores.values() if row.get(co.id) is not None]
        cp = _summary(cp_vals, course)
        mapped = [a["title"] for a in gb["assessments"] if co.id in a["co_ids"]]
        l_cp, l_ncp = cp["level"], ncp_summary["level"]
        if l_cp is not None and l_ncp is not None and wsum:
            value = round((course.cp_weight * l_cp + course.ncp_weight * l_ncp) / wsum, 2)
            basis = "CP + NCP"
        elif l_cp is not None:
            value, basis = float(l_cp), "CP only"
        elif l_ncp is not None:
            value, basis = float(l_ncp), "NCP only"
        else:
            value, basis = None, "No data"
        co_values[co.id] = value
        cos_out.append({
            "id": co.id, "code": co.code, "description": co.description,
            "assessments": mapped, "cp": cp, "ncp": ncp_summary,
            "attainment": value, "basis": basis,
            "attained": None if value is None else value >= course.target_level,
        })

    pos_out = []
    matrix = []
    if course.program_id:
        pos = db.query(ProgramOutcome).filter_by(program_id=course.program_id).order_by(ProgramOutcome.id).all()
        links = (db.query(CoPoMapping).join(CourseOutcome, CourseOutcome.id == CoPoMapping.co_id)
                 .filter(CourseOutcome.course_id == course.id).all())
        strength = {(l.co_id, l.po_id): l.strength for l in links}
        for co in course.outcomes:
            matrix.append({"co_id": co.id, "co": co.code,
                           "values": {po.id: strength.get((co.id, po.id)) for po in pos}})
        for po in pos:
            num = den = 0.0
            for co in course.outcomes:
                st = strength.get((co.id, po.id))
                if st and co_values.get(co.id) is not None:
                    num += co_values[co.id] * st
                    den += st
            mapped_any = any(strength.get((co.id, po.id)) for co in course.outcomes)
            pos_out.append({"id": po.id, "code": po.code, "description": po.description,
                            "mapped": mapped_any,
                            "attainment": round(num / den, 2) if den else None})

    return {
        "course": {"id": course.id, "code": course.code, "name": course.name,
                   "academic_year": course.academic_year, "semester": course.semester,
                   "section": course.section,
                   "faculty": course.faculty.name if course.faculty else None,
                   "program": course.program.name if course.program else None},
        "config": {"co_target_pct": course.co_target_pct, "level1_pct": course.level1_pct,
                   "level2_pct": course.level2_pct, "level3_pct": course.level3_pct,
                   "target_level": course.target_level, "cp_weight": course.cp_weight,
                   "ncp_weight": course.ncp_weight},
        "students": len(gb["students"]),
        "cos": cos_out,
        "pos": pos_out,
        "matrix": matrix,
    }


def program_attainment(db: Session, program_id: int, academic_year: str | None = None) -> dict:
    q = db.query(Course).filter(Course.program_id == program_id)
    if academic_year:
        q = q.filter(Course.academic_year == academic_year)
    courses = q.order_by(Course.semester, Course.code).all()
    pos = db.query(ProgramOutcome).filter_by(program_id=program_id).order_by(ProgramOutcome.id).all()
    rows = []
    per_po: dict[int, list[float]] = defaultdict(list)
    for c in courses:
        att = course_attainment(db, c)
        vals = {p["id"]: p["attainment"] for p in att["pos"]}
        for pid, v in vals.items():
            if v is not None:
                per_po[pid].append(v)
        rows.append({"course_id": c.id, "code": c.code, "name": c.name, "semester": c.semester,
                     "academic_year": c.academic_year, "values": vals})
    summary = [{"id": p.id, "code": p.code, "description": p.description,
                "attainment": round(sum(per_po[p.id]) / len(per_po[p.id]), 2) if per_po[p.id] else None,
                "courses": len(per_po[p.id])} for p in pos]
    return {"program_id": program_id, "academic_year": academic_year,
            "pos": summary, "courses": rows,
            "po_list": [{"id": p.id, "code": p.code} for p in pos]}
