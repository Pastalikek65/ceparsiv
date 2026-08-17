from collections.abc import Iterator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

FTS_TABLE_UNICODE61 = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5("
    "title, body, content='items', content_rowid='id', tokenize='unicode61')"
)
FTS_TABLE_TRIGRAM = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5("
    "title, body, content='items', content_rowid='id',"
    " tokenize='trigram case_sensitive 0')"
)
FTS_TABLE_DDL = FTS_TABLE_UNICODE61
TRIGGER_ITEMS_AI = """
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END
"""
TRIGGER_ITEMS_AD = """
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, body)
    VALUES ('delete', old.id, old.title, old.body);
END
"""
TRIGGER_ITEMS_AU = """
CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, body)
    VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO items_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END
"""
FTS_REBUILD = "INSERT INTO items_fts(items_fts) VALUES('rebuild')"


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA cache_size=-2000")
    cursor.close()


def get_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def trigram_supported(conn) -> bool:
    try:
        conn.execute(text("CREATE VIRTUAL TABLE _probe USING fts5(x, tokenize='trigram case_sensitive 0')"))
        conn.execute(text("DROP TABLE _probe"))
        return True
    except OperationalError:
        return False


def _fts_table_sql(conn) -> str | None:
    row = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='items_fts'")
    ).first()
    return row[0] if row is not None else None


def _ensure_fts(engine: Engine) -> None:
    try:
        with engine.begin() as conn:
            has_trigram = trigram_supported(conn)
            existing = _fts_table_sql(conn)
            if existing is not None:
                if has_trigram and "trigram" not in existing:
                    conn.execute(text("DROP TABLE items_fts"))
                    conn.execute(text(FTS_TABLE_TRIGRAM))
                elif not has_trigram and "unicode61" not in existing:
                    conn.execute(text(FTS_TABLE_UNICODE61))
            else:
                conn.execute(text(FTS_TABLE_TRIGRAM if has_trigram else FTS_TABLE_UNICODE61))
    except OperationalError:
        return
    with engine.begin() as conn:
        conn.execute(text(TRIGGER_ITEMS_AI))
        conn.execute(text(TRIGGER_ITEMS_AD))
        conn.execute(text(TRIGGER_ITEMS_AU))
        conn.execute(text(FTS_REBUILD))


def init_schema(engine: Engine) -> None:
    from cepearsiv import models

    SQLModel.metadata.create_all(engine)
    _ensure_fts(engine)


def get_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
