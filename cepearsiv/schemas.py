from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ItemCreate(BaseModel):
    type: Literal["note", "bookmark", "snippet"] = "note"
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="")
    url: str | None = None

    @model_validator(mode="after")
    def bookmark_requires_url(self) -> "ItemCreate":
        if self.type == "bookmark" and not self.url:
            raise ValueError("bookmark icin url zorunlu")
        return self


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    url: str | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None


class ItemOut(BaseModel):
    id: int
    type: str
    title: str
    slug: str
    body: str
    url: str | None
    is_favorite: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_item(cls, item, tags: list[str] | None = None) -> "ItemOut":
        return cls(
            id=item.id,
            type=item.type,
            title=item.title,
            slug=item.slug,
            body=item.body,
            url=item.url,
            is_favorite=item.is_favorite,
            is_archived=item.is_archived,
            created_at=item.created_at,
            updated_at=item.updated_at,
            tags=tags or [],
        )


class SearchOut(BaseModel):
    items: list[ItemOut]
    has_next: bool


class TagOut(BaseModel):
    name: str
    count: int
