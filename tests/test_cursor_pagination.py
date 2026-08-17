import base64
from datetime import datetime

import pytest

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item, decode_cursor, encode_cursor, list_items
from tests.conftest import make_user


def test_cursor_roundtrip():
    moment = datetime(2026, 8, 17, 12, 30, 45, 123456)
    token = encode_cursor(moment, 42)
    assert decode_cursor(token) == (moment, 42)


def test_decode_invalid_cursor_raises():
    with pytest.raises(ValueError):
        decode_cursor("!!!")
    with pytest.raises(ValueError):
        decode_cursor(base64.urlsafe_b64encode(b"|noktasi-yok").decode())


def test_list_items_cursor_walks_pages(db_session):
    user = make_user(db_session, username="cur")
    for i in range(41):
        create_item(db_session, user.id, ItemCreate(type="note", title=f"Imlec {i}"))
    page1, next1 = list_items(db_session, user.id, page_size=20)
    assert len(page1) == 20
    assert next1 is True
    cursor1 = encode_cursor(page1[-1].created_at, page1[-1].id)
    page2, next2 = list_items(db_session, user.id, page_size=20, cursor=cursor1)
    assert len(page2) == 20
    assert next2 is True
    assert not {item.id for item in page1} & {item.id for item in page2}
    cursor2 = encode_cursor(page2[-1].created_at, page2[-1].id)
    page3, next3 = list_items(db_session, user.id, page_size=20, cursor=cursor2)
    assert len(page3) == 1
    assert next3 is False


def test_cursor_wins_over_page(db_session):
    user = make_user(db_session, username="curpage")
    for i in range(30):
        create_item(db_session, user.id, ItemCreate(type="note", title=f"Sayfa {i}"))
    page1, _ = list_items(db_session, user.id, page_size=10)
    cursor = encode_cursor(page1[-1].created_at, page1[-1].id)
    via_cursor, _ = list_items(db_session, user.id, page_size=10, cursor=cursor)
    page_param_ignored, _ = list_items(db_session, user.id, page=3, page_size=10, cursor=cursor)
    assert [item.id for item in via_cursor] == [item.id for item in page_param_ignored]
