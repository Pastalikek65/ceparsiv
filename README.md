# CepArsiv

[![tests](https://github.com/Pastalikek65/ceparsiv/actions/workflows/test.yml/badge.svg)](https://github.com/Pastalikek65/ceparsiv/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Kişisel bilgi arşivi: not, yer imi ve snippet'leri tek bir yerde toplar. Termux'ta proot Ubuntu içinde telefonda çalışacak şekilde yazıldı — düşük kaynak, tek kullanıcı, CDN'siz. FastAPI + SQLModel + SQLite (WAL) + Jinja2 + HTMX.

## Özellikler

- **Üç item tipi** — not, yer imi, snippet
- **Markdown** — detay görünümünde güvenli render (raw HTML passthrough kapalı)
- **Tam metin arama** — SQLite FTS5, desteklenmeyen derlemelerde LIKE fallback
- **Tag, favori, arşiv** — soft delete ile geri alınabilir silme
- **REST API** — Bearer token ile tüm CRUD + arama
- **JSON export / import** — doğrulamalı, slug çakışmalarını otomatik çözer
- **Audit log** — login, item, export/import olayları (`/settings/audit`)
- **Yedekleme** — `scripts/backup.py` ile zaman damgalı SQLite kopyası
- **CDN'siz statikler** — pico.css ve htmx.js repo içinde, çevrimdışı çalışır

Ekran görüntüleri ileride eklenecek.

## Proje yapısı

```
cepearsiv/
  app.py              uygulama girişi, hata handler'ları
  config.py           env tabanlı ayarlar
  db.py               engine + PRAGMA'lar + FTS5 init
  schemas.py          pydantic model'ler
  routers/            web (Jinja2) + api router'ları
  services/           auth, items, tags, search, tokens, audit, dataport
  templates/          Jinja2 (items, settings, errors)
  static/             pico.min.css, htmx.min.js
scripts/
  init_db.py          şema + FTS5 init
  backup.py           data/backups/ altına kopya
  check_fts5.py       FTS5 desteğini raporlar
docs/
  API.md              REST API referansı
  SECURITY.md         güvenlik modelinin özeti
  PERFORMANCE.md      veritabanı ve sunucu kararları
  ROADMAP.md          MVP/V1/V2
```

## Kurulum (Termux / proot Ubuntu)

```bash
pkg install python git -y
git clone https://github.com/Pastalikek65/ceparsiv
cd ceparsiv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
uvicorn cepearsiv.app:app --host 127.0.0.1 --port 8000
```

FTS5 durumu:

```bash
python scripts/check_fts5.py
```

Ayrık SQLite derlemesi FTS5 içermiyorsa arama otomatik olarak LIKE fallback'e düşer, uygulama çalışmaya devam eder.

## Yapılandırma

Hepsi env değişkeni, hepsi opsiyonel:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `SECRET_KEY` | dev-only değer | oturum imzası; üretimde mutlaka atayın |
| `DATABASE_URL` | `sqlite:///data/app.db` | SQLite dosya yolu |
| `DEBUG` | `0` | `1` iken 500 sayfası traceback gösterir |
| `SESSION_HOURS` | `24` | oturum süresi |

Üretim:

```bash
DEBUG=0 SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
uvicorn cepearsiv.app:app --host 127.0.0.1 --port 8000
```

## Hızlı başlangıç

1. `http://127.0.0.1:8000/register` — ilk hesap (tek kullanıcı varsayımı)
2. Login olun, ana sayfadan ilk item'ı oluşturun
3. API için `/settings/tokens` sayfasından token üretin

```bash
TOKEN='<token>'
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/items

curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"type": "note", "title": "ilk not", "body": "merhaba"}' \
  http://127.0.0.1:8000/api/v1/items
```

Tam uç listesi ve şemalar: [docs/API.md](docs/API.md)

## Test

```bash
python -m pytest -q
```

83 test; CI Python 3.12/3.13/3.14'te çalıştırır.

## Güvenlik

PBKDF2-SHA256 (390k iterasyon), DB tabanlı oturum (HttpOnly, SameSite=Strict), CSRF token tüm POST'larda, API token'ları hash'lenmiş saklanır. Ayrıntı: [docs/SECURITY.md](docs/SECURITY.md). Performans kararları: [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Yedekleme

```bash
python scripts/backup.py
```

`data/backups/` altına zaman damgalı kopya yazar. JSON yedek için web arayüzündeki export/import sayfaları da var.

## Yol haritası

V1 tamamlandı. V2 planı (trigram FTS5, dark mode, tag birleştirme, paylaşılabilir linkler, clipper): [docs/ROADMAP.md](docs/ROADMAP.md)

## Lisans

[MIT](LICENSE)
