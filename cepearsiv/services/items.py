import base64
import re
from datetime import datetime
from typing import Literal

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from cepearsiv.models import Item, ItemTag, Tag, utcnow
from cepearsiv.schemas import ItemCreate
from cepearsiv.services.audit import log_audit

MAX_SLUG_ATTEMPTS = 5

_TR_FOLD = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "Ş": "s",
        "Ğ": "g",
        "Ü": "u",
        "Ö": "o",
        "Ç": "c",
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    }
)


def generate_slug(title: str) -> str:
    text = title.translate(_TR_FOLD).casefold()
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "item"


def create_item(session: Session, user_id: int, data: ItemCreate) -> Item:
    if data.type == "bookmark" and not data.url:
        raise ValueError("bookmark icin url zorunlu")
    base_slug = generate_slug(data.title)
    candidate = base_slug
    for attempt in range(MAX_SLUG_ATTEMPTS):
        if attempt > 0:
            candidate = f"{base_slug}-{attempt + 1}"
        item = Item(
            user_id=user_id,
            type=data.type,
            title=data.title,
            slug=candidate,
            body=data.body,
            url=data.url,
        )
        session.add(item)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        session.refresh(item)
        log_audit(session, user_id, "item.created", entity_type="item", entity_id=item.id)
        return item
    raise ValueError("benzersiz slug uretilemedi")


def get_item(session: Session, user_id: int, item_id: int) -> Item | None:
    return session.exec(
        select(Item).where(Item.id == item_id, Item.user_id == user_id)
    ).first()


def update_item(session: Session, user_id: int, item_id: int, data) -> Item:
    item = get_item(session, user_id, item_id)
    if item is None:
        raise ValueError("item bulunamadi")
    fields = data.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(item, field, value)
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def toggle_flag(
    session: Session,
    user_id: int,
    item_id: int,
    flag: Literal["favorite", "archived", "deleted"],
) -> Item:
    item = get_item(session, user_id, item_id)
    if item is None:
        raise ValueError("item bulunamadi")
    if flag == "deleted":
        item.is_deleted = True
    elif flag == "favorite":
        item.is_favorite = not item.is_favorite
    elif flag == "archived":
        item.is_archived = not item.is_archived
    else:
        raise ValueError("gecersiz bayrak")
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def restore_item(session: Session, user_id: int, item_id: int) -> Item:
    item = get_item(session, user_id, item_id)
    if item is None:
        raise ValueError("item bulunamadi")
    item.is_deleted = False
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_or_create_bookmark_by_url(
    session: Session, user_id: int, url: str, title: str | None, selection: str
) -> tuple[Item, bool]:
    existing = session.exec(
        select(Item).where(
            Item.user_id == user_id, Item.url == url, Item.is_deleted == False
        )
    ).first()
    if existing is not None:
        return existing, False
    data = ItemCreate(
        type="bookmark",
        title=(title or url).strip() or url,
        body=selection,
        url=url,
    )
    return create_item(session, user_id, data), True


def encode_cursor(created_at: datetime, item_id: int) -> str:
    payload = f"{created_at.isoformat()}|{item_id}".encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(token: str) -> tuple[datetime, int]:
    try:
        payload = base64.urlsafe_b64decode(token.encode()).decode()
        raw_ts, raw_id = payload.rsplit("|", 1)
        return datetime.fromisoformat(raw_ts), int(raw_id)
    except Exception:
        raise ValueError("gecersiz imlec")


def list_items(
    session: Session,
    user_id: int,
    type: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    archived: bool | None = None,
    deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
    cursor: str | None = None,
) -> tuple[list[Item], bool]:
    stmt = select(Item).where(Item.user_id == user_id, Item.is_deleted == deleted)
    if tag is not None:
        stmt = (
            stmt.join(ItemTag, ItemTag.item_id == Item.id)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(Tag.user_id == user_id, Tag.name == tag)
        )
    if type is not None:
        stmt = stmt.where(Item.type == type)
    if favorite is not None:
        stmt = stmt.where(Item.is_favorite == favorite)
    if archived is not None:
        stmt = stmt.where(Item.is_archived == archived)
    stmt = stmt.order_by(Item.created_at.desc(), Item.id.desc())
    if cursor:
        cursor_ts, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Item.created_at < cursor_ts,
                and_(Item.created_at == cursor_ts, Item.id < cursor_id),
            )
        )
    else:
        stmt = stmt.offset((page - 1) * page_size)
    stmt = stmt.limit(page_size + 1)
    rows = list(session.exec(stmt).all())
    has_next = len(rows) > page_size
    return rows[:page_size], has_next
