# CepArsiv Frontend Yeniden Tasarımı — Tasarım Belgesi

Tarih: 2026-08-18
Durum: onaylandı

## Amaç

CepArsiv'in tüm arayüzünü "Arşiv Kataloğu" kimliğiyle en baştan yeniden kurmak:
sıcak kâğıt tonları, dizin kartı düzeni, monospace katalog verisi, kiremit damga
vurgusu. Telefonda (Termux) tek elle kullanım için tasarlandı: 0 CDN bağımlılığı,
hafif yük, PWA ile ana ekrana kurulabilir.

## Tasarım sistemi

### Renk token'ları (CSS değişkenleri, `[data-theme="light|dark"]` ile iki set)

| Rol | Işıklı | Koyu |
|---|---|---|
| `--bg` | `#F6F1E7` | `#161A1E` |
| `--card` | `#FFFDF6` | `#1F252B` |
| `--ink` | `#20272E` | `#E7E2D6` |
| `--muted` | `#5C666F` | `#9AA3AC` |
| `--line` | `#E3DAC6` | `#2D343B` |
| `--accent` (kiremit/damga) | `#B85C38` | `#C96A4A` |
| `--accent-2` (arşiv laciverti) | `#1E3A5F` | `#7FA3C9` |
| `--ok` / `--err` | `#3E7A4E` / `#B03030` | `#7FB98B` / `#E07A6A` |

Tüm bileşen renkleri bu token'lardan türer; ham hex'ler yalnızca tanımda geçer.

### Tipografi

- **Body:** `system-ui` stack (indirme yok).
- **Veri/katalog:** IBM Plex Mono 400/600 — woff2 dosyaları `static/fonts/` altına
  indirilir (CDN'den çekilip pakete gömülür; runtime CDN yok).
- **Başlıklar:** system-ui, 700 ağırlık, geniş harf aralığı (`letter-spacing`).
- Türkçe karakter desteği her yerde zorunlu.

### Signature: Damga

- Her item kartında köşede mono katalog numarası `CA-{id}` (4 haneli, sıfır dolgulu).
- Tür damgası rozeti: `NOT` / `YER İMİ` / `SNIPPET` — kiremit çerçeveli, mono.
- HTMX ile yüklenen yeni kartlar "damga basılma" animasyonu (scale+fade, ~200ms).
- `prefers-reduced-motion: reduce` altında tüm animasyonlar kapalı.

### Layout

- **Sticky üst bar:** wordmark · arama kutusu (her zaman görünür, `/` kısayolu) ·
  `+` hızlı yeni · tema düğmesi · kullanıcı menüsü.
- **Dashboard (`/`, girişli):** istatistik şeridi (toplam / son 7 gün / favori /
  etiket — mono rakamlar), son eklenenler listesi, hızlı kayıt formu.
- **Arşiv (`/items`):** dizin kartı grid (mobil 1 kolon, ≥720px 2 kolon), filtre
  çubuğu (tür/favori/arşiv/çöp), HTMX "Daha fazla yükle" (cursor pagination).
- **Detay (`/items/{id}`):** içerik + yan meta paneli (meta, etiketler, paylaşım,
  eylemler). Kod blokları koyu kutu, tablolar çizgili.
- **Form (`/items/new`, `/items/{id}/edit`):** yan yana editör + canlı önizleme
  (mobilde sekme düğmeleri); önizleme sunucu tarafı HTMX ile.
- **Ayarlar:** üst sekme listesi (2FA / Token / Denetim / Veri / Ana).
- **Auth (giriş/kayıt/2FA):** ortalanmış kart, wordmark başlık.

## Yeni backend parçaları (hepsi test-first)

1. **Item düzenleme:** `GET /items/{item_id}/edit` + `POST /items/{item_id}/edit`
   (form.html zaten edit modunu destekliyor; route yok). POST'ta title/type/url/
   tags/body güncellenir, `updated_at` tazelenir, audit log `item.update`.
2. **Dashboard istatistikleri:** `services/dashboard.py` →
   `dashboard_stats(session, user_id)` → `{total, last7, favorites, tags}`; route
   `GET /` girişli kullanıcıya dashboard, misafire index sayfası.
3. **Arama vurgusu:** `search_items` sonuçları için `highlight` alanı — body'den
   eşleşen ilk parçayı çevresel bağlamla keser, eşleşmeler `<mark>` ile sarılır
   (HTML escape sonrası). FTS5 ve LIKE her iki backend için ortak yardımcı.
4. **Markdown önizleme:** `POST /items/preview` — body'yi render edip HTML parçası
   döner (Jinja `markdown.html` partial). CSRF korumalı, girişli.
5. **HTMX partial'lar:** `/items` cursor "daha fazla" için `items/partials/card_grid.html`
   (yeni kartlar), `/search` için sonuç partial'ı; tam sayfa olmayan swap'lar.
6. **Toast:** flash mesajları için `partials/toast.html` + HTMX swap kutusu;
   `web_data._flash_store` deseni genelleştirilir (`web/toast.py` yardımcıları).

## PWA

- `static/manifest.json` (name CepArsiv, theme_color koyu, icons SVG+PNG),
  `static/icons/icon-192.png`, `icon-512.png` (SVG'den üretilir),
  `static/sw.js` (precache: css, js, fonts, manifest, ikonlar; runtime network-first
  sayfalar, cache-first statik).
- `base.html`'de manifest link + SW kaydı + `apple-touch-icon`.
- Mobil kullanılabilirlik: `viewport-fit=cover`, güvenli alan boşlukları.

## İstemci JS (vanilla + htmx, yeni kütüphane yok)

- `static/app.js`: `/` arama odakla, `n` yeni item (girişli sayfalarda), `j/k`
  liste gezintisi, tema döngüsü, SW kaydı, toast otomatik kaybolma.
- htmx zaten mevcut; `hx-get`/`hx-post`/`hx-swap` ile canlı arama (debounce),
  daha fazla yükle, önizleme, toggle'lar (ayrı görünüm istekleri, token-typed).

## Kapsam dışı (bilinçli)

- Yeni pip paketi yok. Yeni JS kütüphanesi yok (markdown istemci tarafı yok —
  önizleme sunucuda).
- Çok kullanıcılı/işbirliği, API değişikliği (yeni endpoint'ler eklemek dışında).
- Mevcut 149 testin tamamı yeşil kalmalı.

## Test stratejisi

- Backend değişiklikleri (edit, dashboard, highlight, preview) kırmızı→yeşil test-first.
- Template yeniden yazımları mevcut süitle doğrulanır (testler template içeriğine
  bağlı değil).
- Her görev sonunda tam `pytest -q` + `py_compile`.

## Commit düzeni

- Backend özellikleri kendi commit'lerinde: `feat(web): edit item route`,
  `feat(web): dashboard stats`, `feat(search): highlighted snippets`,
  `feat(web): markdown preview`.
- Tasarım sistemi: `ui: catalog design system (tokens, fonts, base)`,
  ardından sayfa bazında `ui: <page> redesign`.
- PWA: `feat(pwa): manifest, sw, icons`.
- Her commit CI'da yeşil; push yalnızca tam süit yeşilken.
