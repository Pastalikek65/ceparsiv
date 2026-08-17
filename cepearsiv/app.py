from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cepearsiv.config import settings

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="CepArsiv", debug=settings.debug)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static"), check_dir=False), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")
