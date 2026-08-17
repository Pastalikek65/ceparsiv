from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlmodel import Session

from cepearsiv.models import User, UserSession

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


def fix_form_value(value: str) -> str:
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def fix_form_encoding(form_data: dict[str, str]) -> dict[str, str]:
    return {key: fix_form_value(value) for key, value in form_data.items()}
