from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.tags import tags_with_counts

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"


@router.get("/tags")
def tags_index(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    rows = tags_with_counts(session, user.id)
    return templates.TemplateResponse(
        request,
        "tags/index.html",
        {"user": user, "tags": rows, "csrf_token": token},
    )
