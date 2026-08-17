from sqlmodel import select

from cepearsiv.models import User
from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item
from cepearsiv.services.tags import get_or_create_tags, set_item_tags, tags_with_counts


def _user_id(db_session):
    user = db_session.exec(select(User).where(User.username == "testuser")).first()
    assert user is not None
    return user.id


def test_rename_route_updates_db(authenticated_client, db_session):
    uid = _user_id(db_session)
    (tag,) = get_or_create_tags(db_session, uid, ["django"])
    item = create_item(db_session, uid, ItemCreate(type="note", title="Yeniden Ad"))
    set_item_tags(db_session, uid, item.id, ["django"])
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/tags/{tag.id}/rename",
        data={"name": "flask", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    db_session.expire_all()
    names = [t.name for t, _ in tags_with_counts(db_session, uid)]
    assert "flask" in names
    assert "django" not in names


def test_rename_route_conflict_422(authenticated_client, db_session):
    uid = _user_id(db_session)
    get_or_create_tags(db_session, uid, ["python", "py"])
    (tag,) = get_or_create_tags(db_session, uid, ["PYTHON"])
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/tags/{tag.id}/rename",
        data={"name": "py", "csrf_token": token},
    )
    assert response.status_code == 422
    names = [t.name for t, _ in tags_with_counts(db_session, uid)]
    assert "PYTHON" in names or "python" in names


def test_rename_missing_tag_404(authenticated_client, db_session):
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        "/tags/99999/rename",
        data={"name": "hayalet", "csrf_token": token},
    )
    assert response.status_code == 404


def test_rename_without_csrf_403(authenticated_client, db_session):
    uid = _user_id(db_session)
    (tag,) = get_or_create_tags(db_session, uid, ["django"])
    response = authenticated_client.post(
        f"/tags/{tag.id}/rename", data={"name": "flask"}
    )
    assert response.status_code == 403


def test_merge_route_moves_links_and_deletes_source(authenticated_client, db_session):
    uid = _user_id(db_session)
    (src,) = get_or_create_tags(db_session, uid, ["django"])
    (dst,) = get_or_create_tags(db_session, uid, ["python"])
    i1 = create_item(db_session, uid, ItemCreate(type="note", title="Merge Bir"))
    i2 = create_item(db_session, uid, ItemCreate(type="note", title="Merge Iki"))
    set_item_tags(db_session, uid, i1.id, ["django"])
    set_item_tags(db_session, uid, i2.id, ["django", "python"])
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/tags/{src.id}/merge",
        data={"target_id": dst.id, "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    db_session.expire_all()
    counts = {t.name: c for t, c in tags_with_counts(db_session, uid)}
    assert counts == {"python": 2}


def test_merge_self_422(authenticated_client, db_session):
    uid = _user_id(db_session)
    (tag,) = get_or_create_tags(db_session, uid, ["python"])
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/tags/{tag.id}/merge",
        data={"target_id": tag.id, "csrf_token": token},
    )
    assert response.status_code == 422


def test_merge_without_csrf_403(authenticated_client, db_session):
    uid = _user_id(db_session)
    (src,) = get_or_create_tags(db_session, uid, ["django"])
    (dst,) = get_or_create_tags(db_session, uid, ["python"])
    response = authenticated_client.post(
        f"/tags/{src.id}/merge", data={"target_id": dst.id}
    )
    assert response.status_code == 403
