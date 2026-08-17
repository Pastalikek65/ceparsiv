import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from cepearsiv.db import get_engine, init_schema
from cepearsiv.models import Item, User

ROOT = Path(__file__).resolve().parents[1]


def _fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE fts_check USING fts5(content)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


requires_fts5 = pytest.mark.skipif(
    not _fts5_available(), reason="sqlite FTS5 desteklenmiyor"
)


@pytest.fixture()
def db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/test.db")
    init_schema(engine)
    with Session(engine) as session:
        yield engine, session
    engine.dispose()


def _make_user(session, username="alice"):
    user = User(username=username, password_hash="pbkdf2_sha256$1$dummy$deadbeef")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _fts_count(session, match: str) -> int:
    result = session.execute(
        text("SELECT COUNT(*) FROM items_fts WHERE items_fts MATCH :q"), {"q": match}
    )
    return int(result.scalar())


def test_pragmas_active(db):
    engine, _ = db
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


@requires_fts5
def test_fts_insert_sync(db):
    _, session = db
    user = _make_user(session)
    session.add(
        Item(
            user_id=user.id,
            type="note",
            title="Arama Notu",
            slug="arama-notu",
            body="termux sqlite full text arama",
        )
    )
    session.commit()
    assert _fts_count(session, "sqlite") == 1


@requires_fts5
def test_fts_delete_sync(db):
    _, session = db
    user = _make_user(session)
    item = Item(
        user_id=user.id,
        type="note",
        title="Silinecek",
        slug="silinecek",
        body="bu icerik fts indeksinden kalkmali",
    )
    session.add(item)
    session.commit()
    assert _fts_count(session, "kalkmali") == 1
    session.delete(item)
    session.commit()
    assert _fts_count(session, "kalkmali") == 0


@requires_fts5
def test_fts_update_sync(db):
    _, session = db
    user = _make_user(session)
    item = Item(
        user_id=user.id,
        type="note",
        title="Guncellenecek",
        slug="guncellenecek",
        body="eski govde icerigi",
    )
    session.add(item)
    session.commit()
    assert _fts_count(session, "eski") == 1
    item.body = "yeni govde icerigi"
    session.add(item)
    session.commit()
    assert _fts_count(session, "yeni") == 1
    assert _fts_count(session, "eski") == 0


def test_unique_slug_violation(db):
    _, session = db
    user = _make_user(session)
    session.add(
        Item(user_id=user.id, type="note", title="B1", slug="ayni-slug", body="bir")
    )
    session.commit()
    session.add(
        Item(user_id=user.id, type="note", title="B2", slug="ayni-slug", body="iki")
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_unique_slug_scoped_to_user(db):
    _, session = db
    u1 = _make_user(session, "alice")
    u2 = _make_user(session, "bob")
    session.add(
        Item(user_id=u1.id, type="note", title="A", slug="ayni-slug", body="a")
    )
    session.add(
        Item(user_id=u2.id, type="note", title="B", slug="ayni-slug", body="b")
    )
    session.commit()


def test_init_db_idempotent(tmp_path):
    db_url = f"sqlite:///{tmp_path}/init.db"
    env = dict(os.environ, DATABASE_URL=db_url)
    script = str(ROOT / "scripts" / "init_db.py")
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, script],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr


def test_check_fts5_script():
    script = str(ROOT / "scripts" / "check_fts5.py")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "FTS5: OK" in result.stdout or "FTS5: YOK" in result.stdout
