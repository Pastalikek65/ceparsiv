import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlmodel import Session

from cepearsiv.deps import fix_form_value, get_current_user, get_session
from cepearsiv.schemas import ItemCreate
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.items import (
    create_item,
    get_item,
    list_items,
    restore_item,
    toggle_flag,
)
from cepearsiv.services.tags import get_item_tags, set_item_tags

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"

FLAG_VALUES = {"favorite", "archived", "deleted"}


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _csrf_response(request: Request, template: str, status_code: int = 200, **context):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    context["csrf_token"] = token
    return templates.TemplateResponse(request, template, context, status_code=status_code)


def _parse_filters(request: Request):
    item_type = request.query_params.get("type") or None
    tag = request.query_params.get("tag") or None
    favorite = request.query_params.get("favorite") == "1" or None
    archived = request.query_params.get("archived") == "1" or None
    deleted = request.query_params.get("deleted") == "1"
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
    except ValueError:
        page = 1
    return item_type, tag, favorite, archived, deleted, page


@router.get("/items")
def items_list(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    item_type, tag, favorite, archived, deleted, page = _parse_filters(request)
    items, has_next = list_items(
        session,
        user.id,
        type=item_type,
        tag=tag,
        favorite=favorite,
        archived=archived,
        deleted=deleted,
        page=page,
    )
    params = []
    if item_type:
        params.append(f"type={item_type}")
    if tag:
        params.append(f"tag={tag}")
    if favorite:
        params.append("favorite=1")
    if archived:
        params.append("archived=1")
    if deleted:
        params.append("deleted=1")
    base_query = f"?{'&'.join(params)}" if params else ""
    if params:
        base_query += "&"
    return _csrf_response(
        request,
        "items/list.html",
        user=user,
        items=items,
        has_next=has_next,
        current_page=page,
        prev_query=f"{base_query}page={page - 1}" if page > 1 else None,
        next_query=f"{base_query}page={page + 1}" if has_next else None,
        filters={
            "type": item_type or "",
            "tag": tag or "",
            "favorite": favorite or False,
            "archived": archived or False,
            "deleted": deleted,
        },
    )


@router.get("/items/new")
def items_new(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return _csrf_response(
        request, "items/form.html", user=user, action="/items", item=None, error=None
    )


def _parse_tag_names(raw_tags: str) -> list[str]:
    return [part.strip() for part in raw_tags.split(",") if part.strip()]


@router.post("/items")
def items_create(
    request: Request,
    session: Session = Depends(get_session),
    title: str = Form(""),
    type: str = Form("note"),
    body: str = Form(""),
    url: str = Form(""),
    tags: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    title = fix_form_value(title)
    body = fix_form_value(body)
    url = fix_form_value(url)
    type = fix_form_value(type)
    tags = fix_form_value(tags)
    if not _csrf_ok(request, csrf_token):
        return _csrf_response(
            request,
            "items/form.html",
            status_code=403,
            user=user,
            action="/items",
            item=None,
            error="CSRF dogrulamasi basarisiz.",
        )
    try:
        data = ItemCreate(type=type, title=title.strip(), body=body, url=url.strip() or None)
    except ValidationError as error:
        message = error.errors()[0].get("msg", "Geçersiz giriş.") if error.errors() else "Geçersiz giriş."
        return _csrf_response(
            request,
            "items/form.html",
            status_code=422,
            user=user,
            action="/items",
            item={"title": title, "type": type, "body": body, "url": url, "tags": tags},
            error=message,
        )
    tag_names = _parse_tag_names(tags)
    try:
        item = create_item(session, user.id, data)
        if tag_names:
            set_item_tags(session, user.id, item.id, tag_names)
    except ValueError as error:
        return _csrf_response(
            request,
            "items/form.html",
            status_code=422,
            user=user,
            action="/items",
            item={"title": title, "type": type, "body": body, "url": url, "tags": tags},
            error=str(error),
        )
    return RedirectResponse(f"/items/{item.id}", status_code=302)


@router.get("/items/{item_id}")
def items_detail(request: Request, item_id: int, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    item = get_item(session, user.id, item_id)
    if item is None:
        return _csrf_response(request, "items/not_found.html", status_code=404, user=user)
    item_tags = get_item_tags(session, user.id, item.id)
    return _csrf_response(
        request, "items/detail.html", user=user, item=item, item_tags=item_tags
    )


@router.post("/items/{item_id}/toggle/{flag}")
def items_toggle(
    request: Request,
    item_id: int,
    flag: str,
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if flag not in FLAG_VALUES:
        return RedirectResponse(f"/items/{item_id}", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return RedirectResponse(f"/items/{item_id}", status_code=302)
    try:
        toggle_flag(session, user.id, item_id, flag)
    except ValueError:
        return _csrf_response(request, "items/not_found.html", status_code=404, user=user)
    return RedirectResponse(f"/items/{item_id}", status_code=302)


@router.post("/items/{item_id}/restore")
def items_restore(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return RedirectResponse(f"/items/{item_id}", status_code=302)
    try:
        restore_item(session, user.id, item_id)
    except ValueError:
        return _csrf_response(request, "items/not_found.html", status_code=404, user=user)
    return RedirectResponse(f"/items/{item_id}", status_code=302)
