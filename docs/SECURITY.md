# Güvenlik Notları

CepArsiv tek kullanıcı varsayımıyla, düşük kaynaklı (proot Ubuntu) bir ortamda çalışacak şekilde tasarlandı. Aşağıdakiler mevcut durumun özeti, garantiler değil.

## Parola

- PBKDF2-HMAC-SHA256, **390.000 iterasyon**, 16 bayt rastgele tuz (`secrets.token_hex(16)`).
- Saklama formatı: `pbkdf2_sha256$390000$<salt>$<digest-hex>` (`cepearsiv/security.py`).
- Doğrulamada `hmac.compare_digest` ile sabit zamanlı karşılaştırma.

## Oturum (web)

- DB tabanlı oturum kayıtları; cookie yalnızca oturum anahtarını taşır.
- Cookie: `HttpOnly`, `SameSite=Strict`, varsayılan yol `/`.
- Süre: 24 saat (`SESSION_HOURS` ile değişir).

## CSRF

- Formlarda `csrf_token` hidden alanı; tüm POST'larda zorunlu, eksikse `403`.
- Token `secrets.token_urlsafe(32)` ile üretilir.

## API token

- `secrets.token_urlsafe(32)` ile üretilir; ham değeri yalnızca bir kez gösterilir.
- DB'de yalnızca SHA-256 hash'i saklanır (`cepearsiv/services/tokens.py`).
- Silinen ya da süresi geçen token'lar `401` döner.

## XSS

- Jinja2 autoescape açık; `|safe` yalnızca `render_markdown` çıktısında kullanılır.
- Markdown: `html` passthrough kapalı (`_md.options["html"] = False`), link `href`/`title` escape edilir, scheme beyaz listesi (`http/https/mailto/ftp`), linklere `rel="nofollow noopener"`.

## SQL Injection

- Tüm sorgular SQLAlchemy parametreli sorgularıyla gider.
- FTS5 MATCH query builder, özel karakterleri temizler; LIKE fallback ise `%`, `_`, `\` kaçışlanır. Ham kullanıcı girdisi SQL içine string birleştirmeyle konmaz.

## İki faktörlü auth (TOTP)

- Kullanıcı başına opsiyonel; `/settings/2fa` üzerinden etkinleştirilir.
- TOTP: RFC 6238, 30 sn adım, `valid_window=1` (±30 sn saat kayması toleransı). Sır DB'de düz metin saklanır (TOTP doğası gereği sunucunun sırrı bilmesi gerekir).
- Etkinleştirme iki adımda: sır oluşturulur → kullanıcı QR'ı tarar → kod doğrulanmadan `otp_enabled` açılmaz.
- 10 yedek kod üretilir, DB'de yalnızca SHA-256 hash'i saklanır; her biri tek kullanımlık, kullanıldığı an işaretlenir. Yedek kodlar yalnızca etkinleştirme ekranında bir kez gösterilir.
- 2FA girişi: şifre doğruysa geçici, 5 dk ömürlü HttpOnly bilet verilir; kod doğrulanana kadar oturum açılmaz. Bilet tek kullanımlık, in-memory (tek worker varsayımı).
- Devre dışı bırakma şifre + güncel kod (veya yedek kod) gerektirir; sır ve tüm yedek kodlar silinir.

## Kaba kuvvet koruması

- Login: kullanıcı + IP başına 5 deneme / 5 dakika, aşılırsa `429`.
- In-memory sayaç; tek worker varsayımına dayanır, çok worker'da koruma zayıflar.

## Import limitleri

- Dosya boyutu: en fazla 10 MB (`MAX_IMPORT_BYTES`).
- Item sayısı: en fazla 5000 (`MAX_IMPORT_ITEMS`); aşan dosya `422` ile tamamen reddedilir, kısmi yazım olmaz.

## Diğer

- Üretimde `DEBUG=0` zorunlu; `DEBUG=1` iken 500 sayfası traceback gösterebilir.
- `SECRET_KEY` ortama değişkeniyle atanmalı; varsayılan değer yalnızca geliştirme içindir.
