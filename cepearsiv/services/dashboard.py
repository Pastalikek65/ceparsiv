from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from cepearsiv.models import Item, Tag


def dashboard_stats(session: Session, user_id: int) -> dict:
    total = session.exec(
        select(func.count(Item.id)).where(Item.user_id == user_id, Item.is_deleted == False)
    ).one()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    last7 = session.exec(
        select(func.count(Item.id)).where(
            Item.user_id == user_id, Item.is_deleted == False, Item.created_at >= week_ago
        )
    ).one()
    favorites = session.exec(
        select(func.count(Item.id)).where(
            Item.user_id == user_id, Item.is_deleted == False, Item.is_favorite == True
        )
    ).one()
    tags = session.exec(select(func.count(Tag.id)).where(Tag.user_id == user_id)).one()
    return {"total": total, "last7": last7, "favorites": favorites, "tags": tags}
