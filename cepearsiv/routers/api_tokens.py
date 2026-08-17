import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.tokens import create_api_token, delete_api_token, list_api_tokens

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"

_new_token_store: dict[str, str] = {}


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _set_csrf_cookie(response, token: str):
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


def _render(request: Request, session: Session, status_code: int = 200, **context):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    context["csrf_token"] = token
    response = templates.TemplateResponse(
        request, "settings/tokens.html", context, status_code=status_code
    )
    return _set_csrf_cookie(response, token)


@router.get("/settings/tokens")
def tokens_index(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    raw_shown = None
    session_token = request.cookies.get("session_token")
    if session_token and session_token in _new_token_store:
        raw_shown = _new_token_store.pop(session_token)
    return _render(
        request,
        session,
        user=user,
        tokens=list_api_tokens(session, user.id),
        raw_shown=raw_shown,
        error=None,
    )


@router.post("/settings/tokens")
def tokens_create(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _render(
            request,
            session,
            status_code=403,
            user=user,
            tokens=list_api_tokens(session, user.id),
            raw_shown=None,
            error="CSRF dogrulamasi basarisiz.",
        )
    if not name.strip():
        return _render(
            request,
            session,
            user=user,
            tokens=list_api_tokens(session, user.id),
            raw_shown=None,
            error="Token adi bos olamaz.",
        )
    _, raw = create_api_token(session, user.id, name.strip())
    session_token = request.cookies.get("session_token")
    if session_token:
        _new_token_store[session_token] = raw
    return RedirectResponse("/settings/tokens", status_code=302)


@router.post("/settings/tokens/{token_id}/delete")
def tokens_delete(
    request: Request,
    token_id: int,
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return RedirectResponse("/settings/tokens", status_code=302)
    delete_api_token(session, user.id, token_id)
    return RedirectResponse("/settings/tokens", status_code=302)
