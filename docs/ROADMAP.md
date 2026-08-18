# Yol Haritası

## MVP — tamamlandı

| Faz | Kapsam |
|---|---|
| M1 | İskelet, config, SQLite şema, auth (register/login) |
| M2 | Item CRUD (note/bookmark/snippet), slug, soft delete |
| M3 | Tag'ler, favorite/archive, listeleme + sayfalama |
| M4 | FTS5 tam metin arama + LIKE fallback |
| M5 | Web arayüz, Jinja2 template'ler, HTMX |

## V1 — tamamlandı

| Faz | Kapsam |
|---|---|
| E1 | Markdown render (güvenli), item detay görünümü |
| E2 | JSON export/import, audit log, `scripts/backup.py` |
| E3 | Sertleştirme: 404/500 sayfaları, README, dokümanlar, pin'li bağımlılıklar |

## V2 — tamamlandı

| Faz | Kapsam | Durum |
|---|---|---|
| V2-A | Dark mode (tema çerezi, auto/dark/light) | tamamlandı |
| V2-A | Tag yeniden adlandırma ve birleştirme, çakışmada 422 | tamamlandı |
| V2-B | Cursor pagination: item listesi web ve API'de `cursor`/`next_cursor`, OFFSET kaldırıldı | tamamlandı |
| V2-B | Trigram tokenizer (SQLite ≥3.34): alt dize + Türkçe FTS5 arama, kısa sorgularda LIKE fallback | tamamlandı |
| V2-C | Paylaşılabilir tekil link: `/share/<token>`, salt okunur, sahibi silebilir | tamamlandı |
| V2-C | Web clipper bookmarklet: `POST /api/v1/clipper`, duplicate URL dedupe, CORS preflight | tamamlandı |
| V2-D | İki faktörlü auth: TOTP + SVG QR + 10 hash'lenmiş yedek kod | tamamlandı |

## V3 — frontend yeniden tasarımı (tamamlandı)

| Kapsam |
|---|
| "Arşiv Kataloğu" kimliği: IBM Plex Mono + system-ui, damga/cat-num signature, stamp-in animasyon |
| Tasarım sistemi: `static/css/app.css` token'ları (light/dark/auto), favicon.svg, `base.html` yeniden yazımı |
| Dashboard: istatistik kartları, hızlı kayıt formu, son eklenenler |
| Arşiv grid: HTMX load-more (cursor), filtre barı, dizin kartları |
| Item düzenleme sayfaları + canlı markdown önizleme (`/items/preview`) |
| Detay sayfası: yan işlem paneli, paylaşım linki kopyalama (`data-copy`) |
| Canlı arama: debounce HTMX, `<mark>` vurgulu snippet'ler, sayfalama |
| Etiketler hub'ı, ayarlar sekme navigasyonu, auth/hata sayfaları |
| Klavye kısayolları (`/`, `n`, `j/k`), tema döngüsü, toast altyapısı |
| PWA: manifest, service worker (sayfa network-first/statik cache-first), PNG ikonlar |
