from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utcnow)


class UserSession(SQLModel, table=True):
    __tablename__ = "sessions"
    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    ip: Optional[str] = Field(default=None)

    __table_args__ = (Index("ix_sessions_expires", "expires_at"),)


class Item(SQLModel, table=True):
    __tablename__ = "items"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    type: str = Field(default="note")
    title: str
    slug: str
    body: str = Field(default="")
    url: Optional[str] = Field(default=None)
    is_favorite: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "slug"),
        Index("ix_items_user_deleted_created", "user_id", "is_deleted", text("created_at DESC")),
        Index("ix_items_user_type", "user_id", "type"),
    )


class Tag(SQLModel, table=True):
    __tablename__ = "tags"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    name: str
    created_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "name"),)


class ItemTag(SQLModel, table=True):
    __tablename__ = "item_tags"
    item_id: Optional[int] = Field(default=None, foreign_key="items.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tags.id", primary_key=True, index=True)


class ApiToken(SQLModel, table=True):
    __tablename__ = "api_tokens"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    name: str
    token_hash: str = Field(unique=True)
    prefix: str
    last_seen_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = Field(default=None)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    action: str
    entity_type: Optional[str] = Field(default=None)
    entity_id: Optional[int] = Field(default=None)
    detail: Optional[str] = Field(default=None)
    ip: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", text("created_at DESC")),
    )


class ShareToken(SQLModel, table=True):
    __tablename__ = "share_tokens"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    item_id: int = Field(foreign_key="items.id", unique=True)
    token: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow)
