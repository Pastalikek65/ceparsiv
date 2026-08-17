from sqlmodel import select

from cepearsiv.models import AuditLog
from cepearsiv.services.audit import log_audit
from tests.conftest import PASSWORD, get_csrf, make_user


def _audit_rows(db_session, action=None, user_id=None):
    stmt = select(AuditLog)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return list(db_session.exec(stmt).all())


def test_audit_login_success(db_session, client):
    make_user(db_session)
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "testuser", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    rows = _audit_rows(db_session, action="login.success")
    assert len(rows) == 1
    assert rows[0].ip is not None


def test_audit_login_failure(db_session, client):
    make_user(db_session)
    csrf = get_csrf(client, "/login")
    client.post(
        "/login",
        data={"username": "testuser", "password": "yanlis", "csrf_token": csrf},
        follow_redirects=False,
    )
    rows = _audit_rows(db_session, action="login.failure")
    assert len(rows) == 1


def test_audit_item_created(db_session):
    from cepearsiv.schemas import ItemCreate
    from cepearsiv.services.items import create_item

    user = make_user(db_session, username="auditor")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Denetim Notu"))
    rows = _audit_rows(db_session, action="item.created")
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].entity_type == "item"
    assert rows[0].entity_id == item.id


def test_audit_token_created(db_session):
    from cepearsiv.services.tokens import create_api_token

    user = make_user(db_session, username="tokaudit")
    create_api_token(db_session, user.id, "denetim-token")
    rows = _audit_rows(db_session, action="token.created")
    assert len(rows) == 1
    assert rows[0].user_id == user.id


def test_audit_user_isolation(db_engine, db_session, client):
    user_a = make_user(db_session, username="isol_a")
    user_b = make_user(db_session, username="isol_b")
    log_audit(
        db_session, user_a.id, "item.created", entity_type="item", entity_id=1,
        detail="kayit-A-gizli",
    )
    log_audit(
        db_session, user_b.id, "item.created", entity_type="item", entity_id=2,
        detail="kayit-B-gorunur",
    )

    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "isol_b", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302

    page = client.get("/settings/audit")
    assert page.status_code == 200
    assert "kayit-B-gorunur" in page.text
    assert "kayit-A-gizli" not in page.text


def test_audit_page_requires_login(client):
    response = client.get("/settings/audit", follow_redirects=False)
    assert response.status_code == 302
