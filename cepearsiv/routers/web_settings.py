import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.models import AuditLog
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.audit import log_audit

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"

VALID_THEMES = ("auto", "dark", "light")


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


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
