from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.models import AuditLog
from cepearsiv.security import generate_csrf_token

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"


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
