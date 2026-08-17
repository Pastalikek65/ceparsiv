from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cepearsiv.config import settings
from cepearsiv.routers import web_auth, web_items, web_search, web_tags

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
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static"), check_dir=False), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.include_router(web_auth.router)
app.include_router(web_items.router)
app.include_router(web_search.router)
app.include_router(web_tags.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")
