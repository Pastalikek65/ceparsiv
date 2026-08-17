import re

import pytest
from fastapi.testclient import TestClient

PASSWORD = "testpass"


def make_user(session, username="testuser", password=PASSWORD):
    from cepearsiv.models import User
    from cepearsiv.security import hash_password

    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_csrf(client, path="/login"):
    html = client.get(path).text
    match = re.search(r'<input[^>]*name="csrf_token"[^>]*>', html)
    assert match, f"csrf_token input bulunamadi: {path}"
    value = re.search(r'value="([^"]*)"', match.group(0))
    assert value, "csrf_token input value icermiyor"
    return value.group(1)


def login_client(client, username="testuser", password=PASSWORD):
    csrf = get_csrf(client, "/login")
    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    return client


@pytest.fixture()
def db_engine(tmp_path):
    from cepearsiv.db import get_engine, init_schema

    engine = get_engine(f"sqlite:///{tmp_path}/auth.db")
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    from sqlmodel import Session

    with Session(db_engine) as session:
        yield session


@pytest.fixture()
def client(db_engine):
    from cepearsiv.app import app
    from cepearsiv.services.auth import reset_rate_limit_state

    reset_rate_limit_state()
    app.state.engine = db_engine
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def authenticated_client(db_engine, db_session):
    from cepearsiv.app import app
    from cepearsiv.services.auth import reset_rate_limit_state

    reset_rate_limit_state()
    make_user(db_session)
    app.state.engine = db_engine
    with TestClient(app) as test_client:
        login_client(test_client)
        yield test_client
