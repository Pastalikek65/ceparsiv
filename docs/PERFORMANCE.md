# Performans Notları

Düşük kaynaklı cihaz (proot Ubuntu, tek çekirdek ağırlıklı) için alınan kararlar.

## SQLite yapılandırması

Her bağlantıda PRAGMA olarak ayarlanır (`cepearsiv/db.py`):

| PRAGMA | Değer | Neden |
|---|---|---|
| `journal_mode` | `WAL` | Okuma/yazma çakışmaz, eşzamanlı okuma |
| `synchronous` | `NORMAL` | WAL ile yeterli dayanıklılık, daha az fsync |
| `foreign_keys` | `ON` | Bütünlük |
| `busy_timeout` | `5000` | Kilit için 5 sn bekle, anında hata verme |
| `cache_size` | `-2000` | 2 MB sayfa cache |

## Sunucu

- Tek worker uvicorn. SQLite + in-memory rate limit varsayımı tek worker'a göre kuruludur; worker sayısını artırmayın.

## Sayfalama

- `COUNT(*)` sorgusu yok: `LIMIT page_size + 1` ile çekilir, satır sayısı `page_size`'ı aşıyorsa `has_next = true` (`cepearsiv/services/items.py:151`).

## Arama

- FTS5 kullanılabilirse tam metin araması; değilse escape'li LIKE fallback (`cepearsiv/services/search.py`).
- FTS5 index'i taban tablolarla trigger'lar üzerinden senkron kalır; import sonrası rebuild edilir.

## Statikler

- `pico.min.css` ve `htmx.min.js` yerelde (`cepearsiv/static/`). CDN yok, dış ağ isteği yok.

## Telefon (Termux / proot) optimizasyonları

- `--reload` yalnızca geliştirme sırasında; üretimde düz `uvicorn`.
- Sunucu gereksizken uvicorn'u kapatın.
- Büyük import'ları şarjda ve ekran kapalıyken yapın.
- `termux-wake-lock` yalnızca sunucu açıkken tutulsun; işiniz bitince bırakın.
- `pytest` tam süiti düşük cihazda ~30 sn sürer; hızlı döngü için tek test dosyası çalıştırın.
