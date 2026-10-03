import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, client_ip, get_current_user
from ..models import User, utcnow
from ..schemas import ChangePasswordIn, LoginIn, RefreshIn, TokenOut, UserOut
from ..security import (
    create_access_token, create_refresh_token, decode_token, hash_password, login_throttle,
    validate_password_strength, verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role, user.token_version),
        refresh_token=create_refresh_token(user.id, user.role, user.token_version),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{body.email.lower()}|{client_ip(request)}"
    wait = login_throttle.blocked(key)
    if wait:
        raise HTTPException(429, f"Too many failed attempts. Try again in {wait} seconds.")
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        login_throttle.fail(key)
        audit(db, user, "login_failed", "user", user.id if user else None, body.email, request)
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated. Contact the administrator.")
    login_throttle.reset(key)
    user.last_login_at = utcnow()
    audit(db, user, "login", "user", user.id, request=request)
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise HTTPException(401, "Session no longer valid")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=TokenOut)
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    problem = validate_password_strength(body.new_password)
    if problem:
        raise HTTPException(422, problem)
    if body.new_password == body.current_password:
        raise HTTPException(422, "New password must be different from the current one")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version += 1  # signs out every other session
    audit(db, user, "password_changed", "user", user.id, request=request)
    db.commit()
    return _tokens(user)


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    audit(db, user, "logout_all", "user", user.id, request=request)
    db.commit()
