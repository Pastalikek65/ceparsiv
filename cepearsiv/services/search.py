import html
import re

from sqlalchemy import func, or_, text
from sqlmodel import Session, select

from cepearsiv.models import Item, ItemTag, Tag

FTS5_OPERATORS_CHARS = ['"', "*"]


def _clean_fts_term(term: str) -> str:
    for ch in FTS5_OPERATORS_CHARS:
        term = term.replace(ch, "")
    return term


def build_fts_query(user_input: str) -> str:
    terms = [
        cleaned
        for raw in user_input.strip().split()
        if (cleaned := _clean_fts_term(raw))
    ]
    return " AND ".join(f'"{term}"' for term in terms)


def _ensure_casefold(session: Session) -> None:
    raw = session.connection().connection.dbapi_connection
    raw.create_function(
        "casefold", 1, lambda v: v.casefold() if isinstance(v, str) else v
    )


def _escape_like(term: str) -> str:
    escaped = term.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_fts5(
    session: Session,
    user_id: int,
    q: str,
    type: str | None,
    tag: str | None,
    include_archived: bool,
    include_deleted: bool,
    page: int,
    page_size: int,
) -> tuple[list[Item], bool]:
    fts_query = build_fts_query(q)
    if not fts_query:
        return [], False
    sql = [
        "SELECT items.id FROM items_fts",
        "JOIN items ON items.id = items_fts.rowid",
    ]
    params: dict[str, object] = {"fts": fts_query, "uid": user_id}
    if tag is not None:
        sql.append(
            "JOIN item_tags ON item_tags.item_id = items.id"
            " JOIN tags ON tags.id = item_tags.tag_id AND tags.user_id = :uid"
        )
    where = ["items_fts MATCH :fts", "items.user_id = :uid"]
    if not include_deleted:
        where.append("items.is_deleted = 0")
    if not include_archived:
        where.append("items.is_archived = 0")
    if type is not None:
        where.append("items.type = :itype")
        params["itype"] = type
    if tag is not None:
        where.append("tags.name = :tag")
        params["tag"] = tag
    sql.append(f"WHERE {' AND '.join(where)}")
    sql.append("ORDER BY items.created_at DESC, items.id DESC")
    sql.append("LIMIT :lim OFFSET :off")
    params["lim"] = page_size + 1
    params["off"] = (page - 1) * page_size
    rows = session.execute(text(" ".join(sql)), params).all()
    ids = [row[0] for row in rows]
    if not ids:
        return [], False
    found = session.exec(select(Item).where(Item.id.in_(ids))).all()
    by_id = {item.id: item for item in found}
    items = [by_id[item_id] for item_id in ids if item_id in by_id]
    has_next = len(items) > page_size
    return items[:page_size], has_next


def _search_like(
    session: Session,
    user_id: int,
    q: str,
    type: str | None,
    tag: str | None,
    include_archived: bool,
    include_deleted: bool,
    page: int,
    page_size: int,
) -> tuple[list[Item], bool]:
    _ensure_casefold(session)
    stmt = select(Item).where(Item.user_id == user_id)
    if tag is not None:
        stmt = stmt.join(ItemTag, ItemTag.item_id == Item.id).join(
            Tag, Tag.id == ItemTag.tag_id
        ).where(Tag.user_id == user_id, Tag.name == tag)
    if not include_deleted:
        stmt = stmt.where(Item.is_deleted == False)
    if not include_archived:
        stmt = stmt.where(Item.is_archived == False)
    if type is not None:
        stmt = stmt.where(Item.type == type)
    terms = [t for t in q.strip().split() if t]
    if not terms:
        return [], False
    conds = []
    for term in terms:
        pattern = _escape_like(term)
        conds.append(
            or_(
                func.casefold(Item.title).like(pattern, escape="\\"),
                func.casefold(Item.body).like(pattern, escape="\\"),
            )
        )
    for cond in conds:
        stmt = stmt.where(cond)
    stmt = (
        stmt.order_by(Item.created_at.desc(), Item.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )
    rows = list(session.exec(stmt).all())
    has_next = len(rows) > page_size
    return rows[:page_size], has_next


def search_items(
    session: Session,
    user_id: int,
    q: str,
    backend: str,
    type: str | None = None,
    tag: str | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Item], bool]:
    if not q or not q.strip():
        raise ValueError("arama sorgusu bos olamaz")
    if backend in ("fts5", "trigram"):
        if backend == "trigram" and _needs_like(q):
            return _search_like(
                session, user_id, q, type, tag, include_archived, include_deleted,
                page, page_size,
            )
        return _search_fts5(
            session, user_id, q, type, tag, include_archived, include_deleted,
            page, page_size,
        )
    if backend == "like":
        return _search_like(
            session, user_id, q, type, tag, include_archived, include_deleted,
            page, page_size,
        )
    raise ValueError(f"bilinmeyen arama backend: {backend}")


def _needs_like(user_input: str) -> bool:
    terms = [raw for raw in user_input.strip().split() if _clean_fts_term(raw)]
    if not terms:
        return False
    return any(len(term) < 3 for term in terms)


def detect_backend(session: Session) -> str:
    row = session.execute(
        text("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='items_fts'")
    ).first()
    if row is None:
        return "like"
    if row[1] and "trigram" in row[1]:
        return "trigram"
    return "fts5"


def build_highlight(body: str, terms: list[str], radius: int = 60) -> str:
    if not body:
        return ""
    lowered = body.lower()
    first = len(body)
    for term in terms:
        idx = lowered.find(term.lower())
        if idx != -1:
            first = min(first, idx)
    if first == len(body):
        snippet = body[: 2 * radius]
        prefix = ""
        suffix = ""
    else:
        start = max(0, first - radius)
        end = min(len(body), first + radius)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(body) else ""
        snippet = body[start:end]
    text = html.escape(prefix + snippet + suffix)
    escaped = [html.escape(t) for t in terms if t.strip()]
    if not escaped:
        return text
    pattern = re.compile("(" + "|".join(re.escape(t) for t in escaped) + ")", re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", text)
