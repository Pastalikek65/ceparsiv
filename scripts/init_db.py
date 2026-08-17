import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cepearsiv.config import Settings
from cepearsiv.db import get_engine, init_schema


def _resolve_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    path = url[len("sqlite:///"):]
    if path.startswith("/") or path == ":memory:":
        return url
    db_path = ROOT / path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def main() -> int:
    settings = Settings()
    database_url = os.getenv("DATABASE_URL", settings.database_url)
    database_url = _resolve_url(database_url)
    engine = get_engine(database_url)
    init_schema(engine)
    engine.dispose()
    print(f"DB hazir: {database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
