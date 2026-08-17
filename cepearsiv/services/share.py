import secrets

from sqlmodel import Session, select

from cepearsiv.models import Item, ShareToken
from cepearsiv.services.audit import log_audit


def _get_owned_item(session: Session, user_id: int, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None or item.user_id != user_id:
        raise ValueError("item bulunamadi")
    return item


def get_or_create_share_token(session: Session, user_id: int, item_id: int) -> ShareToken:
    _get_owned_item(session, user_id, item_id)
    existing = session.exec(
        select(ShareToken).where(ShareToken.item_id == item_id, ShareToken.user_id == user_id)
    ).first()
    if existing is not None:
        return existing
    share = ShareToken(
        user_id=user_id, item_id=item_id, token=secrets.token_urlsafe(16)
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    log_audit(session, user_id, "share.created", entity_type="item", entity_id=item_id)
    return share


def get_shared_item(session: Session, token: str) -> Item | None:
    share = session.exec(select(ShareToken).where(ShareToken.token == token)).first()
    if share is None:
        return None
    item = session.get(Item, share.item_id)
    if item is None or item.is_deleted or item.user_id != share.user_id:
        return None
    return item


def delete_share_token(session: Session, user_id: int, item_id: int) -> bool:
    _get_owned_item(session, user_id, item_id)
    share = session.exec(
        select(ShareToken).where(ShareToken.item_id == item_id, ShareToken.user_id == user_id)
    ).first()
    if share is None:
        return False
    session.delete(share)
    session.commit()
    log_audit(session, user_id, "share.deleted", entity_type="item", entity_id=item_id)
    return True
