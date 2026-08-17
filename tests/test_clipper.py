from sqlmodel import select

from cepearsiv.models import Item, User
from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item
from tests.conftest import make_user


def _token(db_session, username):
    from cepearsiv.services.tokens import create_api_token

    user = make_user(db_session, username=username)
    _, raw = create_api_token(db_session, user.id, "clipper-token")
    return user, raw


def test_clipper_no_auth_401(client):
    response = client.post(
        "/api/v1/clipper", json={"url": "https://example.com"}
    )
    assert response.status_code == 401


def test_clipper_create_bookmark(client, db_session):
    user, raw = _token(db_session, "clipper1")
    response = client.post(
        "/api/v1/clipper",
        json={"title": "Example", "url": "https://example.com", "selection": "secim"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "bookmark"
    assert data["title"] == "Example"
    assert data["url"] == "https://example.com"
    assert data["body"] == "secim"


def test_clipper_title_defaults_to_url(client, db_session):
    user, raw = _token(db_session, "clipper2")
    response = client.post(
        "/api/v1/clipper",
        json={"url": "https://basliksiz.example.com/yol"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "https://basliksiz.example.com/yol"


def test_clipper_url_required_422(client, db_session):
    user, raw = _token(db_session, "clipper3")
    response = client.post(
        "/api/v1/clipper",
        json={"title": "Ornek"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 422


def test_clipper_duplicate_url_returns_existing(client, db_session):
    user, raw = _token(db_session, "clipper4")
    first = client.post(
        "/api/v1/clipper",
        json={"title": "Ilk", "url": "https://ornek.example.com"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    second = client.post(
        "/api/v1/clipper",
        json={"title": "Ikinci", "url": "https://ornek.example.com"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_clipper_user_isolation(client, db_session):
    user_a, raw_a = _token(db_session, "clipperA")
    user_b, raw_b = _token(db_session, "clipperB")
    created = client.post(
        "/api/v1/clipper",
        json={"url": "https://ayri.example.com"},
        headers={"Authorization": f"Bearer {raw_a}"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    listed_b = client.get("/api/v1/items", headers={"Authorization": f"Bearer {raw_b}"})
    assert all(row["id"] != item_id for row in listed_b.json()["items"])
    dup_b = client.post(
        "/api/v1/clipper",
        json={"url": "https://ayri.example.com"},
        headers={"Authorization": f"Bearer {raw_b}"},
    )
    assert dup_b.status_code == 201
    assert dup_b.json()["id"] != item_id


def test_clipper_cors_preflight(client):
    response = client.options(
        "/api/v1/clipper",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
    assert "authorization" in response.headers.get("access-control-allow-headers", "").lower()
