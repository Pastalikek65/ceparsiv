# CepArsiv

Kişisel bilgi arşivi: not, yer imi ve snippet'leri tek bir yerde tutar. Termux/proot Ubuntu üzerinde telefonda çalışacak şekilde tasarlandı — düşük kaynak, tek kullanıcı, CDN'siz.

## Özellikler

- Üç item tipi: not, yer imi, snippet
- Güvenli Markdown render (detay görünümü)
- Tam metin arama (FTS5, yoksa LIKE fallback)
- Tag, favori ve arşivleme, soft delete
- REST API (Bearer token)
- JSON export / import
- Audit log (`/settings/audit`)
- SQLite yedekleme: `python scripts/backup.py`

Ekran görüntüleri ileride eklenecek.

## Kurulum (Termux / proot Ubuntu)

```bash
pkg install python -y
git clone https://example.invalid/ceparsiv
cd ceparsiv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
uvicorn cepearsiv.app:app --host 127.0.0.1 --port 8000
```

Ayrılmış bir SQLite derlemesi FTS5'in tam halini içermezse uygulama LIKE fallback'e düşer; durumu `python scripts/check_fts5.py` ile kontrol edin.

Üretim ortamı için:

```bash
DEBUG=0 SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
uvicorn cepearsiv.app:app --host 127.0.0.1 --port 8000
```

## Hızlı başlangıç

1. `http://127.0.0.1:8000/register` ile hesap oluşturun (ilk kayıt kullanıcı olur).
2. Login olun.
3. Ana sayfadan ilk item'ı oluşturun.
4. API kullanacaksanız `/settings/tokens` sayfasından token üretin → [docs/API.md](docs/API.md).

## Test

```bash
python -m pytest -q
```

## Güvenlik

Parola hash'i, oturum, CSRF, token saklama, XSS/SQLi önlemleri ve import limitleri: [docs/SECURITY.md](docs/SECURITY.md). Performans kararları: [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Yedekleme

```bash
python scripts/backup.py
```

Yedekler `data/backups/` altına zaman damgalı kopya olarak yazılır.

## Yol haritası

[docs/ROADMAP.md](docs/ROADMAP.md)

## Lisans

MIT
