import re

import pyotp
from sqlmodel import select

from cepearsiv.models import BackupCode, User
from tests.conftest import get_csrf, login_client, make_user

PASSWORD = "testpass"


def _user(db_session, username="testuser"):
    return db_session.exec(select(User).where(User.username == username)).first()


def _csrf(client):
    return client.cookies.get("csrf_token") or get_csrf(client, "/account")


def _enable_otp(client, db_session, username="testuser"):
    user = _user(db_session, username)
    csrf = _csrf(client)
    response = client.post(
        "/settings/2fa/enable",
        data={"password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    db_session.expire_all()
    user = _user(db_session, username)
    assert user.otp_secret is not None
    return user


def test_enable_creates_pending_secret(authenticated_client, db_session):
    user = _enable_otp(authenticated_client, db_session)
    assert user.otp_enabled is False
    setup_page = authenticated_client.get("/settings/2fa/setup")
    assert setup_page.status_code == 200
    assert user.otp_secret in setup_page.text
    assert "otpauth://totp/" in setup_page.text
    assert "<svg" in setup_page.text


def test_enable_requires_password(authenticated_client, db_session):
    csrf = _csrf(authenticated_client)
    response = authenticated_client.post(
        "/settings/2fa/enable",
        data={"password": "yanlissifre", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code in (401, 403, 422)
    user = _user(db_session)
    assert user.otp_secret is None


def test_verify_code_enables_and_creates_backup_codes(authenticated_client, db_session):
    user = _enable_otp(authenticated_client, db_session)
    code = pyotp.TOTP(user.otp_secret).now()
    csrf = _csrf(authenticated_client)
    response = authenticated_client.post(
        "/settings/2fa/verify",
        data={"code": code, "csrf_token": csrf},
    )
    assert response.status_code == 200
    db_session.expire_all()
    user = _user(db_session)
    assert user.otp_enabled is True
    codes = list(
        db_session.exec(select(BackupCode).where(BackupCode.user_id == user.id)).all()
    )
    assert len(codes) == 10
    assert all(c.used_at is None for c in codes)


def test_verify_wrong_code_stays_disabled(authenticated_client, db_session):
    _enable_otp(authenticated_client, db_session)
    csrf = _csrf(authenticated_client)
    response = authenticated_client.post(
        "/settings/2fa/verify",
        data={"code": "000000", "csrf_token": csrf},
    )
    assert response.status_code in (200, 422)
    user = _user(db_session)
    assert user.otp_enabled is False


def test_login_redirects_to_2fa_and_succeeds(client, db_session):
    user = make_user(db_session, username="twofa")
    user.otp_secret = pyotp.random_base32()
    user.otp_enabled = True
    db_session.add(user)
    db_session.commit()
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "twofa", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login/2fa"
    page = client.get("/login/2fa")
    assert page.status_code == 200
    csrf2 = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    code = pyotp.TOTP(user.otp_secret).now()
    done = client.post(
        "/login/2fa",
        data={"code": code, "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert done.status_code == 302
    assert done.headers["location"] == "/account"
    assert client.get("/account", follow_redirects=False).status_code == 200


def test_login_2fa_wrong_code_rejected(client, db_session):
    user = make_user(db_session, username="twofa2")
    user.otp_secret = pyotp.random_base32()
    user.otp_enabled = True
    db_session.add(user)
    db_session.commit()
    csrf = get_csrf(client, "/login")
    client.post(
        "/login",
        data={"username": "twofa2", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    page = client.get("/login/2fa")
    csrf2 = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post(
        "/login/2fa",
        data={"code": "123456", "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert response.status_code in (401, 422)
    assert client.get("/account", follow_redirects=False).status_code == 302


def test_backup_code_single_use(client, db_session):
    from cepearsiv.services.twofactor import generate_backup_codes

    user = make_user(db_session, username="twofa3")
    user.otp_secret = pyotp.random_base32()
    user.otp_enabled = True
    db_session.add(user)
    db_session.commit()
    plain_codes = generate_backup_codes(db_session, user.id)
    first = plain_codes[0]
    csrf = get_csrf(client, "/login")
    client.post(
        "/login",
        data={"username": "twofa3", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    page = client.get("/login/2fa")
    csrf2 = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    ok = client.post(
        "/login/2fa",
        data={"code": first, "csrf_token": csrf2},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers["location"] == "/account"
    client.post("/logout", data={"csrf_token": client.cookies.get("csrf_token")})
    csrf3 = get_csrf(client, "/login")
    client.post(
        "/login",
        data={"username": "twofa3", "password": PASSWORD, "csrf_token": csrf3},
        follow_redirects=False,
    )
    page2 = client.get("/login/2fa")
    csrf4 = re.search(r'name="csrf_token" value="([^"]+)"', page2.text).group(1)
    again = client.post(
        "/login/2fa",
        data={"code": first, "csrf_token": csrf4},
        follow_redirects=False,
    )
    assert again.status_code in (401, 422)


def test_disable_requires_password_and_code(authenticated_client, db_session):
    user = _enable_otp(authenticated_client, db_session)
    code = pyotp.TOTP(user.otp_secret).now()
    csrf = _csrf(authenticated_client)
    authenticated_client.post(
        "/settings/2fa/verify", data={"code": code, "csrf_token": csrf}
    )
    db_session.expire_all()
    user = _user(db_session)
    assert user.otp_enabled is True
    csrf = _csrf(authenticated_client)
    response = authenticated_client.post(
        "/settings/2fa/disable",
        data={"password": "yanlissifre", "code": "000000", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code in (401, 403, 422)
    fresh_code = pyotp.TOTP(user.otp_secret).now()
    csrf = _csrf(authenticated_client)
    response = authenticated_client.post(
        "/settings/2fa/disable",
        data={"password": PASSWORD, "code": fresh_code, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    db_session.expire_all()
    user = _user(db_session)
    assert user.otp_enabled is False
    assert user.otp_secret is None


def test_login_without_2fa_unchanged(client, db_session):
    make_user(db_session, username="plainuser")
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "plainuser", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/account"


def test_2fa_isolation_between_users(client, db_session):
    user_a = make_user(db_session, username="isoA")
    user_a.otp_secret = pyotp.random_base32()
    user_a.otp_enabled = True
    db_session.add(user_a)
    db_session.commit()
    make_user(db_session, username="isoB")
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": "isoB", "password": PASSWORD, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/account"
