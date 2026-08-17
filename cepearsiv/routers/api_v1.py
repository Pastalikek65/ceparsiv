from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from cepearsiv.deps import get_api_user, get_session
from cepearsiv.schemas import ItemCreate, ItemOut, ItemUpdate, SearchOut, TagOut
from cepearsiv.services.items import (
    create_item,
    decode_cursor,
    encode_cursor,
    get_item,
    list_items,
    toggle_flag,
    update_item,
)
from cepearsiv.services.search import detect_backend, search_items
from cepearsiv.services.tags import get_item_tags, tags_with_counts

router = APIRouter()

MAX_PAGE_LIMIT = 100


def _item_out(session: Session, user_id: int, item) -> ItemOut:
    tag_names = [tag.name for tag in get_item_tags(session, user_id, item.id)]
    return ItemOut.from_item(item, tags=tag_names)


@router.get("/items")
def api_list_items(
    request: Request,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
    type: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    archived: bool | None = None,
    deleted: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
):
    if cursor is not None:
        try:
            decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=422, detail="gecersiz imlec")
    items, has_next = list_items(
        session,
        user.id,
        type=type,
        tag=tag,
        favorite=favorite,
        archived=archived,
        deleted=deleted,
        page=page,
        page_size=limit,
        cursor=cursor,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if (items and has_next) else None
    return {
        "items": [_item_out(session, user.id, item) for item in items],
        "has_next": has_next,
        "page": page,
        "next_cursor": next_cursor,
    }


@router.post("/items", status_code=201)
def api_create_item(
    request: Request,
    data: ItemCreate,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
):
    try:
        item = create_item(session, user.id, data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return _item_out(session, user.id, item)


@router.get("/items/{item_id}")
def api_get_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
):
    item = get_item(session, user.id, item_id)
    if item is None or item.is_deleted:
        raise HTTPException(status_code=404, detail="item bulunamadi")
    return _item_out(session, user.id, item)


@router.patch("/items/{item_id}")
def api_update_item(
    request: Request,
    item_id: int,
    data: ItemUpdate,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
):
    try:
        item = update_item(session, user.id, item_id, data)
    except ValueError:
        raise HTTPException(status_code=404, detail="item bulunamadi")
    return _item_out(session, user.id, item)


@router.delete("/items/{item_id}")
def api_delete_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
):
    try:
        toggle_flag(session, user.id, item_id, flag="deleted")
    except ValueError:
        raise HTTPException(status_code=404, detail="item bulunamadi")
    return {"detail": "deleted"}


@router.get("/search")
def api_search(
    request: Request,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
    q: str = Query(min_length=1),
    type: str | None = None,
    tag: str | None = None,
    include_archived: bool = True,
    include_deleted: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_LIMIT),
):
    try:
        items, has_next = search_items(
            session,
            user.id,
            q=q,
            backend=detect_backend(session),
            type=type,
            tag=tag,
            include_archived=include_archived,
            include_deleted=include_deleted,
            page=page,
            page_size=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return SearchOut(
        items=[_item_out(session, user.id, item) for item in items],
        has_next=has_next,
    )


@router.get("/tags")
def api_tags(
    request: Request,
    session: Session = Depends(get_session),
    user=Depends(get_api_user),
):
    rows = tags_with_counts(session, user.id)
    return {"tags": [TagOut(name=tag.name, count=count) for tag, count in rows]}
