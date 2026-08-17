from sqlmodel import Session

from cepearsiv.models import AuditLog


def log_audit(
    session: Session,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
    ip: str | None = None,
) -> None:
    try:
        session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
                ip=ip,
            )
        )
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
