from fastapi.testclient import TestClient

from cepearsiv.app import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_renders_base_template():
    response = client.get("/")
    assert response.status_code == 200
    assert "CepArsiv" in response.text
