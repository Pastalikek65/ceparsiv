import hmac
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.audit import log_audit
from cepearsiv.services.dataport import MAX_IMPORT_BYTES, export_user_data, import_user_data

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"

_flash_store: dict[str, str] = {}


def _csrf_ok(request: Request, form_value: str | None) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE)
    if not form_value or not cookie_value:
        return False
    return hmac.compare_digest(form_value, cookie_value)


def _render(request: Request, status_code: int = 200, **context):
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    context["csrf_token"] = token
    session_cookie = request.cookies.get("session_token")
    if session_cookie and session_cookie in _flash_store:
        context["message"] = _flash_store.pop(session_cookie)
    else:
        context.setdefault("message", None)
    response = templates.TemplateResponse(
        request, "data/export_import.html", context, status_code=status_code
    )
    response.set_cookie(CSRF_COOKIE, token, samesite="strict", path="/")
    return response


@router.get("/settings/data")
def data_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return _render(request, user=user, error=None)


@router.post("/settings/data/export")
def data_export(
    request: Request,
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _render(request, status_code=403, user=user, error="CSRF dogrulamasi basarisiz.")
    data = export_user_data(session, user.id)
    log_audit(session, user.id, "data.export", ip=_client_ip(request))
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="cepearsiv-export-{stamp}.json"'},
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post("/settings/data/import")
async def data_import(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not _csrf_ok(request, csrf_token):
        return _render(request, status_code=403, user=user, error="CSRF dogrulamasi basarisiz.")
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        return _render(request, status_code=413, user=user, error="Dosya cok buyuk (en fazla 10 MB).")
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _render(request, status_code=422, user=user, error="Gecerli bir JSON dosyasi degil.")
    try:
        count = import_user_data(session, user.id, data)
    except ValueError as error:
        return _render(request, status_code=422, user=user, error=str(error))
    log_audit(
        session, user.id, "data.import", detail=f"{count} item", ip=_client_ip(request)
    )
    session_cookie = request.cookies.get("session_token")
    if session_cookie:
        _flash_store[session_cookie] = f"{count} item import edildi."
    return RedirectResponse("/settings/data", status_code=302)
