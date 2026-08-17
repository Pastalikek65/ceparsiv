from sqlalchemy import func
from sqlmodel import Session, select

from cepearsiv.models import ItemTag, Tag


def normalize(name: str) -> str:
    cleaned = name.strip().casefold()
    if not cleaned:
        raise ValueError("tag adi bos olamaz")
    if "," in cleaned:
        raise ValueError("tag adi virgul iceremez")
    return cleaned


def get_or_create_tags(session: Session, user_id: int, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for raw in names:
        name = normalize(raw)
        existing = session.exec(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        ).first()
        if existing is None:
            existing = Tag(user_id=user_id, name=name)
            session.add(existing)
            session.commit()
            session.refresh(existing)
        tags.append(existing)
    return tags


def set_item_tags(session: Session, user_id: int, item_id: int, names: list[str]) -> None:
    tags = get_or_create_tags(session, user_id, names)
    old_links = session.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all()
    for link in old_links:
        session.delete(link)
    for tag in tags:
        session.add(ItemTag(item_id=item_id, tag_id=tag.id))
    session.commit()


def get_item_tags(session: Session, user_id: int, item_id: int) -> list[Tag]:
    return list(
        session.exec(
            select(Tag)
            .join(ItemTag, Tag.id == ItemTag.tag_id)
            .where(ItemTag.item_id == item_id, Tag.user_id == user_id)
        ).all()
    )


def tags_with_counts(session: Session, user_id: int) -> list[tuple[Tag, int]]:
    stmt = (
        select(Tag, func.count(ItemTag.item_id))
        .outerjoin(ItemTag, ItemTag.tag_id == Tag.id)
        .where(Tag.user_id == user_id)
        .group_by(Tag.id)
        .order_by(func.count(ItemTag.item_id).desc(), Tag.name.asc())
    )
    return list(session.exec(stmt).all())
