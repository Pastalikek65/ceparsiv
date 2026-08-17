import hashlib
import secrets
from datetime import datetime, timezone

from sqlmodel import Session, select

from cepearsiv.models import ApiToken
from cepearsiv.services.audit import log_audit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_api_token(session: Session, user_id: int, name: str) -> tuple[ApiToken, str]:
    raw = secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=user_id,
        name=name,
        token_hash=_hash_token(raw),
        prefix=raw[:8],
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    log_audit(session, user_id, "token.created", entity_type="api_token", entity_id=token.id)
    return token, raw


def get_api_token_by_hash(session: Session, raw_token: str) -> ApiToken | None:
    token = session.exec(
        select(ApiToken).where(ApiToken.token_hash == _hash_token(raw_token))
    ).first()
    if token is None:
        return None
    if token.expires_at is not None and token.expires_at <= _utcnow():
        return None
    return token


def delete_api_token(session: Session, user_id: int, token_id: int) -> bool:
    token = session.exec(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
    ).first()
    if token is None:
        return False
    session.delete(token)
    session.commit()
    return True


def list_api_tokens(session: Session, user_id: int) -> list[ApiToken]:
    return list(
        session.exec(select(ApiToken).where(ApiToken.user_id == user_id)).all()
    )
