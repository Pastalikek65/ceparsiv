def test_dark_cookie_sets_data_theme(client):
    client.cookies.set("theme", "dark")
    html = client.get("/").text
    assert 'data-theme="dark"' in html


def test_light_cookie_sets_data_theme(client):
    client.cookies.set("theme", "light")
    html = client.get("/").text
    assert 'data-theme="light"' in html


def test_auto_or_missing_cookie_no_data_theme(client):
    html = client.get("/").text
    assert "data-theme" not in html
    client.cookies.set("theme", "auto")
    html = client.get("/").text
    assert "data-theme" not in html


def test_invalid_cookie_value_ignored(client):
    client.cookies.set("theme", "neon")
    html = client.get("/").text
    assert "data-theme" not in html


def test_toggle_sets_cookie_and_redirects(authenticated_client):
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        "/settings/theme",
        data={"theme": "dark", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "theme=dark" in response.headers.get("set-cookie", "")


def test_toggle_invalid_theme_422(authenticated_client):
    token = authenticated_client.cookies.get("csrf_token")
    response = authenticated_client.post(
        "/settings/theme",
        data={"theme": "neon", "csrf_token": token},
    )
    assert response.status_code == 422


def test_toggle_without_csrf_403(authenticated_client):
    response = authenticated_client.post("/settings/theme", data={"theme": "dark"})
    assert response.status_code == 403


def test_toggle_visible_and_theme_applied_on_login_page(client):
    client.cookies.set("theme", "dark")
    html = client.get("/login").text
    assert 'data-theme="dark"' in html
    assert 'action="/settings/theme"' in html
