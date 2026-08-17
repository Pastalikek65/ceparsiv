import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.markdownx import render_markdown
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.share import delete_share_token, get_or_create_share_token, get_shared_item
from cepearsiv.services.tags import get_item_tags

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _not_found(request: Request):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    return templates.TemplateResponse(
        request, "errors/404.html", {"csrf_token": token}, status_code=404
    )


@router.get("/share/{token}")
def share_detail(request: Request, token: str, session: Session = Depends(get_session)):
    item = get_shared_item(session, token)
    if item is None:
        return _not_found(request)
    item_tags = get_item_tags(session, item.user_id, item.id)
    return templates.TemplateResponse(
        request,
        "share/detail.html",
        {"item": item, "item_tags": item_tags, "rendered_body": render_markdown(item.body)},
    )


@router.post("/items/{item_id}/share")
def share_create(
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
        get_or_create_share_token(session, user.id, item_id)
    except ValueError:
        return _not_found(request)
    return RedirectResponse(f"/items/{item_id}", status_code=302)


@router.post("/items/{item_id}/share/delete")
def share_delete(
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
        deleted = delete_share_token(session, user.id, item_id)
    except ValueError:
        return _not_found(request)
    if not deleted:
        return _not_found(request)
    return RedirectResponse(f"/items/{item_id}", status_code=302)
