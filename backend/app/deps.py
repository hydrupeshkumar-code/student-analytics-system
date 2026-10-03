import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Assessment, AuditLog, Course, Enrollment, Role, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session no longer valid")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")
        return user

    return checker


require_admin = require_roles(Role.admin)
require_staff = require_roles(Role.admin, Role.faculty)


def get_course_for_view(course_id: int, db: Session, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    if user.role == Role.admin.value:
        return course
    if user.role == Role.faculty.value and course.faculty_id == user.id:
        return course
    if user.role == Role.student.value:
        enrolled = db.query(Enrollment.id).filter_by(course_id=course_id, student_id=user.id).first()
        if enrolled:
            return course
    raise HTTPException(403, "You do not have access to this course")


def get_course_for_edit(course_id: int, db: Session, user: User) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    if user.role == Role.admin.value or (user.role == Role.faculty.value and course.faculty_id == user.id):
        return course
    raise HTTPException(403, "Only the course faculty or an administrator can change this course")


def get_assessment_for_edit(assessment_id: int, db: Session, user: User) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    get_course_for_edit(a.course_id, db, user)
    return a


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def audit(db: Session, user: User | None, action: str, entity: str | None = None,
          entity_id: int | None = None, detail: str | None = None, request: Request | None = None):
    db.add(AuditLog(
        user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id,
        detail=detail[:2000] if detail else None, ip=client_ip(request) if request else None,
    ))
