from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_current_user, require_admin, require_staff
from ..models import Course, Program, ProgramOutcome, User
from ..schemas import OutcomeIn, OutcomeOut, ProgramIn, ProgramOut
from ..services import attainment, reports
from ..utils import XLSX, file_response

router = APIRouter(prefix="/programs", tags=["programs"])


@router.get("", response_model=list[ProgramOut])
def list_programs(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Program).order_by(Program.code).all()


@router.post("", response_model=ProgramOut, status_code=201)
def create_program(body: ProgramIn, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    if db.query(Program.id).filter(Program.code == body.code).first():
        raise HTTPException(409, "Program code already exists")
    p = Program(**body.model_dump())
    db.add(p)
    db.flush()
    audit(db, admin, "program_created", "program", p.id, p.code, request)
    db.commit()
    return p


@router.patch("/{program_id}", response_model=ProgramOut)
def update_program(program_id: int, body: ProgramIn, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404, "Program not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Program code already exists")
    return p


@router.delete("/{program_id}", status_code=204)
def delete_program(program_id: int, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404, "Program not found")
    if db.query(Course.id).filter_by(program_id=program_id).first():
        raise HTTPException(409, "Program has courses; reassign or delete them first")
    audit(db, admin, "program_deleted", "program", p.id, p.code, request)
    db.delete(p)
    db.commit()


@router.post("/{program_id}/outcomes", response_model=OutcomeOut, status_code=201)
def add_po(program_id: int, body: OutcomeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(Program, program_id):
        raise HTTPException(404, "Program not found")
    if db.query(ProgramOutcome.id).filter_by(program_id=program_id, code=body.code).first():
        raise HTTPException(409, f"{body.code} already exists")
    po = ProgramOutcome(program_id=program_id, **body.model_dump())
    db.add(po)
    db.commit()
    return po


@router.patch("/{program_id}/outcomes/{po_id}", response_model=OutcomeOut)
def update_po(program_id: int, po_id: int, body: OutcomeIn, admin: User = Depends(require_admin),
              db: Session = Depends(get_db)):
    po = db.get(ProgramOutcome, po_id)
    if not po or po.program_id != program_id:
        raise HTTPException(404, "Program outcome not found")
    po.code, po.description = body.code, body.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"{body.code} already exists")
    return po


@router.delete("/{program_id}/outcomes/{po_id}", status_code=204)
def delete_po(program_id: int, po_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    po = db.get(ProgramOutcome, po_id)
    if not po or po.program_id != program_id:
        raise HTTPException(404, "Program outcome not found")
    db.delete(po)
    db.commit()


@router.get("/{program_id}/attainment")
def program_attainment(program_id: int, academic_year: str | None = None,
                       _: User = Depends(require_staff), db: Session = Depends(get_db)):
    if not db.get(Program, program_id):
        raise HTTPException(404, "Program not found")
    return attainment.program_attainment(db, program_id, academic_year)


@router.get("/{program_id}/attainment.xlsx")
def program_attainment_xlsx(program_id: int, academic_year: str | None = None,
                            _: User = Depends(require_staff), db: Session = Depends(get_db)) -> Response:
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404, "Program not found")
    data = attainment.program_attainment(db, program_id, academic_year)
    return file_response(reports.program_xlsx(p, data), XLSX, f"PO_attainment_{p.code}.xlsx")
