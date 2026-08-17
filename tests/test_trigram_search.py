import sqlite3

import pytest

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item
from cepearsiv.services.search import detect_backend, search_items
from tests.conftest import make_user


def _trigram_supported() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE probe USING fts5(x, tokenize='trigram case_sensitive 0')"
        )
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


requires_trigram = pytest.mark.skipif(
    not _trigram_supported(), reason="sqlite trigram tokenizer yok"
)


@requires_trigram
def test_detect_backend_trigram(db_session):
    assert detect_backend(db_session) == "trigram"


@requires_trigram
def test_substring_search_matches(db_session):
    user = make_user(db_session, username="tg1")
    create_item(db_session, user.id, ItemCreate(type="note", title="Çağdaş Uygulama", body="govde"))
    items, _ = search_items(db_session, user.id, q="ağda", backend="trigram")
    assert [item.title for item in items] == ["Çağdaş Uygulama"]


@requires_trigram
def test_case_insensitive_substring(db_session):
    user = make_user(db_session, username="tg2")
    create_item(db_session, user.id, ItemCreate(type="note", title="ÇAĞDAŞ BÜYÜK", body="baska"))
    items, _ = search_items(db_session, user.id, q="çağda", backend="trigram")
    assert len(items) == 1


@requires_trigram
def test_two_char_query_falls_back_to_like(db_session):
    user = make_user(db_session, username="tg3")
    create_item(db_session, user.id, ItemCreate(type="note", title="Çağdaş Uygulama", body="govde"))
    items, _ = search_items(db_session, user.id, q="ağ", backend="trigram")
    assert len(items) == 1


@requires_trigram
def test_trigram_query_builds_safe_phrase():
    from cepearsiv.services.search import build_fts_query

    assert build_fts_query("ağda") == '"ağda"'
    assert build_fts_query("çağdaş uygulama") == '"çağdaş" AND "uygulama"'
