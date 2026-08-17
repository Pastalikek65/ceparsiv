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

## V2 — planlanan

- Trigram tokenizer ile Türkçe FTS5 iyileştirme
- Dark mode
- Tag birleştirme / yeniden adlandırma
- Paylaşılabilir tekil link
- Web clipper bookmarklet
- Offset yerine cursor pagination
- İki faktörlü auth (opsiyonel)
