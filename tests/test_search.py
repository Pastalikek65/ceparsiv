import sqlite3

import pytest

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item, toggle_flag
from cepearsiv.services.search import build_fts_query, search_items
from tests.conftest import make_user


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

INJECTION_QUERIES = ['"', "*", "NEAR", "OR 1=1", "%", "DROP TABLE items"]


def _seed(db_session, username="searcher"):
    user = make_user(db_session, username=username)
    return user


@requires_fts5
def test_search_two_words_fts5(db_session):
    user = _seed(db_session, username="ftsuser")
    create_item(
        db_session,
        user.id,
        ItemCreate(type="note", title="Python Django", body="Python ile Django web framework"),
    )
    items, _ = search_items(db_session, user.id, q="python django", backend="fts5")
    assert len(items) == 1
    assert items[0].title == "Python Django"


def test_search_two_words_like(db_session):
    user = _seed(db_session, username="likeuser")
    create_item(
        db_session,
        user.id,
        ItemCreate(type="note", title="Python Django", body="Python ile Django web framework"),
    )
    items, _ = search_items(db_session, user.id, q="python django", backend="like")
    assert len(items) == 1
    assert items[0].title == "Python Django"


def test_search_turkish_characters(db_session):
    user = _seed(db_session, username="truser")
    create_item(
        db_session,
        user.id,
        ItemCreate(type="note", title="Çağdaş Türkçe", body="İstanbul Ankara İzmir"),
    )
    items, _ = search_items(db_session, user.id, q="çağdaş türkçe", backend="like")
    assert len(items) == 1


@requires_fts5
@pytest.mark.parametrize("query", INJECTION_QUERIES)
def test_search_injection_attempts_fts5(db_session, query):
    user = _seed(db_session, username="injf")
    create_item(db_session, user.id, ItemCreate(type="note", title="Normal Not", body="icerik"))
    items, _ = search_items(db_session, user.id, q=query, backend="fts5")
    assert isinstance(items, list)


@pytest.mark.parametrize("query", INJECTION_QUERIES)
def test_search_injection_attempts_like(db_session, query):
    user = _seed(db_session, username="injl")
    create_item(db_session, user.id, ItemCreate(type="note", title="Normal Not", body="icerik"))
    items, _ = search_items(db_session, user.id, q=query, backend="like")
    assert isinstance(items, list)


@requires_fts5
def test_search_deleted_excluded_by_default(db_session):
    user = _seed(db_session, username="deluser")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="test notu", body="test"))
    toggle_flag(db_session, user.id, item.id, flag="deleted")
    items, _ = search_items(db_session, user.id, q="test", backend="fts5", include_deleted=False)
    assert items == []
    items, _ = search_items(db_session, user.id, q="test", backend="fts5", include_deleted=True)
    assert len(items) == 1


@requires_fts5
def test_search_archived_included_by_default(db_session):
    user = _seed(db_session, username="arcuser")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="arsiv testi", body="test"))
    toggle_flag(db_session, user.id, item.id, flag="archived")
    items, _ = search_items(db_session, user.id, q="test", backend="fts5")
    assert len(items) == 1
    items, _ = search_items(db_session, user.id, q="test", backend="fts5", include_archived=False)
    assert items == []


def test_search_empty_query_raises_valueerror(db_session):
    user = _seed(db_session, username="emptyuser")
    create_item(db_session, user.id, ItemCreate(type="note", title="Dolu Not", body="veri"))
    with pytest.raises(ValueError):
        search_items(db_session, user.id, q="", backend="like")
    with pytest.raises(ValueError):
        search_items(db_session, user.id, q="   ", backend="like")


def test_build_fts_query_escapes_operators():
    assert build_fts_query("python django") == '"python" AND "django"'
    assert build_fts_query('"quoted"') == '"quoted"'
    assert build_fts_query("*") == ""
    assert build_fts_query("python AND django") == '"python" AND "AND" AND "django"'
