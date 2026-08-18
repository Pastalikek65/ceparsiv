# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CepArsiv'in tüm arayüzünü "Arşiv Kataloğu" kimliğiyle (kâğıt tonları, dizin kartları, mono katalog verisi, damga vurgusu) yeniden kurmak; dashboard, item düzenleme, canlı arama, markdown önizleme, toast'lar ve PWA eklemek.

**Architecture:** Backend yetenekleri (test-first): item edit route (servis `update_item` mevcut), dashboard istatistik servisi, arama sonucu highlight, sunucu-taraflı markdown önizleme endpoint'i, HTMX partial'ları. Frontend: Pico.css yerine `static/css/app.css` token sistemi (light/dark CSS değişkenleri), `base.html` yeniden yazımı, sayfa başına yeniden tasarım. JS: yalnızca vanilla `app.js` + mevcut htmx.

**Tech Stack:** Python 3.12+, FastAPI, SQLModel, Jinja2, htmx (mevcut), vanilla JS, SVG favicon, PWA manifest + service worker. Yeni pip paketi ve yeni JS kütüphanesi YOK.

## Global Constraints

- Test-first: her backend değişikliği önce RED test, sonra GREEN implementasyon.
- Kod yorumu YOK. Türkçe arayüz metinleri Türkçe ASCII (çıktıda sorun çıkmasın diye "dogrulamasi" gibi mevcut sözleşme).
- CSS ham hex yok; yalnızca `:root` ve `[data-theme="dark"]` token bloklarında.
- CDN yok: tüm asset'ler `cepearsiv/static/` altında.
- Mevcut 149 testin tamamı yeşil kalmalı; her görev sonunda tam `pytest -q`.
- venv: `/tmp/opencode/cepvenv/bin/python -m pytest` (çalışma dizini `/root/ceparsiv`).
- Commit kuralı: backend özellikleri ayrı commit, `ui:` önekli tasarım commit'leri; push yalnızca tam süit yeşilken.

---

### Task 1: Item düzenleme route'ları (backend)

