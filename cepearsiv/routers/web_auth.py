import hmac
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.config import settings
from cepearsiv.deps import SESSION_COOKIE, fix_form_value, get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.auth import (
    LimitExceeded,
    authenticate,
    create_session,
    delete_session,
    register,
)
from cepearsiv.services.twofactor import verify_login_code

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"
OTP_PENDING_COOKIE = "otp_pending"
OTP_PENDING_TTL_SECONDS = 300

_pending_2fa: dict[str, tuple[int, float]] = {}


def get_pending_2fa_token(request: Request):
    ticket = request.cookies.get(OTP_PENDING_COOKIE)
    if not ticket or ticket not in _pending_2fa:
        return None
    user_id, created = _pending_2fa[ticket]
    if time.monotonic() - created > OTP_PENDING_TTL_SECONDS:
        _pending_2fa.pop(ticket, None)
        return None
    return ticket, user_id


def _set_csrf_cookie(response, token: str):
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _render_csrf_get(request: Request, template: str, **context):
    token = generate_csrf_token()
    context["csrf_token"] = token
    response = templates.TemplateResponse(request, template, context)
    return _set_csrf_cookie(response, token)


def _render_csrf_error(request: Request, template: str, status_code: int, error: str):
    token = request.cookies.get(CSRF_COOKIE) or ""
    return templates.TemplateResponse(
        request, template, {"csrf_token": token, "error": error}, status_code=status_code
    )


@router.get("/register")
def register_get(request: Request):
    return _render_csrf_get(request, "auth/register.html")


@router.post("/register")
def register_post(
    request: Request,
    session: Session = Depends(get_session),
    username: str = Form(""),
    password: str = Form(""),
    csrf_token: str | None = Form(None),
):
    if not _csrf_ok(request, csrf_token):
        return _render_csrf_error(
            request, "auth/register.html", 403, "CSRF dogrulamasi basarisiz."
        )
    try:
        register(session, fix_form_value(username), fix_form_value(password))
    except ValueError:
        return _render_csrf_error(request, "auth/register.html", 409, "Bu kullanici adi alinmis.")
    return RedirectResponse("/login", status_code=302)


@router.get("/login")
def login_get(request: Request):
    return _render_csrf_get(request, "auth/login.html")


@router.post("/login")
def login_post(
    request: Request,
    session: Session = Depends(get_session),
    username: str = Form(""),
    password: str = Form(""),
    csrf_token: str | None = Form(None),
):
    if not _csrf_ok(request, csrf_token):
        return _render_csrf_error(request, "auth/login.html", 403, "CSRF dogrulamasi basarisiz.")
    ip = request.client.host if request.client else ""
    try:
        user = authenticate(
            session, fix_form_value(username), fix_form_value(password), ip=ip
        )
    except LimitExceeded:
        return _render_csrf_error(
            request, "auth/login.html", 429, "Cok fazla deneme. Daha sonra tekrar deneyin."
        )
    if user is None:
        return _render_csrf_error(request, "auth/login.html", 401, "Kullanici adi veya sifre hatali.")
    if user.otp_enabled:
        ticket = secrets.token_urlsafe(32)
        _pending_2fa[ticket] = (user.id, time.monotonic())
        response = RedirectResponse("/login/2fa", status_code=302)
        response.set_cookie(
            OTP_PENDING_COOKIE,
            ticket,
            httponly=True,
            samesite="strict",
            max_age=OTP_PENDING_TTL_SECONDS,
            path="/",
        )
        return response
    token = create_session(session, user.id, ip=ip)
    response = RedirectResponse("/account", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return response


@router.get("/login/2fa")
def login_2fa_get(request: Request):
    pending = get_pending_2fa_token(request)
    if pending is None:
        return RedirectResponse("/login", status_code=302)
    return _render_csrf_get(request, "auth/2fa.html")


@router.post("/login/2fa")
def login_2fa_post(
    request: Request,
    session: Session = Depends(get_session),
    code: str = Form(""),
    csrf_token: str | None = Form(None),
):
    if not _csrf_ok(request, csrf_token):
        return _render_csrf_error(request, "auth/2fa.html", 403, "CSRF dogrulamasi basarisiz.")
    pending = get_pending_2fa_token(request)
    if pending is None:
        return RedirectResponse("/login", status_code=302)
    ticket, user_id = pending
    if not verify_login_code(session, user_id, fix_form_value(code)):
        return _render_csrf_error(
            request, "auth/2fa.html", 401, "Kod hatali veya suresi gecmis."
        )
    _pending_2fa.pop(ticket, None)
    ip = request.client.host if request.client else ""
    token = create_session(session, user_id, ip=ip)
    response = RedirectResponse("/account", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    response.delete_cookie(OTP_PENDING_COOKIE, path="/")
    return response


@router.post("/logout")
def logout_post(
    request: Request,
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    if not _csrf_ok(request, csrf_token):
        return _render_csrf_error(request, "auth/login.html", 403, "CSRF dogrulamasi basarisiz.")
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        delete_session(session, token)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/account")
def account_get(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    token = generate_csrf_token()
    response = templates.TemplateResponse(
        request, "auth/account.html", {"csrf_token": token, "user": user}
    )
    return _set_csrf_cookie(response, token)
