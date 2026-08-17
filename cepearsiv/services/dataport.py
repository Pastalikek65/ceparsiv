import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session, select

from cepearsiv.models import Item, ItemTag, Tag, User
from cepearsiv.services.items import generate_slug

MAX_IMPORT_ITEMS = 5000
MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_TITLE_LEN = 200
MAX_BODY_LEN = 100000
MAX_URL_LEN = 2048
MAX_SLUG_ATTEMPTS = 5
ALLOWED_TYPES = {"note", "bookmark", "snippet"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def export_user_data(session: Session, user_id: int) -> dict:
    user = session.get(User, user_id)
    username = user.username if user is not None else ""
    items = session.exec(
        select(Item)
        .where(Item.user_id == user_id, Item.is_deleted == False)
        .order_by(Item.id)
    ).all()
    rows = []
    for item in items:
        tag_names = [
            tag.name
            for tag in session.exec(
                select(Tag)
                .join(ItemTag, Tag.id == ItemTag.tag_id)
                .where(ItemTag.item_id == item.id)
            ).all()
        ]
        rows.append(
            {
                "type": item.type,
                "title": item.title,
                "slug": item.slug,
                "body": item.body,
                "url": item.url,
                "is_favorite": item.is_favorite,
                "is_archived": item.is_archived,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "tags": tag_names,
            }
        )
    return {
        "schema_version": 1,
        "exported_at": _utcnow().isoformat(),
        "user": username,
        "items": rows,
    }


def _validate_items(items: list) -> list[dict]:
    cleaned: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError("gecersiz item kaydi")
        item_type = raw.get("type")
        title = raw.get("title")
        body = raw.get("body")
        url = raw.get("url")
        tags = raw.get("tags", [])
        if item_type not in ALLOWED_TYPES:
            raise ValueError("gecersiz type alani")
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_LEN:
            raise ValueError("gecersiz title alani")
        if body is None:
            body = ""
        if not isinstance(body, str) or len(body) > MAX_BODY_LEN:
            raise ValueError("gecersiz body alani")
        if url is not None:
            if not isinstance(url, str) or len(url) > MAX_URL_LEN:
                raise ValueError("gecersiz url alani")
            url = url.strip() or None
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError("gecersiz tags alani")
        slug = raw.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            slug = generate_slug(title)
        cleaned.append(
            {
                "type": item_type,
                "title": title.strip(),
                "slug": slug.strip(),
                "body": body,
                "url": url,
                "is_favorite": bool(raw.get("is_favorite", False)),
                "is_archived": bool(raw.get("is_archived", False)),
                "created_at": _parse_dt(raw.get("created_at"), _utcnow()),
                "updated_at": _parse_dt(raw.get("updated_at"), _utcnow()),
                "tags": tags,
            }
        )
    return cleaned


def _rebuild_fts(session: Session) -> None:
    try:
        session.execute(text("INSERT INTO items_fts(items_fts) VALUES('rebuild')"))
        session.commit()
    except OperationalError:
        session.rollback()


def import_user_data(session: Session, user_id: int, data: dict) -> int:
    if not isinstance(data, dict):
        raise ValueError("gecersiz import dosyasi")
    if data.get("schema_version") != 1:
        raise ValueError("Invalid schema version")
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("gecersiz items alani")
    if len(items) > MAX_IMPORT_ITEMS:
        raise ValueError("Too many items")
    estimated = sum(
        len(json.dumps(item, ensure_ascii=False).encode("utf-8")) for item in items
    )
    if estimated > MAX_IMPORT_BYTES:
        raise ValueError("File too large")
    cleaned = _validate_items(items)

    used_slugs = set(
        session.exec(select(Item.slug).where(Item.user_id == user_id)).all()
    )
    tag_ids = {
        tag.name: tag.id
        for tag in session.exec(select(Tag).where(Tag.user_id == user_id)).all()
    }
    count = 0
    try:
        for row in cleaned:
            slug = row["slug"]
            candidate = slug
            attempt = 2
            while candidate in used_slugs and attempt <= MAX_SLUG_ATTEMPTS:
                candidate = f"{slug}-import-{attempt}"
                attempt += 1
            used_slugs.add(candidate)
            item = Item(
                user_id=user_id,
                type=row["type"],
                title=row["title"],
                slug=candidate,
                body=row["body"],
                url=row["url"],
                is_favorite=row["is_favorite"],
                is_archived=row["is_archived"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            session.add(item)
            session.flush()
            for tag_name in row["tags"]:
                name = tag_name.strip().casefold()
                if not name or "," in name:
                    continue
                tag_id = tag_ids.get(name)
                if tag_id is None:
                    tag = Tag(user_id=user_id, name=name)
                    session.add(tag)
                    session.flush()
                    tag_id = tag.id
                    tag_ids[name] = tag_id
                session.add(ItemTag(item_id=item.id, tag_id=tag_id))
            count += 1
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("import sirasinda veritabani hatasi")
    except Exception:
        session.rollback()
        raise
    _rebuild_fts(session)
    return count