**Files:**
- Modify: `cepearsiv/routers/web_items.py` (create route'u model alır)
- Modify: `tests/test_items.py` (edit testleri eklenir)

**Interfaces:**
- Consumes: `update_item(session, user_id, item_id, data) -> Item` (services/items.py:77, mevcut),
  `set_item_tags(session, user_id, item_id, names)` (mevcut), `get_item_tags` (mevcut),
  `ItemCreate(type, title, body, url)` (mevcut, pydantic), `_parse_tag_names` (web_items.py:130),
  `_csrf_response` (web_items.py:43), `fix_form_value` (deps).
- Produces: `GET /items/{item_id}/edit` — form.html'ı `action="/items/{id}/edit"`,
  `item=<Item>`, `item_tags="<virgülle>"` ile render eder; `POST /items/{item_id}/edit` —
  302 → `/items/{item_id}`.

- [ ] **Step 1: RED testleri yaz** (`tests/test_items.py` sonuna ekle):

```python
def test_edit_form_renders(client, make_user, get_csrf):
    user = make_user("duzenleyen", "Sifre12345")
    r = client.get("/login")
    csrf = get_csrf(r.text)
    client.post("/login", data={"username": "duzenleyen", "password": "Sifre12345", "csrf_token": csrf})
    item = make_item(client, user, "Eski baslik", type="note")
    r = client.get(f"/items/{item.id}/edit")
    assert r.status_code == 200
    assert 'action="/items/%d/edit"' % item.id in r.text
    assert 'value="Eski baslik"' in r.text


def test_edit_updates_item(client, make_user, get_csrf):
    user = make_user("duzenleyen", "Sifre12345")
    r = client.get("/login")
    csrf = get_csrf(r.text)
    client.post("/login", data={"username": "duzenleyen", "password": "Sifre12345", "csrf_token": csrf})
    item = make_item(client, user, "Eski baslik", type="note")
    csrf = get_csrf(client.get(f"/items/{item.id}/edit").text)
    r = client.post(
        f"/items/{item.id}/edit",
        data={
            "title": "Yeni baslik", "type": "note", "body": "yeni govde",
            "url": "", "tags": "guncel", "csrf_token": csrf,
        },
    )
    assert r.status_code == 302
    assert r.headers["location"].endswith(f"/items/{item.id}")
    r = client.get(f"/items/{item.id}")
    assert "Yeni baslik" in r.text
    assert "guncel" in r.text


def test_edit_wrong_csrf_rejected(client, make_user, get_csrf):
    user = make_user("duzenleyen", "Sifre12345")
    r = client.get("/login")
    csrf = get_csrf(r.text)
    client.post("/login", data={"username": "duzenleyen", "password": "Sifre12345", "csrf_token": csrf})
    item = make_item(client, user, "Eski baslik", type="note")
    r = client.post(
        f"/items/{item.id}/edit",
        data={"title": "X", "type": "note", "body": "", "url": "", "tags": "", "csrf_token": "yanlis"},
    )
    assert r.status_code == 403
```

Not: `make_item` test yardımcısı yoksa conftest'te `make_user` deseniyle `tests/test_items.py` içindeki mevcut yardımcıyı kullan (dosyada nasıl item üretildiğine bak: POST `/items` üzerinden).

- [ ] **Step 2: RED doğrula** — `pytest tests/test_items.py::test_edit_form_renders -q` → 404/405 hatası beklenir.

- [ ] **Step 3: GREEN implement** (`web_items.py`, `items_create` route'unun hemen sonrasına):

```python
@router.get("/items/{item_id}/edit")
def items_edit_form(
    request: Request, item_id: int, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    item = get_item(session, user.id, item_id)
    if item is None:
        return _csrf_response(request, "items/not_found.html", status_code=404, user=user)
    tags = ", ".join(t.name for t in get_item_tags(session, user.id, item.id))
    return _csrf_response(
        request,
        "items/form.html",
        user=user,
        action=f"/items/{item.id}/edit",
        item={"title": item.title, "type": item.type, "body": item.body, "url": item.url or "", "tags": tags},
        error=None,
    )


@router.post("/items/{item_id}/edit")
def items_edit(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
    title: str = Form(""),
    type: str = Form("note"),
    body: str = Form(""),
    url: str = Form(""),
    tags: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    title = fix_form_value(title)
    body = fix_form_value(body)
    url = fix_form_value(url)
    type = fix_form_value(type)
    tags = fix_form_value(tags)
    if not _csrf_ok(request, csrf_token):
        return _csrf_response(
            request, "items/form.html", status_code=403,
            user=user, action=f"/items/{item_id}/edit",
            item={"title": title, "type": type, "body": body, "url": url, "tags": tags},
            error="CSRF dogrulamasi basarisiz.",
        )
    try:
        data = ItemCreate(type=type, title=title.strip(), body=body, url=url.strip() or None)
    except ValidationError as error:
        message = error.errors()[0].get("msg", "Gecersiz giris.") if error.errors() else "Gecersiz giris."
        return _csrf_response(
            request, "items/form.html", status_code=422,
            user=user, action=f"/items/{item_id}/edit",
            item={"title": title, "type": type, "body": body, "url": url, "tags": tags},
            error=message,
        )
    try:
        item = update_item(session, user.id, item_id, data)
        if tags.strip():
            set_item_tags(session, user.id, item.id, _parse_tag_names(tags))
        log_audit(session, user.id, "item.update", entity_type="item", entity_id=item.id)
    except ValueError as error:
        return _csrf_response(
            request, "items/form.html", status_code=422,
            user=user, action=f"/items/{item_id}/edit",
            item={"title": title, "type": type, "body": body, "url": url, "tags": tags},
            error=str(error),
        )
    return RedirectResponse(f"/items/{item_id}", status_code=302)
```

Gerekli import'lar zaten mevcut: `update_item`, `set_item_tags`, `get_item_tags`, `get_item`, `log_audit` (dosyanın mevcut import'larını kontrol et; `update_item` yoksa `from cepearsiv.services.items import update_item` ekle).

- [ ] **Step 4: GREEN doğrula** — `pytest tests/test_items.py -q` → hepsi yeşil.
- [ ] **Step 5: Tam süit** — `pytest -q` → 149+3 yeşil.
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/routers/web_items.py tests/test_items.py
git commit -m "feat(web): item edit routes"
```

---

### Task 2: Dashboard istatistik servisi + ana sayfa ayrımı

**Files:**
- Create: `cepearsiv/services/dashboard.py`
- Create: `tests/test_dashboard.py`
- Modify: `cepearsiv/app.py` (`/` route'u; get_current_user zaten importlu)

**Interfaces:**
- Produces: `dashboard_stats(session, user_id) -> dict` — `{"total": int, "last7": int, "favorites": int, "tags": int}`.

- [ ] **Step 1: RED test** (`tests/test_dashboard.py`):

```python
def test_dashboard_stats_counts(client, make_user, get_csrf):
    user = make_user("dash", "Sifre12345")
    r = client.get("/login")
    csrf = get_csrf(r.text)
    client.post("/login", data={"username": "dash", "password": "Sifre12345", "csrf_token": csrf})
    for i in range(3):
        csrf = get_csrf(client.get("/items/new").text)
        client.post("/items", data={"title": f"not {i}", "type": "note", "body": "x", "url": "", "tags": "", "csrf_token": csrf})
    csrf = get_csrf(client.get(f"/items/1").text)
    client.post("/items/1/toggle/favorite", data={"csrf_token": csrf})
    from cepearsiv.services.dashboard import dashboard_stats
    from cepearsiv.db import get_engine, get_session_factory
    from sqlmodel import Session as SModel
    engine = get_engine("sqlite:///:memory:")
    with SModel(engine) as s:
        stats = dashboard_stats(s, user.id)
    assert stats["total"] == 3
    assert stats["favorites"] == 1
    assert stats["tags"] == 0
    assert stats["last7"] == 3
```

Not: test, app DB'si yerine kendi SQLite bağlamını açsın — mevcut testlerin DB kurulum desenine uy (conftest'taki fixture'lara bak; `make_user` zaten hangi DB'ye yazıyorsa aynı `engine`/session'ı oradan al).

- [ ] **Step 2: RED doğrula** — `pytest tests/test_dashboard.py -q` → ImportError.
- [ ] **Step 3: GREEN implement** (`cepearsiv/services/dashboard.py`):

```python
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from cepearsiv.models import Item, Tag


def dashboard_stats(session: Session, user_id: int) -> dict:
    total = session.exec(
        select(func.count(Item.id)).where(Item.user_id == user_id, Item.is_deleted == False)
    ).one()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    last7 = session.exec(
        select(func.count(Item.id)).where(
            Item.user_id == user_id, Item.is_deleted == False, Item.created_at >= week_ago
        )
    ).one()
    favorites = session.exec(
        select(func.count(Item.id)).where(
            Item.user_id == user_id, Item.is_deleted == False, Item.is_favorite == True
        )
    ).one()
    tags = session.exec(
        select(func.count(Tag.id)).where(Tag.user_id == user_id)
    ).one()
    return {"total": total, "last7": last7, "favorites": favorites, "tags": tags}
```

Not: mevcut kod `is_deleted == False` yerine `~Item.is_deleted` mi kullanıyor kontrol et; aynı stili kullan.

- [ ] **Step 4: GREEN doğrula** — `pytest tests/test_dashboard.py -q`.
- [ ] **Step 5: Tam süit** — `pytest -q`.
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/services/dashboard.py tests/test_dashboard.py
git commit -m "feat(web): dashboard stats service"
```

---

### Task 3: Markdown önizleme endpoint'i

**Files:**
- Modify: `cepearsiv/routers/web_items.py`
- Modify: `tests/test_markdown.py`

**Interfaces:**
- Produces: `POST /items/preview` — form `body` + CSRF; girişli; dönen HTML parçası
  `templates/partials/markdown_preview.html` ile (`{{ rendered|safe }}`).
  Yetkisiz → 401 JSON değil, boş parça dönsün (HTMX swap'ı bozmasın).

- [ ] **Step 1: RED test** (`tests/test_markdown.py` sonuna):

```python
def test_preview_returns_rendered_markdown(client, make_user, get_csrf):
    user = make_user("prev", "Sifre12345")
    r = client.get("/login")
    csrf = get_csrf(r.text)
    client.post("/login", data={"username": "prev", "password": "Sifre12345", "csrf_token": csrf})
    csrf = get_csrf(client.get("/items/new").text)
    r = client.post("/items/preview", data={"body": "**kalın** ve `kod`", "csrf_token": csrf})
    assert r.status_code == 200
    assert "<strong>kalın</strong>" in r.text
    assert "<code>kod</code>" in r.text
```

- [ ] **Step 2: RED doğrula** → 404.
- [ ] **Step 3: GREEN implement** — `web_items.py`'ye (POST `/items` route'undan ÖNCE — `/items/preview` yoksa `/items/{item_id}` pattern'i onu yakalamasın diye üstte tanımla):

```python
@router.post("/items/preview")
def items_preview(
    request: Request,
    session: Session = Depends(get_session),
    body: str = Form(""),
    csrf_token: str | None = Form(None),
):
    user = get_current_user(request, session)
    if user is None:
        return templates.TemplateResponse(request, "partials/markdown_preview.html", {"rendered": ""})
    if not _csrf_ok(request, csrf_token):
        return templates.TemplateResponse(request, "partials/markdown_preview.html", {"rendered": ""})
    return templates.TemplateResponse(
        request, "partials/markdown_preview.html", {"rendered": render_markdown(fix_form_value(body))}
    )
```

- [ ] **Step 4: GREEN doğrula** — `pytest tests/test_markdown.py -q`.
- [ ] **Step 5: Tam süit** — `pytest -q`.
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/routers/web_items.py tests/test_markdown.py
git commit -m "feat(web): markdown preview endpoint"
```

---

### Task 4: Arama sonucu vurgusu (highlight)

**Files:**
- Modify: `cepearsiv/services/search.py`
- Modify: `cepearsiv/routers/web_search.py`
- Modify: `tests/test_search.py`

**Interfaces:**
- Produces: `build_highlight(body: str, terms: list[str], radius: int = 60) -> str`
  — body'de ilk eşleşen terimin çevresini `radius` kadar keser, `…` ile sarar,
  eşleşmeleri `<mark>...</mark>` yapar. `escape()` sonrası regex ile işaretleme.
  Arama route'u `search_items` çağrısından sonra her item için
  `build_highlight(item.body or "", terms)` ile `highlights` sözlüğü kurar ve
  template'e `highlights` geçirir.

- [ ] **Step 1: RED test** (`tests/test_search.py` sonuna):

```python
def test_build_highlight_wraps_terms():
    from cepearsiv.services.search import build_highlight

    out = build_highlight("kisa icerik", ["kisa"])
    assert "<mark>kisa</mark>" in out

def test_build_highlight_truncates_long_body():
    from cepearsiv.services.search import build_highlight

    body = "a" * 500 + " hedef " + "b" * 500
    out = build_highlight(body, ["hedef"])
    assert "…" in out
    assert len(out) < 180

def test_build_highlight_escapes_html():
    from cepearsiv.services.search import build_highlight

    out = build_highlight("<script>x</script> guvenli", ["guvenli"])
    assert "<script>" not in out
    assert "<mark>guvenli</mark>" in out
```

- [ ] **Step 2: RED doğrula** → ImportError.
- [ ] **Step 3: GREEN implement** (`search.py` sonuna):

```python
import html
import re

from cepearsiv.markdownx import escape  # mevcut escape varsa kullan, yoksa html.escape

def build_highlight(body: str, terms: list[str], radius: int = 60) -> str:
    if not body:
        return ""
    lowered = body.lower()
    first = len(body)
    for term in terms:
        idx = lowered.find(term.lower())
        if idx != -1:
            first = min(first, idx)
    if first == len(body):
        snippet = body[: 2 * radius]
        start, end = 0, len(snippet)
        prefix = ""
        suffix = ""
    else:
        start = max(0, first - radius)
        end = min(len(body), first + radius)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(body) else ""
        snippet = body[start:end]
    text = html.escape(prefix + snippet + suffix)
    pattern = re.compile(
        "(" + "|".join(re.escape(html.escape(t)) for t in terms if t.strip()) + ")",
        re.IGNORECASE,
    )
    return pattern.sub(r"<mark>\1</mark>", text)
```

Dikkat: escape sonrası term eşleşmesi için term'leri de escape et. Regex yalnızca boş olmayan terimlerle kurulsun.

- [ ] **Step 4: GREEN doğrula** — `pytest tests/test_search.py -q`.
- [ ] **Step 5: Route'a bağla** — `web_search.py`'de `search_items` dönüşünden sonra:

```python
terms = [t for t in q.strip().split() if t.strip()]
highlights = {item.id: build_highlight(item.body or "", terms) for item in items}
```

template çağrısına `highlights=highlights` ekle. (Template kullanımı Task 12'de.)

- [ ] **Step 6: Tam süit** — `pytest -q`.
- [ ] **Step 7: Commit**

```bash
git add cepearsiv/services/search.py cepearsiv/routers/web_search.py tests/test_search.py
git commit -m "feat(search): highlighted result snippets"
```

---

### Task 5: Tasarım sistemi temeli (fontlar, app.css, base.html, favicon)

**Files:**
- Create: `cepearsiv/static/css/app.css`
- Create: `cepearsiv/static/favicon.svg`
- Create: `cepearsiv/static/fonts/IBMPlexMono-Regular.woff2`, `.../IBMPlexMono-SemiBold.woff2` (indir)
- Modify: `cepearsiv/templates/base.html` (tam yeniden yazım)

- [ ] **Step 1: Fontları indir** (GitHub raw, woff2 — CDN değil, build-time):

```bash
mkdir -p /root/ceparsiv/cepearsiv/static/fonts /root/ceparsiv/cepearsiv/static/css
curl -sL -o /root/ceparsiv/cepearsiv/static/fonts/IBMPlexMono-Regular.woff2 \
  "https://raw.githubusercontent.com/IBM/plex/v6.4.0/packages/plex-mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2"
curl -sL -o /root/ceparsiv/cepearsiv/static/fonts/IBMPlexMono-SemiBold.woff2 \
  "https://raw.githubusercontent.com/IBM/plex/v6.4.0/packages/plex-mono/fonts/complete/woff2/IBMPlexMono-SemiBold.woff2"
ls -la /root/ceparsiv/cepearsiv/static/fonts/
```

- [ ] **Step 2: `static/css/app.css`** — token sistemi (spec'teki palet; ham hex yalnızca burada):

```css
:root {
  --bg: #F6F1E7; --card: #FFFDF6; --ink: #20272E; --muted: #5C666F;
  --line: #E3DAC6; --accent: #B85C38; --accent-2: #1E3A5F;
  --ok: #3E7A4E; --err: #B03030;
  --radius: 10px; --shadow: 0 1px 3px rgba(32, 39, 46, .08);
  --mono: "IBM Plex Mono", ui-monospace, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
[data-theme="dark"] {
  --bg: #161A1E; --card: #1F252B; --ink: #E7E2D6; --muted: #9AA3AC;
  --line: #2D343B; --accent: #C96A4A; --accent-2: #7FA3C9;
  --ok: #7FB98B; --err: #E07A6A;
  --shadow: 0 1px 3px rgba(0, 0, 0, .4);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* koyu auto */ }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--sans); line-height: 1.55; font-size: 1rem;
}
```

Devamında (aynı dosya): `a` (accent-2, altı çizili hover), `.container` (max-width 960px, padding), `.topbar` (sticky, blur), `.btn` + varyantlar (`--accent` dolu, `outline`, `ghost`, `danger`), `.card` (dizin kartı: bg card, border line, radius, shadow, hover'da hafif yükselme), `.cat-num` (mono, muted, küçük), `.stamp` (mono, accent border, küçük büyük harf, letter-spacing), `.tag-pill`, `.row`/`.grid-2` (≥720px media query), `.stat` (mono rakam + etiket), `.form-control` (input/select/textarea ortak stil, focus'da accent-2 ring), `.markdown-body` (h1-h4, p, ul/ol, blockquote, code: koyu arkaplan; pre: `#1E242A` zemin, `#E7E2D6` metin, radius, taşma kaydırma), table çizgili, `.toast` (fixed, alt-orta), `.empty` (kesikli çerçeve, merkez), `.stamp-in` animasyonu (scale .96→1 + opacity, 200ms ease-out; `@media (prefers-reduced-motion: reduce)` altında `animation: none`), `.md-body` kısaltma (eski template'lerdeki `md-body` class'ı için alias), `.mark` rengi (`<mark>`: accent arka planı açık).

- [ ] **Step 3: `static/favicon.svg`** — 64×64, kiremit zemin, beyaz "C" mono (elle yaz).

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#B85C38"/><text x="32" y="44" font-family="monospace" font-size="34" font-weight="bold" fill="#FFFDF6" text-anchor="middle">C</text></svg>
```

- [ ] **Step 4: `base.html` tam yeniden yazım** — yapı:

```
<!doctype html> <html lang="tr" data-theme="{% tema cookie %}">
head: charset, viewport (viewport-fit=cover), title blok, favicon.svg,
  manifest link, apple-touch-icon, theme-color meta,
  <link rel="stylesheet" href="/static/css/app.css">,
  preload: fontları
body:
  {% if user %} topbar: wordmark(CepArsiv, mono vurgulu) · arama formu (/search,
    input#topsearch, "/" kısayolu) · + Yeni (/items/new) · tema düğmesi
    (POST /settings/theme, JS ile auto/light/dark döngüsü) · kullanıcı adı + Çıkış
  {% else %} basit üst bar (wordmark, Giriş/Kayıt)
  {% endif %}
  <main class="container"> {% block content %} {% endblock %} </main>
  toast kutusu: <div id="toast" hx-swap-oob="true"></div>
  script: htmx.min.js, app.js (defer)
{% block scripts %}{% endblock %}
```

Tema: `data-theme` cookie'den (`auto`/`light`/`dark`); `auto` ise `<meta name="color-scheme">` ve JS'te matchMedia ile çözülür. Tema düğmesi artık üç ayrı form yerine TEK buton + JS döngüsü (POST `/settings/theme` — mevcut route `theme` form alanı bekliyor; JS `data-theme` değerini gönderir).

- [ ] **Step 5: Mevcut render'ı doğrula** — `pytest -q` (template içeriği test edilmiyor; hepsi geçmeli). Ayrıca `curl -s http://127.0.0.1:8000/` (sunucu çalışıyorsa) sayfa açılıyor mu bak.
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/static/ cepearsiv/templates/base.html
git commit -m "ui: catalog design system (tokens, fonts, base, favicon)"
```

---

### Task 6: Dashboard ana sayfa

**Files:**
- Modify: `cepearsiv/templates/index.html` (misafir: tanıtım + giriş/kayıt)
- Create: `cepearsiv/templates/dashboard.html`
- Modify: `cepearsiv/app.py` (home route: girişliyse dashboard render)

**Interfaces:**
- Consumes: `dashboard_stats` (Task 2), `list_items(session, user_id, page=1, page_size=5)` (mevcut).
- Produces: girişli `/` → `dashboard.html` (stats, son 5 item, hızlı kayıt formu POST `/items`).

- [ ] **Step 1: app.py home route'u** (mevcut `home` yerine):

```python
@app.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user is None:
        return templates.TemplateResponse(request, "index.html", {"user": None})
    from cepearsiv.services.dashboard import dashboard_stats
    from cepearsiv.services.items import list_items

    stats = dashboard_stats(session, user.id)
    recent, _ = list_items(session, user.id, page=1, page_size=5)
    return templates.TemplateResponse(
        request, "dashboard.html", {"user": user, "stats": stats, "recent": recent}
    )
```

- [ ] **Step 2: `templates/index.html`** (misafir) — temel stillerle: wordmark başlık, 1-2 satır tanıtım, Giriş/Kayıt butonları (`.btn`).
- [ ] **Step 3: `templates/dashboard.html`** — bölümler:
  1. İstatistik şeridi: `.stat` ×4 (Toplam, Son 7 gün, Favori, Etiket — mono rakam).
  2. Hızlı kayıt: tek satır form (başlık input + Tür select + Kaydet); POST `/items`, gizli csrf; başarısızsa normal `/items/new`'e düşer.
  3. Son eklenenler: `partials/item_card.html` include ×5; üstünde "Tümü →" linki.
- [ ] **Step 4: Doğrula** — `pytest -q` + elle `curl -b cookies.txt http://127.0.0.1:8000/` (önceki oturum cookie'si varsa) → istatistikler görünüyor.
- [ ] **Step 5: Commit**

```bash
git add cepearsiv/app.py cepearsiv/templates/index.html cepearsiv/templates/dashboard.html
git commit -m "ui: dashboard home with stats and quick capture"
```

---

### Task 7: Arşiv listesi (dizin kartı grid + HTMX daha fazla)

**Files:**
- Modify: `cepearsiv/templates/items/list.html` (tam yeniden yazım)
- Modify: `cepearsiv/templates/partials/item_card.html` (dizin kartı tasarımı)
- Create: `cepearsiv/templates/partials/card_grid.html` (HTMX swap hedefi)
- Modify: `cepearsiv/routers/web_items.py` (items_list'e `partial` query param desteği)

**Interfaces:**
- Produces: `GET /items?partial=1&cursor=...` → `partials/card_grid.html` (sadece grid, kart animasyonlu); normal GET tam sayfa. Kartlarda: `CA-{id:04d}` mono köşe, tür damgası, başlık, snippet, tarih mono, url, favori/arşiv/çöp mini ikonları, etiket rozetleri (ilk 3, `+N`).

- [ ] **Step 1: Route'a partial desteği** (`items_list` sonunda):

```python
    if request.query_params.get("partial") == "1":
        return _csrf_response(
            request, "partials/card_grid.html",
            user=user, items=items, has_next=has_next, next_query=next_query,
        )
```

(dönüşlerden önce normal render bloğunun üstüne koy.)

- [ ] **Step 2: `item_card.html`** — dizin kartı:

```html
<article class="card stamp-in">
  <div style="display:flex;justify-content:space-between;align-items:baseline;gap:.5rem;">
    <span class="cat-num">CA-{{ "%04d" | format(item.id) }}</span>
    <span class="stamp">{{ item.type }}</span>
  </div>
  <h3 style="margin:.35rem 0 .25rem;"><a href="/items/{{ item.id }}">{{ item.title }}</a></h3>
  {% if item.body %}<p class="snippet">{{ item.body[:120] }}{% if item.body|length > 120 %}…{% endif %}</p>{% endif %}
  {% if item.url %}<p class="snippet"><a href="{{ item.url }}" rel="noopener">{{ item.url[:48] }}</a></p>{% endif %}
  <footer style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-top:.5rem;">
    <small class="muted mono">{{ item.created_at.strftime("%Y-%m-%d") }}</small>
    {% if item.is_favorite %}<span title="Favori">★</span>{% endif %}
    {% if item.is_archived %}<span title="Arşivde">🗄</span>{% endif %}
    {% if item.is_deleted %}<span title="Çöpte">🗑</span>{% endif %}
  </footer>
</article>
```

- [ ] **Step 3: `card_grid.html`** — `<div id="card-grid">` içinde kartlar (tam sayfadaki aynı id'yi kullan) + sayfada "Daha fazla" varsa buton:

```html
<div id="card-grid">
  {% for item in items %}{% include "partials/item_card.html" %}{% endfor %}
</div>
{% if has_next %}
<div style="text-align:center;margin:1rem 0;" hx-get="/items{{ next_query }}&partial=1"
     hx-target="#card-grid" hx-swap="beforeend" hx-trigger="click"
     hx-include="this" class="load-more">
  <button class="btn outline">Daha fazla yükle ↓</button>
</div>
{% endif %}
```

Dikkat: `next_query` `?cursor=...` veya `?type=note&cursor=...` biçiminde; `&partial=1` eklenmesi için route'ta `partial` parametresi "&" ile eklenmiş şekilde üretilmeli (Task 7 Step 1'de `next_query` zaten base_query üretiyor; `partial=1` için sorgu string'ini tek bir noktada kur — `next_query + ("&" if "?" in next_query else "?") + "partial=1"`).

- [ ] **Step 4: `list.html`** — filtre çubuğu (tür select, favori/arşiv/çöp checkbox, `.btn`), grid bölümü (ilk sayfa: tam sayfa render — kartlar `#card-grid` div'inde), yukarıdaki `has_next` bloğu tam sayfada da, boş durum: kesikli `.empty` kutusu + "İlk öğeni oluştur" butonu.
- [ ] **Step 5: Doğrula** — `pytest -q`; elle: `curl -b cookies.txt "http://127.0.0.1:8000/items"` → kart CSS class'ları; `?partial=1&cursor=...` dener.
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/templates/items/list.html cepearsiv/templates/partials/ cepearsiv/routers/web_items.py
git commit -m "ui: archive grid with index cards and htmx load more"
```

---

### Task 8: Item form (editör + canlı önizleme)

**Files:**
- Modify: `cepearsiv/templates/items/form.html` (tam yeniden yazım)
- Create: `cepearsiv/templates/partials/markdown_preview.html`
- Create: `cepearsiv/static/preview.js` (sekme + debounce htmx isteği)

**Interfaces:**
- Consumes: `POST /items/preview` (Task 3). Form `data` attribute: `data-preview-target="#preview-pane"`.

- [ ] **Step 1: `markdown_preview.html`**:

```html
<div id="preview-pane" class="markdown-body">{{ rendered|safe }}</div>
```

- [ ] **Step 2: `form.html`** — üstte sekme çubuğu (Yaz / Önizle — mobil) veya ≥960px yan yana grid; gizli csrf; alanlar: başlık (required, maxlength 200), tür select (not/bookmark/snippet), url (bookmark için required işareti), etiketler (virgülle, `tags` input), içerik textarea (id `body`, `data-preview` attr). Preview div'i ayrı. Hata mesajı `.alert` stilinde. `action`/`item` mevcut context değişkenlerini kullanır (create+edit ortak).
- [ ] **Step 3: `preview.js`** — sayfa içi `data-preview` textarea var olduğunda:

```js
(function () {
  var ta = document.querySelector("textarea[data-preview]");
  var pane = document.querySelector(ta && ta.dataset.previewTarget);
  if (!ta || !pane) return;
  var csrf = document.cookie.match(/csrf_token=([^;]+)/);
  var t;
  function render() {
    if (!csrf) return;
    var fd = new FormData();
    fd.append("body", ta.value);
    fd.append("csrf_token", decodeURIComponent(csrf[1]));
    fetch("/items/preview", { method: "POST", body: fd, headers: { "Accept": "text/html" } })
      .then(function (r) { return r.text(); })
      .then(function (html) { pane.innerHTML = html; });
  }
  ta.addEventListener("input", function () {
    clearTimeout(t);
    t = setTimeout(render, 400);
  });
  render();
})();
```

(preview.js'e "yorum yazma" kuralı unutulmadan.)

- [ ] **Step 4: base.html'e preview.js ekleme** — sadece form sayfasında yüklemek için `{% block scripts %}` içine `<script src="/static/preview.js" defer></script>`; base.html'de blok tanımlı olmalı (Task 5'te ekledin).
- [ ] **Step 5: Doğrula** — `pytest -q`; elle `/items/new` render + `curl -X POST /items/preview` (Task 3'te test edildi).
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/templates/items/form.html cepearsiv/templates/partials/markdown_preview.html cepearsiv/static/preview.js
git commit -m "ui: item form with live markdown preview"
```

---

### Task 9: Item detay sayfası

**Files:**
- Modify: `cepearsiv/templates/items/detail.html` (tam yeniden yazım)

**Interfaces:**
- Consumes: mevcut context: `item`, `item_tags`, `rendered_body`, `share_url`, `csrf_token`, `user`.

- [ ] **Step 1: Detay layout'u** — `grid-2` (≥960px: içerik + yan panel):

```
article.card:
  header: cat-num CA-{id:04d} + stamp (tür) + favori/arşiv/çöp ikonları
  h1 başlık
  meta satırı (mono): oluşturulma / güncelleme tarihi
  url bloğu (bookmark ise açılır link)
  div.markdown-body: rendered_body|safe
  etiket rozetleri
aside (yan panel):
  Eylemler: Düzenle (a.btn → /items/{id}/edit — yeni route!), favori toggle,
    arşivle toggle, paylaşım kutusu (mevcut share form + url kopyala butonu),
    sil (confirm onaylı form: onsubmit="return confirm('Kalıcı silmek üzere çöpe taşınsın mı?')")
    çöpteyse: Geri Al
  (formlar gizli csrf ile, mevcut POST route'larına)
```

- [ ] **Step 2: Paylaşım kutusu** — share_url varsa kopyalama butonu (`app.js`'te `data-copy` handler — Task 13'te eklenecek; burada sadece `data-copy` attribute'u koy).
- [ ] **Step 3: Doğrula** — `pytest -q`; elle detay sayfası render.
- [ ] **Step 4: Commit**

```bash
git add cepearsiv/templates/items/detail.html
git commit -m "ui: item detail with meta panel and edit entry"
```

---

### Task 10: Arama sayfası (canlı + vurgulu)

**Files:**
- Modify: `cepearsiv/templates/search.html` (tam yeniden yazım)
- Modify: `cepearsiv/templates/partials/item_card.html` (opsiyonel: `highlight` desteği)
- Modify: `cepearsiv/routers/web_search.py` (partial desteği + highlights zaten Task 4'te)

**Interfaces:**
- Consumes: `highlights` (Task 4), `GET /search?partial=1`.
- Produces: `partials/search_results.html` — sonuç listesi (kart değil, sıkı liste: vurgulu snippet `<p class="snippet">…<mark>…</mark>…</p>`).

- [ ] **Step 1: Route partial desteği** (web_search.py, sonuç render'ında):

```python
    template = "partials/search_results.html" if request.query_params.get("partial") == "1" else "search.html"
```

- [ ] **Step 2: `search_results.html`** — `<div id="search-results">` + her sonuç: başlık linki, highlight'lı snippet, meta (mono tarih, tür), varsa `has_next` → "Daha fazla" buton bloğu (`hx-get` ile `&partial=1`).
- [ ] **Step 3: `search.html`** — arama kutusu (debounce: `hx-get="/search"` + `hx-trigger="input changed delay:350ms"` + `hx-target="#search-results"` + `hx-include` — q/type/tag input'ları `name` sahibi), filtre çubukları, `#search-results` div'i (ilk render tam sayfa yapar; sonra htmx partial basar), sonuç yoksa `.empty`.
  Dikkat: htmx partial isteği tüm form verisini taşısın (`hx-include="closest form"` veya `hx-select` yöntemi); ilk sayfa yüklemesi normal form POST/GET akışı — tam sayfa + partial ikiliğinde "deleted/archived" checkbox'ları `name`'li olsun.
- [ ] **Step 4: Doğrula** — `pytest -q`; elle `/search?q=merhaba` → `<mark>` görünüyor.
- [ ] **Step 5: Commit**

```bash
git add cepearsiv/templates/search.html cepearsiv/templates/partials/search_results.html cepearsiv/routers/web_search.py
git commit -m "ui: live search with highlighted snippets"
```

---

### Task 11: Etiketler sayfası

**Files:**
- Modify: `cepearsiv/templates/tags/index.html` (tam yeniden yazım)

- [ ] **Step 1: Rozet grid'i** — her etiket: `.tag-pill` (mono, accent-2 çerçeve), ad + sayı (`.cat-num`), tıklayınca `/items?tag=name`. Alt bölümde yönetim tablosu (rename inline form, merge select+buton — mevcut POST route'ları, gizli csrf). Boş durum: kesikli kutu + "İlk etiketi oluştur" (item oluştururken etiket eklenir).
- [ ] **Step 2: Doğrula** — `pytest -q`.
- [ ] **Step 3: Commit**

```bash
git add cepearsiv/templates/tags/index.html
git commit -m "ui: tags page with pill grid and management"
```

---

### Task 12: Ayarlar sayfaları

**Files:**
- Modify: `cepearsiv/templates/settings/2fa_enable.html`, `2fa_setup.html`, `2fa_disable.html`, `2fa_backup.html`
- Modify: `cepearsiv/templates/settings/tokens.html`, `audit.html`
- Modify: `cepearsiv/templates/data/export_import.html`
- Modify: `cepearsiv/templates/auth/account.html`

**Interfaces:** Mevcut context'ler aynı kalır (template değişken adları DEĞİŞMEZ: `user`, `csrf_token`, `error`, `backup_codes`, `tokens`, `audit_logs`, `raw_shown`, `message`, `qr_svg`, `secret`, `otpauth_uri`, `item_tags` vs.).

- [ ] **Step 1: Ortak sekme navigasyonu** — `partials/settings_nav.html`: bağlantı listesi (Ana / 2FA / API Tokenlar / Denetim / Veri) — aktif sayfa param. Tüm settings template'leri include eder.
- [ ] **Step 2: Her sayfayı yeniden stiller** — `.card` içinde; form kontrolleri `.form-control`; token tablosu çizgili `.table`; raw token kutusu `.raw-token` (mono, kesikli çerçeve, `data-copy`); audit tablosu mono tarih; 2FA setup: SVG `{{ qr_svg|safe }}` beyaz kart içinde (koyu temada okunabilir: `filter: invert(1)` değil — kart zeminine sar, `.qr-box`), secret `.raw-token`; backup kodları 2 kolonlu `.codes-grid` (mono).
- [ ] **Step 3: `account.html`** — profil kartı: username, üyelik tarihi (User.created_at — context'e eklenmez, `user.created_at` doğrudan var), 2FA durumu rozeti (otp_enabled ise "2FA açık" yeşil, değilse "2FA kapalı" gri), bağlantılar (ayarlar nav partial'ı).
- [ ] **Step 4: Doğrula** — `pytest -q` (2FA akış testleri template'e bağlı değil ama yine de geçmeli).
- [ ] **Step 5: Commit**

```bash
git add cepearsiv/templates/settings/ cepearsiv/templates/data/ cepearsiv/templates/auth/account.html cepearsiv/templates/partials/settings_nav.html
git commit -m "ui: settings hub with tabs"
```

---

### Task 13: Auth sayfaları + toast + app.js

**Files:**
- Modify: `cepearsiv/templates/auth/login.html`, `register.html`, `2fa.html`, `2fa_setup.html` (varsa), `share/detail.html`, `errors/404.html`, `errors/500.html`
- Create: `cepearsiv/static/app.js`
- Create: `cepearsiv/templates/partials/toast.html` (toast kutusu base'de var; içerik kısmı)

**Interfaces:**
- Consumes: mevcut POST route'ları (tema dahil), `data-copy` attribute'ları.
- Produces: `app.js` küresel: tema döngüsü (auto→light→dark→auto; POST `/settings/theme`), `/` odak arama (`topsearch`), `n` yeni item, `j/k` liste gezinti (`#card-grid` içinde linkli kartlar), `data-copy` tıklama → clipboard + buton metni "Kopyalandı ✓" (2sn), SW kaydı (yalnızca `location.protocol === "https:"` veya localhost), `prefers-reduced-motion` saygısı.

- [ ] **Step 1: `app.js`** — yukarıdaki davranışlar; hepsi bir IIFE içinde, kısayollar yalnızca `user` sayfalarında (body'de `data-user` attr varsa) aktif.
- [ ] **Step 2: Auth template'leri** — `.auth-wrap` (merkez, max-width 400px, min-height 100vh flex), wordmark üstte, `.card` içinde form; hata `.alert`; 2fa.html aynı düzen; register/login arası linkler.
- [ ] **Step 3: `share/detail.html`** — `.card` içinde, markdown-body, üstte küçük "CepArsiv'de paylaşıldı" mono satır; base.html'i extend eder ama topbar GÖSTERMEZ (misafir modda zaten basit üst bar — `user` None olunca otomatik).
- [ ] **Step 4: Hata sayfaları** — 404: kesikli kutu + ana sayfa linki; 500: benzer + debug detayı.
- [ ] **Step 5: Toast** — `web_data._flash_store` desenini kullanarak mesaj basan tüm redirect'lerin hedefi `partials/toast.html` swap'ı: basit yaklaşım — base.html'de `#toast` kutusu; JS `window.addEventListener("htmx:afterRequest")` yerine şimdilik yalnızca `data-copy` geri bildirimi ve hata sayfaları. Flash toast'lar: `web_data` export/import redirect'leri `_flash_store` zaten kullanıyor; template'ler `message` gösteriyor — dashboard/liste sayfalarında `message` varsa `#toast` içine basan küçük JS bloğu app.js'e ekle (`document.currentScript` verisi yerine: `window.__flashMessage` globali — template'lerde `{% if message %}<script>window.__flashMessage = "{{ message|escape }}"</script>{% endif %}`).
- [ ] **Step 6: Doğrula** — `pytest -q`; elle login/register/404 render.
- [ ] **Step 7: Commit**

```bash
git add cepearsiv/static/app.js cepearsiv/templates/auth/ cepearsiv/templates/errors/ cepearsiv/templates/share/ cepearsiv/templates/partials/toast.html
git commit -m "ui: auth pages, global js, toasts"
```

---

### Task 14: PWA (manifest + service worker + ikonlar)

**Files:**
- Create: `cepearsiv/static/manifest.json`
- Create: `cepearsiv/static/sw.js`
- Create: `cepearsiv/static/icons/icon-192.png`, `icon-512.png` (favicon.svg'den üret)
- Modify: `cepearsiv/templates/base.html` (link + SW kaydı zaten app.js'te)

- [ ] **Step 1: İkonlar** — SVG→PNG dönüşümü için sistem aracı: `rsvg-convert` yoksa Python `cairosvg` (pip YOK — kural!) ya da ImageMagick `convert`. Hiçbiri yoksa: 192/512 PNG'yi elle üretemeyiz → alternatif: manifest'te `"icons": [{"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]` (modern tarayıcılar SVG ikon destekler; PWA install yine çalışır) + `apple-touch-icon` için PNG şart değil — `<link rel="apple-touch-icon" href="/static/favicon.svg">` Safari desteklemez ama zararı yok. Önce kontrol:

```bash
which rsvg-convert convert magick 2>/dev/null; echo "---"; python3 -c "import cairosvg" 2>&1 | head -1
```

`convert` varsa: `convert -background none favicon.svg -resize 192x192 icon-192.png` (×512). Yoksa SVG-only manifest kullan (adım adım: iki yolu da yaz; mevcut araca göre uygula).

- [ ] **Step 2: `manifest.json`**:

```json
{
  "name": "CepArsiv",
  "short_name": "CepArsiv",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#161A1E",
  "theme_color": "#161A1E",
  "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"}]
}
```

(ikon PNG üretilemezse `favicon.svg` `sizes: "any"` ile.)

- [ ] **Step 3: `sw.js`** — versiyonlanmış cache: install'da statik precache (`/static/css/app.css`, `/static/app.js`, `/static/preview.js`, `/static/favicon.svg`, `/static/fonts/*.woff2`, manifest, ikonlar); fetch: statik → cache-first, diğer → network-first (fallback cache), `/` ve sayfalar network-first. Activate: eski cache sil. SW kaydı app.js'te (Task 13) zaten; `localhost` veya https'te çalışır.
- [ ] **Step 4: base.html** — `<link rel="manifest" href="/static/manifest.json">`, `<meta name="theme-color" content="#161A1E">`, apple-touch-icon linki.
- [ ] **Step 5: Doğrula** — `curl /static/manifest.json`, `curl /static/sw.js` 200; `pytest -q` (testler SW'e bağlı değil).
- [ ] **Step 6: Commit**

```bash
git add cepearsiv/static/manifest.json cepearsiv/static/sw.js cepearsiv/static/icons/ cepearsiv/templates/base.html
git commit -m "feat(pwa): manifest, service worker, icons"
```

---

### Task 15: Final doğrulama + dokümanlar

**Files:**
- Modify: `docs/ROADMAP.md` (V3 — frontend yeniden tasarım tamamlandı satırı, varsa)
- Modify: `docs/superpowers/plans/2026-08-18-frontend-redesign.md` (bu dosya, durum kontrolü)

- [ ] **Step 1: Tam süit** — `pytest -q` → 152+ test yeşil (149 mevcut + edit 3 + dashboard 1 + preview 1 + highlight 3 = 157).
- [ ] **Step 2: Elle smoke** — sunucuyu başlat (`/tmp/opencode/cepvenv/bin/python -m uvicorn cepearsiv.app:app --port 8000`), `/`, `/login`, `/register`, `/items`, `/items/new`, `/items/1`, `/search?q=test`, `/tags`, `/settings/2fa`, `/settings/tokens`, `/settings/data`, `/settings/audit`, `/share/{token}`, 404 sayfası — hepsi 200 ve CSS class'ları render ediyor (`curl -s -o /dev/null -w "%{http_code}"`).
- [ ] **Step 3: ROADMAP güncelle** — V3 veya "Frontend" satırına "tamamlandı" işareti.
- [ ] **Step 4: Final commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs: mark frontend redesign complete"
git push origin main
```

- [ ] **Step 5: CI kontrolü** — `gh api "repos/Pastalikek65/ceparsiv/actions/runs?per_page=1"` → `completed/success` beklenir.
