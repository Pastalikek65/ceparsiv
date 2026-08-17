import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.tags import merge_tags, rename_tag, tags_with_counts

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _error_response(request, session, user, status_code: int, error: str):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    rows = tags_with_counts(session, user.id)
    return templates.TemplateResponse(
        request,
        "tags/index.html",
        {"user": user, "tags": rows, "csrf_token": token, "error": error},
        status_code=status_code,
    )


@router.get("/tags")
def tags_index(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    rows = tags_with_counts(session, user.id)
    response = templates.TemplateResponse(
        request, "tags/index.html", {"user": user, "tags": rows, "csrf_token": token}
    )
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


@router.post("/tags/{tag_id}/rename")
def rename_tag_post(
    request: Request,
    tag_id: int,
    session: Session = Depends(get_session),
    name: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _error_response(request, session, user, 403, "csrf dogrulamasi basarisiz")
    try:
        rename_tag(session, user.id, tag_id, name)
    except ValueError as error:
        status = 422 if "zaten var" in str(error) else 404
        return _error_response(request, session, user, status, str(error))
    return RedirectResponse("/tags", status_code=302)


@router.post("/tags/{tag_id}/merge")
def merge_tag_post(
    request: Request,
    tag_id: int,
    session: Session = Depends(get_session),
    target_id: int = Form(0),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _error_response(request, session, user, 403, "csrf dogrulamasi basarisiz")
    try:
        merge_tags(session, user.id, tag_id, target_id)
    except ValueError as error:
        status = 422 if "ayni olamaz" in str(error) else 404
        return _error_response(request, session, user, status, str(error))
    return RedirectResponse("/tags", status_code=302)
