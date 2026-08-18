import pytest
from pydantic import ValidationError

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import (
    create_item,
    get_item,
    list_items,
    restore_item,
    toggle_flag,
)
from tests.conftest import get_csrf, login_client, make_user


def _user_a(db_session):
    return make_user(db_session, username="alice")


def _user_b(db_session):
    return make_user(db_session, username="bob")


def test_create_note(db_session):
    user = _user_a(db_session)
    item = create_item(
        db_session, user.id, ItemCreate(type="note", title="Test Not", body="İçerik")
    )
    assert item.id is not None
    assert item.slug == "test-not"
    assert item.type == "note"
    assert item.is_deleted is False
    assert item.is_archived is False
    assert item.is_favorite is False


def test_create_bookmark_requires_url(db_session):
    user = _user_a(db_session)
    with pytest.raises((ValueError, ValidationError)):
        create_item(
            db_session, user.id, ItemCreate(type="bookmark", title="Link", url=None)
        )


def test_create_snippet(db_session):
    user = _user_a(db_session)
    item = create_item(
        db_session, user.id, ItemCreate(type="snippet", title="Kod", body='print("hi")')
    )
    assert item.id is not None
    assert item.type == "snippet"
    assert item.body == 'print("hi")'


def test_duplicate_slug_gets_suffix(db_session):
    user = _user_a(db_session)
    first = create_item(db_session, user.id, ItemCreate(type="note", title="Test Not"))
    second = create_item(db_session, user.id, ItemCreate(type="note", title="Test Not"))
    assert first.slug == "test-not"
    assert second.slug == "test-not-2"


def test_soft_delete_sets_flag(db_session):
    user = _user_a(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Silinecek"))
    deleted = toggle_flag(db_session, user.id, item.id, flag="deleted")
    assert deleted.is_deleted is True
    restored = restore_item(db_session, user.id, item.id)
    assert restored.is_deleted is False


def test_user_isolation(db_session):
    user_a = _user_a(db_session)
    user_b = _user_b(db_session)
    item = create_item(db_session, user_a.id, ItemCreate(type="note", title="Gizli Not"))
    b_items, _ = list_items(db_session, user_b.id)
    assert all(i.id != item.id for i in b_items)
    assert get_item(db_session, user_b.id, item.id) is None


def test_pagination_with_has_next(db_session):
    user = _user_a(db_session)
    for i in range(41):
        create_item(db_session, user.id, ItemCreate(type="note", title=f"Not {i}"))
    page1, has_next_1 = list_items(db_session, user.id, page=1, page_size=20)
    assert len(page1) == 20
    assert has_next_1 is True
    page3, has_next_3 = list_items(db_session, user.id, page=3, page_size=20)
    assert len(page3) == 1
    assert has_next_3 is False


def test_toggle_favorite_and_archived(db_session):
    user = _user_a(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Bayraklar"))
    fav = toggle_flag(db_session, user.id, item.id, flag="favorite")
    assert fav.is_favorite is True
    arc = toggle_flag(db_session, user.id, item.id, flag="archived")
    assert arc.is_archived is True


def _create_item_via_ui(client, title, csrf):
    response = client.post(
        "/items",
        data={"title": title, "type": "note", "body": "govde", "url": "", "tags": "", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return response.headers["location"].rsplit("/", 1)[-1]


def test_edit_form_renders(client, db_session):
    make_user(db_session, username="duzenleyen", password="Sifre12345")
    login_client(client, "duzenleyen", "Sifre12345")
    csrf = get_csrf(client, "/items/new")
    item_id = _create_item_via_ui(client, "Eski baslik", csrf)
    response = client.get(f"/items/{item_id}/edit")
    assert response.status_code == 200
    assert f'action="/items/{item_id}/edit"' in response.text
    assert 'value="Eski baslik"' in response.text


def test_edit_updates_item(client, db_session):
    make_user(db_session, username="duzenleyen", password="Sifre12345")
    login_client(client, "duzenleyen", "Sifre12345")
    csrf = get_csrf(client, "/items/new")
    item_id = _create_item_via_ui(client, "Eski baslik", csrf)
    csrf = get_csrf(client, f"/items/{item_id}/edit")
    response = client.post(
        f"/items/{item_id}/edit",
        data={"title": "Yeni baslik", "type": "note", "body": "yeni govde", "url": "", "tags": "guncel", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"].endswith(f"/items/{item_id}")
    page = client.get(f"/items/{item_id}")
    assert "Yeni baslik" in page.text
    assert "guncel" in page.text


def test_edit_wrong_csrf_rejected(client, db_session):
    make_user(db_session, username="duzenleyen", password="Sifre12345")
    login_client(client, "duzenleyen", "Sifre12345")
    csrf = get_csrf(client, "/items/new")
    item_id = _create_item_via_ui(client, "Eski baslik", csrf)
    response = client.post(
        f"/items/{item_id}/edit",
        data={"title": "X", "type": "note", "body": "", "url": "", "tags": "", "csrf_token": "yanlis"},
        follow_redirects=False,
    )
    assert response.status_code == 403
