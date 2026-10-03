from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import audit, require_admin, require_staff
from ..models import Program, Role, StudentProfile, User
from ..schemas import UserCreate, UserCreated, UserOut, UserUpdate
from ..security import generate_temp_password, hash_password
from ..utils import csv_response, read_csv_upload

router = APIRouter(prefix="/users", tags=["users"])


def _check_unique(db: Session, email: str | None, roll_no: str | None, exclude_user: int | None = None):
    if email:
        q = db.query(User.id).filter(User.email == email.lower())
        if exclude_user:
            q = q.filter(User.id != exclude_user)
        if q.first():
            raise HTTPException(409, f"Email {email} is already registered")
    if roll_no:
        q = db.query(StudentProfile.id).filter(StudentProfile.roll_no == roll_no)
        if exclude_user:
            q = q.filter(StudentProfile.user_id != exclude_user)
        if q.first():
            raise HTTPException(409, f"Roll number {roll_no} is already in use")


@router.get("")
def list_users(
    role: str | None = None, q: str | None = None, active: bool | None = None,
    program_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=500),
    user: User = Depends(require_staff), db: Session = Depends(get_db),
):
    query = db.query(User).options(joinedload(User.student_profile))
    if user.role == Role.faculty.value:
        role = Role.student.value  # faculty can only look up students (e.g. for enrolment)
    if role:
        query = query.filter(User.role == role)
    if active is not None:
        query = query.filter(User.is_active == active)
    if program_id:
        query = query.join(StudentProfile).filter(StudentProfile.program_id == program_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(StudentProfile, StudentProfile.user_id == User.id) if not program_id else query
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), StudentProfile.roll_no.ilike(like)))
    total = query.with_entities(func.count(func.distinct(User.id))).scalar()
    items = query.order_by(User.role, User.name).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [UserOut.model_validate(u) for u in items]}


@router.post("", response_model=UserCreated, status_code=201)
def create_user(body: UserCreate, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    roll = body.student_profile.roll_no.strip() if body.student_profile else None
    _check_unique(db, body.email, roll)
    temp = None if body.password else generate_temp_password()
    u = User(name=body.name.strip(), email=body.email.lower(), role=body.role, department=body.department,
             password_hash=hash_password(body.password or temp), must_change_password=True)
    if body.role == Role.student.value and body.student_profile:
        sp = body.student_profile
        if sp.program_id and not db.get(Program, sp.program_id):
            raise HTTPException(422, "Program not found")
        u.student_profile = StudentProfile(roll_no=roll, program_id=sp.program_id, batch=sp.batch,
                                           semester=sp.semester, section=sp.section)
    db.add(u)
    db.flush()
    audit(db, admin, "user_created", "user", u.id, f"{u.email} ({u.role})", request)
    db.commit()
    db.refresh(u)
    return UserCreated(user=UserOut.model_validate(u), temporary_password=temp)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    _check_unique(db, data.get("email"), (data.get("student_profile") or {}).get("roll_no"), exclude_user=u.id)
    if u.id == admin.id and (data.get("is_active") is False or data.get("role", "admin") != "admin"):
        raise HTTPException(422, "You cannot deactivate or demote your own account")
    for field in ("name", "department", "is_active", "role"):
        if field in data:
            setattr(u, field, data[field])
    if "email" in data:
        u.email = data["email"].lower()
    if data.get("is_active") is False or "role" in data:
        u.token_version += 1
    sp = data.get("student_profile")
    if sp:
        if u.student_profile:
            for k, v in sp.items():
                setattr(u.student_profile, k, v)
        else:
            u.student_profile = StudentProfile(**sp)
    if u.role == Role.student.value and not u.student_profile:
        raise HTTPException(422, "Students need a roll number")
    audit(db, admin, "user_updated", "user", u.id, str(list(data.keys())), request)
    db.commit()
    db.refresh(u)
    return u


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    temp = generate_temp_password()
    u.password_hash = hash_password(temp)
    u.must_change_password = True
    u.token_version += 1
    audit(db, admin, "password_reset", "user", u.id, request=request)
    db.commit()
    return {"temporary_password": temp}


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(422, "You cannot delete your own account")
    audit(db, admin, "user_deleted", "user", u.id, u.email, request)
    db.delete(u)
    db.commit()


@router.post("/import")
async def import_users(request: Request, file: UploadFile = File(...), admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """CSV columns: name,email,role[,department,roll_no,program_code,batch,semester,section]"""
    rows = await read_csv_upload(file, {"name", "email", "role"})
    programs = {p.code.lower(): p.id for p in db.query(Program).all()}
    created, errors, creds = 0, [], [["name", "email", "role", "temporary_password"]]
    seen_emails, seen_rolls = set(), set()
    for i, r in enumerate(rows, start=2):
        try:
            email, role = r["email"].lower(), r["role"].lower()
            if role not in ("admin", "faculty", "student"):
                raise ValueError(f"unknown role '{r['role']}'")
            if not r["name"] or "@" not in email:
                raise ValueError("name and a valid email are required")
            roll = r.get("roll_no") or None
            if role == "student" and not roll:
                raise ValueError("students need roll_no")
            if email in seen_emails or (roll and roll in seen_rolls):
                raise ValueError("duplicate email/roll_no in file")
            _check_unique(db, email, roll if role == "student" else None)
            prog = r.get("program_code", "").lower()
            if prog and prog not in programs:
                raise ValueError(f"unknown program_code '{r['program_code']}'")
            sem = int(r["semester"]) if r.get("semester") else None
            temp = generate_temp_password()
            u = User(name=r["name"], email=email, role=role, department=r.get("department") or None,
                     password_hash=hash_password(temp), must_change_password=True)
            if role == "student":
                u.student_profile = StudentProfile(roll_no=roll, program_id=programs.get(prog),
                                                   batch=r.get("batch") or None, semester=sem,
                                                   section=r.get("section") or None)
            db.add(u)
            db.flush()
            seen_emails.add(email)
            if roll:
                seen_rolls.add(roll)
            creds.append([u.name, u.email, u.role, temp])
            created += 1
        except HTTPException as e:
            errors.append({"line": i, "error": e.detail})
        except ValueError as e:
            errors.append({"line": i, "error": str(e)})
    if errors:
        db.rollback()
        return {"created": 0, "errors": errors}
    audit(db, admin, "users_imported", "user", None, f"{created} users", request)
    db.commit()
    return {"created": created, "errors": [], "credentials": creds}


@router.get("/import/template")
def import_template(_: User = Depends(require_admin)):
    return csv_response([
        ["name", "email", "role", "department", "roll_no", "program_code", "batch", "semester", "section"],
        ["Asha Rao", "asha.rao@example.edu", "student", "", "24STU0001", "BTECH-CSE", "2024-28", "3", "A"],
        ["Dr. K. Iyer", "k.iyer@example.edu", "faculty", "Computer Science", "", "", "", "", ""],
    ], "users_template.csv")
