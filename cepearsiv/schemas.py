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
