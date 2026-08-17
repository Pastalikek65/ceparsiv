import re
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from cepearsiv.models import Item, ItemTag, Tag, utcnow
from cepearsiv.schemas import ItemCreate

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
        return item
    raise ValueError("benzersiz slug uretilemedi")


def get_item(session: Session, user_id: int, item_id: int) -> Item | None:
    return session.exec(
        select(Item).where(Item.id == item_id, Item.user_id == user_id)
    ).first()


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
    stmt = (
        stmt.order_by(Item.created_at.desc(), Item.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )
    rows = list(session.exec(stmt).all())
    has_next = len(rows) > page_size
    return rows[:page_size], has_next
