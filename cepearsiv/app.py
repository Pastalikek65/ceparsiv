from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from cepearsiv.config import settings
from cepearsiv.deps import get_current_user, get_session
from cepearsiv.routers import (
    api_tokens,
    api_v1,
    web_auth,
    web_data,
    web_items,
    web_search,
    web_settings,
    web_share,
    web_tags,
)

BASE_DIR = Path(__file__).resolve().parent


def _resolve_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    path = url[len("sqlite:///"):]
    if path.startswith("/") or path == ":memory:":
        return url
    return f"sqlite:///{(BASE_DIR.parent / path).resolve()}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    owns_engine = False
    if getattr(app.state, "engine", None) is None:
        from cepearsiv.db import get_engine, init_schema

        database_url = _resolve_url(settings.database_url)
        if database_url.startswith("sqlite:///"):
            db_path = database_url[len("sqlite:///"):]
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        app.state.engine = get_engine(database_url)
        init_schema(app.state.engine)
        owns_engine = True
    try:
        yield
    finally:
        if owns_engine:
            app.state.engine.dispose()


app = FastAPI(title="CepArsiv", debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static"), check_dir=False), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.include_router(web_auth.router)
app.include_router(web_items.router)
app.include_router(web_search.router)
app.include_router(web_tags.router)
app.include_router(web_data.router)
app.include_router(web_share.router)
app.include_router(web_settings.router)
app.include_router(api_v1.router, prefix="/api/v1")
app.include_router(api_tokens.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    return templates.TemplateResponse(request, "index.html", {"user": user})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc.detail)}
        )
    if exc.status_code in (404, 500):
        template_name = "errors/404.html" if exc.status_code == 404 else "errors/500.html"
        return templates.TemplateResponse(
            request,
            template_name,
            {"debug": settings.debug, "detail": str(exc.detail) if settings.debug else ""},
            status_code=exc.status_code,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"detail": "sunucu hatasi"})
    return templates.TemplateResponse(
        request,
        "errors/500.html",
        {"debug": settings.debug, "detail": repr(exc) if settings.debug else ""},
        status_code=500,
    )
