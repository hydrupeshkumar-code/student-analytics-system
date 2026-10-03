import secrets
import string
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings

settings = get_settings()


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


def validate_password_strength(raw: str) -> str | None:
    if len(raw) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isdigit() for c in raw) or not any(c.isalpha() for c in raw):
        return "Password must contain letters and numbers"
    return None


def _encode(user_id: int, role: str, token_version: int, kind: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "type": kind,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str, token_version: int) -> str:
    return _encode(user_id, role, token_version, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: int, role: str, token_version: int) -> str:
    return _encode(user_id, role, token_version, "refresh", timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


class LoginThrottle:
    """In-process sliding-window limiter for failed logins (per email+ip).
    For multi-instance deployments put a shared limiter (e.g. Redis / reverse proxy) in front."""

    def __init__(self):
        self._fails: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float):
        q = self._fails[key]
        while q and now - q[0] > settings.login_window_seconds:
            q.popleft()

    def blocked(self, key: str) -> int:
        """Returns seconds to wait (0 if allowed)."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            q = self._fails[key]
            if len(q) >= settings.login_max_attempts:
                return int(settings.login_window_seconds - (now - q[0])) + 1
            return 0

    def fail(self, key: str):
        with self._lock:
            self._fails[key].append(time.monotonic())

    def reset(self, key: str):
        with self._lock:
            self._fails.pop(key, None)


login_throttle = LoginThrottle()
