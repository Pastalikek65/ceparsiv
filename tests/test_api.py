def _create_token(db_session, user_id, name="test-token"):
    from cepearsiv.services.tokens import create_api_token

    token_model, raw = create_api_token(db_session, user_id, name)
    return raw


def _seed_tag(db_session, user_id, item_id, names):
    from cepearsiv.services.tags import set_item_tags

    set_item_tags(db_session, user_id, item_id, names)


def test_api_no_token_401(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401


def test_api_invalid_token_401(client):
    response = client.get(
        "/api/v1/items", headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_api_crud_with_token(db_session, client):
    from cepearsiv.schemas import ItemCreate
    from cepearsiv.services.items import create_item
    from tests.conftest import make_user

    user = make_user(db_session, username="apiuser")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.post(
        "/api/v1/items",
        json={"type": "note", "title": "API Notu", "body": "govde"},
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "API Notu"
    assert "user_id" not in created
    assert "is_deleted" not in created
    item_id = created["id"]

    response = client.get("/api/v1/items", headers=headers)
    assert response.status_code == 200
    listed = response.json()["items"]
    assert any(i["id"] == item_id for i in listed)

    response = client.get(f"/api/v1/items/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == item_id

    response = client.patch(
        f"/api/v1/items/{item_id}", json={"title": "Yeni Başlık"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Yeni Başlık"

    response = client.delete(f"/api/v1/items/{item_id}", headers=headers)
    assert response.status_code == 200
    response = client.get(f"/api/v1/items/{item_id}", headers=headers)
    assert response.status_code == 404


def test_api_user_isolation_404(db_session, client):
    from tests.conftest import make_user

    user_a = make_user(db_session, username="apia")
    user_b = make_user(db_session, username="apib")
    token_a = _create_token(db_session, user_a.id, name="tok-a")
    token_b = _create_token(db_session, user_b.id, name="tok-b")

    response = client.post(
        "/api/v1/items",
        json={"type": "note", "title": "A'nın Notu"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 201
    item_id = response.json()["id"]

    response = client.get(
        f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404


def test_api_validation_422(db_session, client):
    from tests.conftest import make_user

    user = make_user(db_session, username="apival")
    raw = _create_token(db_session, user.id)
    response = client.post(
        "/api/v1/items",
        json={"type": "bookmark"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 422


def test_api_pagination_limit_max_100(db_session, client):
    from tests.conftest import make_user

    user = make_user(db_session, username="apipage")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/api/v1/items?limit=101", headers=headers)
    assert response.status_code == 422
    response = client.get("/api/v1/items?limit=100", headers=headers)
    assert response.status_code == 200


def test_api_deleted_token_401(db_session, client):
    from sqlmodel import select

    from cepearsiv.models import ApiToken
    from tests.conftest import make_user

    user = make_user(db_session, username="apidel")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}
    assert client.get("/api/v1/items", headers=headers).status_code == 200

    row = db_session.exec(select(ApiToken)).first()
    db_session.delete(row)
    db_session.commit()
    assert client.get("/api/v1/items", headers=headers).status_code == 401


def test_api_expired_token_401(db_session, client):
    from datetime import datetime, timedelta, timezone

    from sqlmodel import select

    from cepearsiv.models import ApiToken
    from tests.conftest import make_user

    user = make_user(db_session, username="apiexp")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}
    assert client.get("/api/v1/items", headers=headers).status_code == 200

    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    row = db_session.exec(select(ApiToken)).first()
    row.expires_at = past
    db_session.add(row)
    db_session.commit()
    assert client.get("/api/v1/items", headers=headers).status_code == 401


def test_api_search_endpoint(db_session, client):
    from tests.conftest import make_user

    user = make_user(db_session, username="apisearch")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}
    response = client.post(
        "/api/v1/items",
        json={"type": "note", "title": "Benzersiz Arama Terimi", "body": "detay"},
        headers=headers,
    )
    assert response.status_code == 201

    response = client.get(
        "/api/v1/search?q=benzersiz+arama", headers=headers
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(i["title"] == "Benzersiz Arama Terimi" for i in items)


def test_api_tags_endpoint(db_session, client):
    from cepearsiv.schemas import ItemCreate
    from cepearsiv.services.items import create_item
    from tests.conftest import make_user

    user = make_user(db_session, username="apitag")
    raw = _create_token(db_session, user.id)
    headers = {"Authorization": f"Bearer {raw}"}
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Etiketli"))
    _seed_tag(db_session, user.id, item.id, ["python"])

    response = client.get("/api/v1/tags", headers=headers)
    assert response.status_code == 200
    tags = response.json()["tags"]
    assert {"name": "python", "count": 1} in tags
