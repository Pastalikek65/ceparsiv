import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from cepearsiv.config import settings
from cepearsiv.models import User, UserSession
from cepearsiv.security import generate_token, hash_password, verify_password

RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 300

_attempts: dict[tuple[str, str], list[float]] = defaultdict(list)


class LimitExceeded(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reset_rate_limit_state() -> None:
    _attempts.clear()


def _check_rate_limit(key: tuple[str, str]) -> None:
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    recent = [t for t in _attempts[key] if t > window_start]
    if len(recent) >= RATE_LIMIT_MAX:
        _attempts[key] = recent
        raise LimitExceeded("cok fazla deneme")
    recent.append(now)
    _attempts[key] = recent


def register(session: Session, username: str, password: str) -> User:
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing is not None:
        raise ValueError("bu kullanici adi alinmis")
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, username: str, password: str, ip: str) -> User | None:
    _check_rate_limit((ip, username))
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_session(session: Session, user_id: int, ip: str) -> str:
    token = generate_token()
    expires_at = _utcnow() + timedelta(hours=settings.session_hours)
    session.add(UserSession(id=token, user_id=user_id, expires_at=expires_at, ip=ip))
    session.commit()
    return token


def delete_session(session: Session, token: str) -> None:
    row = session.get(UserSession, token)
    if row is not None:
        session.delete(row)
        session.commit()


def cleanup_expired_sessions(session: Session) -> int:
    expired = session.exec(select(UserSession).where(UserSession.expires_at <= _utcnow())).all()
    count = len(expired)
    for row in expired:
        session.delete(row)
    session.commit()
    return count
