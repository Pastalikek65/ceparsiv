import hmac
from pathlib import Path

import pyotp
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from cepearsiv.deps import fix_form_value, get_current_user, get_session
from cepearsiv.models import AuditLog
from cepearsiv.security import generate_csrf_token, verify_password
from cepearsiv.services.audit import log_audit
from cepearsiv.services.twofactor import (
    clear_backup_codes,
    generate_backup_codes,
    provisioning_svg,
    verify_backup_code,
    verify_totp,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"
BACKUP_COOKIE = "backup_codes"

VALID_THEMES = ("auto", "dark", "light")


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _login_form(request: Request, user, status_code: int = 200, error: str | None = None):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    response = templates.TemplateResponse(
        request,
        "settings/2fa_enable.html",
        {"user": user, "csrf_token": token, "error": error},
        status_code=status_code,
    )
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


@router.post("/settings/theme")
def set_theme(
    request: Request,
    session: Session = Depends(get_session),
    theme: str = Form(""),
    csrf_token: str | None = Form(None),
):
    if not _csrf_ok(request, csrf_token):
        return HTMLResponse(status_code=403, content="<h1>403</h1><p>CSRF dogrulamasi basarisiz.</p>")
    if theme not in VALID_THEMES:
        return HTMLResponse(status_code=422, content="<h1>422</h1><p>Gecersiz tema degeri.</p>")
    user = get_current_user(request, session)
    log_audit(
        session,
        user.id if user else None,
        "settings.theme",
        detail=theme,
        ip=request.client.host if request.client else None,
    )
    referer = request.headers.get("referer") or "/"
    response = RedirectResponse(referer, status_code=302)
    if theme == "auto":
        response.delete_cookie("theme", path="/")
    else:
        response.set_cookie("theme", theme, samesite="strict", path="/", max_age=365 * 24 * 3600)
    return response


@router.get("/settings/audit")
def audit_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    rows = session.exec(
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(100)
    ).all()
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    response = templates.TemplateResponse(
        request, "settings/audit.html", {"user": user, "audit_logs": rows, "csrf_token": token}
    )
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


def _2fa_form(request: Request, user, template: str, status_code: int = 200, error: str | None = None, **extra):
    csrf = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    response = templates.TemplateResponse(
        request,
        template,
        {"user": user, "csrf_token": csrf, "error": error, **extra},
        status_code=status_code,
    )
    response.set_cookie(CSRF_COOKIE, csrf, samesite="strict", path="/")
    return response


@router.get("/settings/2fa")
def twofa_index(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if user.otp_enabled:
        return _2fa_form(request, user, "settings/2fa_disable.html")
    if user.otp_secret is not None:
        return RedirectResponse("/settings/2fa/setup", status_code=302)
    return _2fa_form(request, user, "settings/2fa_enable.html")


@router.post("/settings/2fa/enable")
def twofa_enable(
    request: Request,
    session: Session = Depends(get_session),
    password: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _2fa_form(request, user, "settings/2fa_enable.html", 403, "CSRF dogrulamasi basarisiz.")
    if not verify_password(fix_form_value(password), user.password_hash):
        return _2fa_form(request, user, "settings/2fa_enable.html", 401, "Sifre hatali.")
    if user.otp_secret is None:
        user.otp_secret = pyotp.random_base32()
        session.add(user)
        session.commit()
    log_audit(session, user.id, "2fa.enable_started")
    return RedirectResponse("/settings/2fa/setup", status_code=302)


@router.get("/settings/2fa/setup")
def twofa_setup(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if user.otp_secret is None or user.otp_enabled:
        return RedirectResponse("/settings/2fa", status_code=302)
    svg = provisioning_svg(user.otp_secret, user.username)
    uri = pyotp.TOTP(user.otp_secret).provisioning_uri(name=user.username, issuer_name="CepArsiv")
    return _2fa_form(
        request,
        user,
        "settings/2fa_setup.html",
        qr_svg=svg,
        otpauth_uri=uri,
        secret=user.otp_secret,
    )


@router.post("/settings/2fa/verify")
def twofa_verify(
    request: Request,
    session: Session = Depends(get_session),
    code: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if user.otp_secret is None or user.otp_enabled:
        return RedirectResponse("/settings/2fa", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _2fa_form(request, user, "settings/2fa_setup.html", 403, "CSRF dogrulamasi basarisiz.")
    if not verify_totp(user.otp_secret, fix_form_value(code)):
        svg = provisioning_svg(user.otp_secret, user.username)
        uri = pyotp.TOTP(user.otp_secret).provisioning_uri(name=user.username, issuer_name="CepArsiv")
        return _2fa_form(
            request,
            user,
            "settings/2fa_setup.html",
            422,
            "Kod hatali. Tekrar deneyin.",
            qr_svg=svg,
            otpauth_uri=uri,
            secret=user.otp_secret,
        )
    user.otp_enabled = True
    session.add(user)
    session.commit()
    plain_codes = generate_backup_codes(session, user.id)
    log_audit(session, user.id, "2fa.enabled")
    response = _2fa_form(request, user, "settings/2fa_backup.html", backup_codes=plain_codes)
    return response


@router.post("/settings/2fa/disable")
def twofa_disable(
    request: Request,
    session: Session = Depends(get_session),
    password: str = Form(""),
    code: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not user.otp_enabled:
        return RedirectResponse("/settings/2fa", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _2fa_form(request, user, "settings/2fa_disable.html", 403, "CSRF dogrulamasi basarisiz.")
    if not verify_password(fix_form_value(password), user.password_hash):
        return _2fa_form(request, user, "settings/2fa_disable.html", 401, "Sifre hatali.")
    raw_code = fix_form_value(code).strip()
    if not verify_totp(user.otp_secret, raw_code) and not verify_backup_code(session, user.id, raw_code):
        return _2fa_form(request, user, "settings/2fa_disable.html", 422, "Kod hatali.")
    user.otp_enabled = False
    user.otp_secret = None
    session.add(user)
    session.commit()
    clear_backup_codes(session, user.id)
    log_audit(session, user.id, "2fa.disabled")
    return RedirectResponse("/settings/2fa", status_code=302)
