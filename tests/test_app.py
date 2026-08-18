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


def _seed_items(client, count):
    import re

    html = client.get("/items/new").text
    for i in range(count):
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        response = client.post(
            "/items",
            data={"title": f"Web Imlec {i}", "type": "note", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 302, response.text


def test_web_items_next_query_uses_cursor(authenticated_client):
    _seed_items(authenticated_client, 25)
    html = authenticated_client.get("/items").text
    assert "cursor=" in html
    assert "Önceki" not in html


def test_web_cursor_follows_next_page(authenticated_client):
    import re

    _seed_items(authenticated_client, 25)
    html = authenticated_client.get("/items").text
    match = re.search(r'hx-get="/items\?([^"]*cursor=[^"]*)"', html)
    assert match
    page2_html = authenticated_client.get(f"/items?{match.group(1)}").text
    assert "cursor=" not in page2_html or "Daha fazla" not in page2_html
