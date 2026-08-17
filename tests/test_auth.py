from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from cepearsiv.models import UserSession
from cepearsiv.security import hash_password, verify_password
from cepearsiv.services.auth import authenticate, register
from tests.conftest import PASSWORD, get_csrf, login_client, make_user


def test_password_hash_format():
    stored = hash_password("testpass")
    algorithm, iterations, salt, digest = stored.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert int(iterations) >= 200000
    assert len(bytes.fromhex(salt)) == 16
    assert len(bytes.fromhex(digest)) >= 32

    other = hash_password("testpass")
    assert other.split("$")[2] != salt


def test_verify_wrong_password():
    stored = hash_password("testpass")
    assert verify_password("testpass", stored) is True
    assert verify_password("wrong", stored) is False


def test_register_duplicate_username(db_session):
    register(db_session, "alice", "secret1")
    try:
        register(db_session, "alice", "secret2")
    except Exception as error:
        assert isinstance(error, Exception)
    else:
        raise AssertionError("ayni username ikinci kez kayit olmamali")


def test_login_success_sets_cookie(db_session, client):
    make_user(db_session)
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "testuser", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    cookies = response.headers.get_list("set-cookie")
    assert any("httponly" in c.lower() for c in cookies)
    assert any("samesite=strict" in c.lower() for c in cookies)


def test_logout_clears_session(authenticated_client):
    csrf = get_csrf(authenticated_client, "/account")
    response = authenticated_client.post(
        "/logout", data={"csrf_token": csrf}, follow_redirects=False
    )
    assert response.status_code == 302
    assert authenticated_client.get("/account", follow_redirects=False).status_code == 302


def test_rate_limit_sixth_attempt_429(client):
    csrf = get_csrf(client, "/login")
    for _ in range(5):
        response = client.post(
            "/login",
            data={"username": "rlvictim", "password": "nope", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code != 302
        assert response.status_code != 429
    sixth = client.post(
        "/login",
        data={"username": "rlvictim", "password": "nope", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert sixth.status_code == 429


def test_csrf_missing_returns_403(db_session, client):
    make_user(db_session, username="csrfuser")
    response = client.post(
        "/login",
        data={"username": "csrfuser", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_expired_session_redirects(authenticated_client, db_engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(db_engine) as session:
        row = session.exec(select(UserSession)).first()
        assert row is not None
        row.expires_at = now - timedelta(minutes=1)
        session.add(row)
        session.commit()
    assert authenticated_client.get("/account", follow_redirects=False).status_code == 302


def test_authenticate_success_and_failure(db_session):
    make_user(db_session, username="authuser", password="dogru")
    assert authenticate(db_session, "authuser", "dogru", ip="127.0.0.1").id is not None
    assert authenticate(db_session, "authuser", "yanlis", ip="127.0.0.1") is None
