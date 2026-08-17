from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from cepearsiv.models import User, UserSession
from cepearsiv.services.tokens import get_api_token_by_hash

SESSION_COOKIE = "session_token"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = session.get(UserSession, token)
    if row is None or row.expires_at <= _utcnow():
        return None
    return session.get(User, row.user_id)


def get_optional_current_user(request: Request, session: Session = Depends(get_session)) -> User | None:
    return get_current_user(request, session)


def get_api_user(request: Request, session: Session = Depends(get_session)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="token eksik")
    raw = header[len("Bearer "):].strip()
    token = get_api_token_by_hash(session, raw)
    if token is None:
        raise HTTPException(status_code=401, detail="gecersiz veya suresi dolmus token")
    user = session.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="gecersiz veya suresi dolmus token")
    token.last_seen_at = _utcnow()
    session.add(token)
    session.commit()
    return user


def fix_form_value(value: str) -> str:
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def fix_form_encoding(form_data: dict[str, str]) -> dict[str, str]:
    return {key: fix_form_value(value) for key, value in form_data.items()}
