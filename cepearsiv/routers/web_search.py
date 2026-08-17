from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from cepearsiv.deps import fix_form_value, get_current_user, get_session
from cepearsiv.security import generate_csrf_token
from cepearsiv.services.search import detect_backend, search_items

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

CSRF_COOKIE = "csrf_token"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.casefold() in ("1", "true", "on", "yes")


@router.get("/search")
def search_route(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    params = request.query_params
    q = fix_form_value(params.get("q", "")).strip()
    item_type = params.get("type") or None
    tag = params.get("tag") or None
    include_archived = _parse_bool(params.get("archived"), True)
    include_deleted = params.get("deleted") == "1"
    try:
        page = max(int(params.get("page", "1")), 1)
    except ValueError:
        page = 1
    token = request.cookies.get(CSRF_COOKIE) or generate_csrf_token()
    context = {
        "user": user,
        "csrf_token": token,
        "q": q,
        "items": [],
        "has_next": False,
        "current_page": page,
        "prev_query": None,
        "next_query": None,
        "searched": False,
        "backend": detect_backend(session),
        "filters": {
            "type": item_type or "",
            "tag": tag or "",
            "archived": include_archived,
            "deleted": include_deleted,
        },
    }
    if q:
        items, has_next = search_items(
            session,
            user.id,
            q,
            context["backend"],
            type=item_type,
            tag=tag,
            include_archived=include_archived,
            include_deleted=include_deleted,
            page=page,
        )
        context.update(searched=True, items=items, has_next=has_next)
        parts = [f"q={q}"]
        if item_type:
            parts.append(f"type={item_type}")
        if tag:
            parts.append(f"tag={tag}")
        if not include_archived:
            parts.append("archived=0")
        if include_deleted:
            parts.append("deleted=1")
        base_query = f"?{'&'.join(parts)}&"
        if page > 1:
            context["prev_query"] = f"{base_query}page={page - 1}"
        if has_next:
            context["next_query"] = f"{base_query}page={page + 1}"
    return templates.TemplateResponse(request, "search.html", context)
