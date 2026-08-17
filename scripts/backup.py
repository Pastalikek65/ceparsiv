import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _resolve_db_path() -> Path:
    import os

    url = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    if not url.startswith("sqlite:///"):
        raise SystemExit(f"desteklenmeyen DATABASE_URL: {url}")
    path = url[len("sqlite:///"):]
    if path.startswith("/"):
        return Path(path)
    return ROOT / path


def main() -> int:
    source = _resolve_db_path()
    if not source.exists():
        print(f"veritabani dosyasi bulunamadi: {source}", file=sys.stderr)
        return 1
    target_dir = ROOT / "data" / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"cepearsiv-{stamp}.db"
    src_conn = sqlite3.connect(str(source))
    try:
        dst_conn = sqlite3.connect(str(target))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    print(f"yedek olusturuldu: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
