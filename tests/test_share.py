from sqlmodel import select

from cepearsiv.models import ShareToken, User
from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item, toggle_flag
from cepearsiv.services.share import get_or_create_share_token
from tests.conftest import login_client, make_user


def _user(db_session, username="testuser"):
    return db_session.exec(select(User).where(User.username == username)).first()


def test_create_share_token(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Paylasilacak"))
    csrf = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/items/{item.id}/share",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    db_session.expire_all()
    row = db_session.exec(select(ShareToken).where(ShareToken.item_id == item.id)).first()
    assert row is not None
    assert row.user_id == user.id


def test_create_share_without_csrf_creates_nothing(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Csrf Yok"))
    response = authenticated_client.post(
        f"/items/{item.id}/share", follow_redirects=False
    )
    assert response.status_code == 302
    row = db_session.exec(select(ShareToken).where(ShareToken.item_id == item.id)).first()
    assert row is None


def test_share_public_access(client, db_session):
    user = make_user(db_session, username="public")
    item = create_item(
        db_session, user.id, ItemCreate(type="note", title="Paylasim Basligi", body="icerik")
    )
    share = get_or_create_share_token(db_session, user.id, item.id)
    response = client.get(f"/share/{share.token}")
    assert response.status_code == 200
    assert "Paylasim Basligi" in response.text


def test_share_invalid_token_404(client):
    assert client.get("/share/invalid_token").status_code == 404


def test_share_deleted_item_404(client, db_session):
    user = make_user(db_session, username="delshare")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Silinecek"))
    share = get_or_create_share_token(db_session, user.id, item.id)
    toggle_flag(db_session, user.id, item.id, flag="deleted")
    assert client.get(f"/share/{share.token}").status_code == 404


def test_share_read_only_page(client, db_session):
    user = make_user(db_session, username="readonly")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Salt Okunur"))
    share = get_or_create_share_token(db_session, user.id, item.id)
    html = client.get(f"/share/{share.token}").text
    assert "/toggle/" not in html
    assert "/share/delete" not in html
    assert "Sil" not in html
    assert "Paylaşım bağlantısı oluştur" not in html


def test_share_second_post_keeps_same_token(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Tek Token"))
    first = get_or_create_share_token(db_session, user.id, item.id)
    csrf = authenticated_client.cookies.get("csrf_token")
    authenticated_client.post(
        f"/items/{item.id}/share", data={"csrf_token": csrf}, follow_redirects=False
    )
    db_session.expire_all()
    rows = list(db_session.exec(select(ShareToken).where(ShareToken.item_id == item.id)).all())
    assert len(rows) == 1
    assert rows[0].token == first.token


def test_detail_page_shows_share_link(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Link Gorunur"))
    share = get_or_create_share_token(db_session, user.id, item.id)
    html = authenticated_client.get(f"/items/{item.id}").text
    assert f"/share/{share.token}" in html


def test_share_delete_token(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Baglanti Silinecek"))
    share = get_or_create_share_token(db_session, user.id, item.id)
    token_value = share.token
    csrf = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/items/{item.id}/share/delete",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert authenticated_client.get(f"/share/{token_value}").status_code == 404
    db_session.expunge_all()
    row = db_session.exec(select(ShareToken).where(ShareToken.item_id == item.id)).first()
    assert row is None


def test_share_delete_without_token_404(authenticated_client, db_session):
    user = _user(db_session)
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Token Yok"))
    csrf = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        f"/items/{item.id}/share/delete",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_share_user_isolation(client, db_session):
    owner = make_user(db_session, username="ownerA")
    make_user(db_session, username="intruderB")
    item = create_item(db_session, owner.id, ItemCreate(type="note", title="A'nin Notu"))
    share = get_or_create_share_token(db_session, owner.id, item.id)
    login_client(client, username="intruderB")
    csrf = client.cookies.get("csrf_token")
    response = client.post(
        f"/items/{item.id}/share/delete",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 404
    assert client.get(f"/share/{share.token}").status_code == 200
