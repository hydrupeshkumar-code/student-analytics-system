from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import audit, get_current_user, require_staff
from ..models import Assessment, Enrollment, Role, Rubric, RubricCriterion, RubricLevel, Score, User
from ..schemas import RubricIn, RubricOut
from ..services.rubric_engine import validate_rubric_payload

router = APIRouter(prefix="/rubrics", tags=["rubrics"])


def _out(db: Session, r: Rubric) -> RubricOut:
    o = RubricOut.model_validate(r)
    o.in_use = db.query(Score.id).join(Assessment).filter(Assessment.rubric_id == r.id).first() is not None
    o.owner_name = r.owner.name if r.owner else None
    return o


def _get(db: Session, rubric_id: int) -> Rubric:
    r = db.get(Rubric, rubric_id, options=[selectinload(Rubric.levels), selectinload(Rubric.criteria)])
    if not r:
        raise HTTPException(404, "Rubric not found")
    return r


def _can_edit(user: User, r: Rubric):
    if user.role != Role.admin.value and r.owner_id != user.id:
        raise HTTPException(403, "Only the rubric owner can change it — duplicate it to make your own copy")


def _apply(r: Rubric, body: RubricIn):
    r.title, r.description = body.title.strip(), body.description
    r.levels = [RubricLevel(label=lv.label.strip(), points=lv.points, position=i)
                for i, lv in enumerate(sorted(body.levels, key=lambda x: -x.points))]
    r.criteria = [RubricCriterion(name=c.name.strip(), description=c.description, weight=c.weight,
                                  descriptors=c.descriptors, position=i) for i, c in enumerate(body.criteria)]


@router.get("", response_model=list[RubricOut])
def list_rubrics(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    # rubrics are a shared institutional library; edit rights stay with the owner
    rs = (db.query(Rubric).options(selectinload(Rubric.levels), selectinload(Rubric.criteria))
          .order_by(Rubric.updated_at.desc()).all())
    return [_out(db, r) for r in rs]


@router.get("/{rubric_id}", response_model=RubricOut)
def get_rubric(rubric_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get(db, rubric_id)
    if user.role == Role.student.value:
        # students may view rubrics attached to visible assessments in their courses
        ok = (db.query(Assessment.id).join(Enrollment, Enrollment.course_id == Assessment.course_id)
              .filter(Assessment.rubric_id == r.id, Enrollment.student_id == user.id,
                      Assessment.status.in_(["completed", "finalized", "in_progress"])).first())
        if not ok:
            raise HTTPException(403, "You do not have access to this rubric")
    return _out(db, r)


@router.post("", response_model=RubricOut, status_code=201)
def create_rubric(body: RubricIn, request: Request, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    validate_rubric_payload(body.levels, body.criteria)
    r = Rubric(owner_id=user.id)
    _apply(r, body)
    db.add(r)
    db.flush()
    audit(db, user, "rubric_created", "rubric", r.id, r.title, request)
    db.commit()
    return _out(db, _get(db, r.id))


@router.put("/{rubric_id}", response_model=RubricOut)
def update_rubric(rubric_id: int, body: RubricIn, request: Request, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    r = _get(db, rubric_id)
    _can_edit(user, r)
    validate_rubric_payload(body.levels, body.criteria)
    if _out(db, r).in_use:
        # structure is locked once marks exist; allow cosmetic edits only
        same_shape = (len(body.levels) == len(r.levels) and len(body.criteria) == len(r.criteria))
        if not same_shape:
            raise HTTPException(409, "This rubric has been used for scoring. Duplicate it to change its structure.")
        r.title, r.description = body.title.strip(), body.description
        for lv, new in zip(r.levels, sorted(body.levels, key=lambda x: -x.points)):
            if abs(lv.points - new.points) > 1e-9:
                raise HTTPException(409, "Points cannot change after scoring. Duplicate the rubric instead.")
            lv.label = new.label.strip()
        for c, new in zip(r.criteria, body.criteria):
            if abs(c.weight - new.weight) > 1e-9:
                raise HTTPException(409, "Weightage cannot change after scoring. Duplicate the rubric instead.")
            c.name, c.description, c.descriptors = new.name.strip(), new.description, new.descriptors
    else:
        _apply(r, body)
    audit(db, user, "rubric_updated", "rubric", r.id, r.title, request)
    db.commit()
    return _out(db, _get(db, r.id))


@router.post("/{rubric_id}/duplicate", response_model=RubricOut, status_code=201)
def duplicate_rubric(rubric_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    src = _get(db, rubric_id)
    r = Rubric(owner_id=user.id, title=f"{src.title} (copy)", description=src.description)
    r.levels = [RubricLevel(label=l.label, points=l.points, position=l.position) for l in src.levels]
    r.criteria = [RubricCriterion(name=c.name, description=c.description, weight=c.weight,
                                  descriptors=c.descriptors, position=c.position) for c in src.criteria]
    db.add(r)
    db.commit()
    return _out(db, _get(db, r.id))


@router.delete("/{rubric_id}", status_code=204)
def delete_rubric(rubric_id: int, request: Request, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    r = _get(db, rubric_id)
    _can_edit(user, r)
    if db.query(Assessment.id).filter_by(rubric_id=r.id).first():
        raise HTTPException(409, "Rubric is attached to assessments; detach it first")
    audit(db, user, "rubric_deleted", "rubric", r.id, r.title, request)
    db.delete(r)
    db.commit()
