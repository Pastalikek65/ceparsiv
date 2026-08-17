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

## V2 — devam ediyor

| Faz | Kapsam | Durum |
|---|---|---|
| V2-A | Dark mode (tema çerezi, auto/dark/light) | tamamlandı |
| V2-A | Tag yeniden adlandırma ve birleştirme, çakışmada 422 | tamamlandı |
| V2-B | Cursor pagination: item listesi web ve API'de `cursor`/`next_cursor`, OFFSET kaldırıldı | tamamlandı |
| V2-B | Trigram tokenizer (SQLite ≥3.34): alt dize + Türkçe FTS5 arama, kısa sorgularda LIKE fallback | tamamlandı |
| V2-C | Paylaşılabilir tekil link | planlandı |
| V2-C | Web clipper bookmarklet | planlandı |
| V2-D | İki faktörlü auth (opsiyonel) | planlandı |
