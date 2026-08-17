# CepArsiv API (v1)

Tüm endpointler `/api/v1` altında ve JSON döner.

## Auth

```
Authorization: Bearer <token>
```

Token, web arayüzündeki `/settings/tokens` sayfasından oluşturulur. Ham token değeri yalnızca bir kez gösterilir; DB'de SHA-256 hash'i saklanır. Geçersiz, silinmiş veya süresi dolmuş token'lar `401` döner.

## Endpointler

| Method | Yol | Açıklama | Parametreler |
|---|---|---|---|
| GET | `/api/v1/items` | Item listesi | `type`, `tag`, `favorite`, `archived`, `deleted`, `page`, `limit`, `cursor` |
| POST | `/api/v1/items` | Item oluştur (201) | body: `ItemCreate` |
| GET | `/api/v1/items/{id}` | Item detayı | — |
| PATCH | `/api/v1/items/{id}` | Item güncelle | body: `ItemUpdate` |
| DELETE | `/api/v1/items/{id}` | Soft delete | — |
| GET | `/api/v1/search` | Tam metin arama | `q` (zorunlu), `type`, `tag`, `include_archived`, `include_deleted`, `page`, `limit` |
| GET | `/api/v1/tags` | Tag listesi + sayılar | — |
| POST | `/api/v1/clipper` | Web clipper: yer imi oluştur veya mevcut olanı döndür | body: `ClipperCreate` |

`page` varsayılanı 1, `limit` varsayılanı 20, üst sınırı 100. `type`: `note`, `bookmark`, `snippet`.

Item listesi cursor tabanlı sayfalamayı da destekler. Yanıttaki `next_cursor` değerini bir sonraki isteğe `?cursor=...` olarak verin; `cursor` verilirse `page` yok sayılır. Geçersiz cursor `422` döner.

## Şemalar

`ItemCreate`:

```json
{"type": "note", "title": "str (1-200)", "body": "str", "url": "str|null"}
```

`type: "bookmark"` için `url` zorunludur; yoksa `422`.

`ItemUpdate` (yalnızca verilen alanlar güncellenir):

```json
{"title": "str|null", "body": "str|null", "url": "str|null", "is_favorite": null, "is_archived": null}
```

`ClipperCreate`:

```json
{"title": "str|null", "url": "str (zorunlu)", "selection": "str"}
```

`title` boşsa `url` başlık olarak kullanılır. Aynı URL daha önce kaydedilmişse yeni item oluşturulmaz, mevcut item `200` ile döner (ilk oluşturma `201`).
```

Item çıktısı:

```json
{"id": 1, "type": "note", "title": "...", "slug": "...", "body": "...", "url": null, "is_favorite": false, "is_archived": false, "created_at": "...", "updated_at": "...", "tags": ["a", "b"]}
```

## Yanıt formatları

- Liste: `{"items": [...], "has_next": true, "page": 1, "next_cursor": "..."}`
- Arama: `{"items": [...], "has_next": true}`
- Tagler: `{"tags": [{"name": "...", "count": 3}]}`
- Silme: `{"detail": "deleted"}`
- Hata: `{"detail": "..."}`

## Hata kodları

| Kod | Anlam |
|---|---|
| 401 | Auth geçersiz / eksik |
| 404 | Item bulunamadı (ya da başka bir kullanıcıya ait) |
| 422 | Şema ya da iş kuralı doğrulama hatası |

## curl örnekleri

```bash
TOKEN='<token>'
BASE=http://127.0.0.1:8000/api/v1

curl -H "Authorization: Bearer $TOKEN" "$BASE/items?type=note&limit=10"

curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type": "note", "title": "ilk not", "body": "merhaba", "tags": ["not"]}' \
  "$BASE/items"

curl -H "Authorization: Bearer $TOKEN" "$BASE/search?q=merhaba"
```

## Web clipper bookmarklet

Browser bookmarks bar'ına yeni bir yer imi ekleyin, URL olarak aşağıdaki kodu yapıştırın. Sayfadayken tıklayınca o sayfa CepArsiv'e bookmark olarak kaydedilir (seçili metin varsa gövdeye eklenir).

```javascript
javascript:(function(){var T='API_TOKEN';var B='http://127.0.0.1:8000/api/v1/clipper';var s=window.getSelection?window.getSelection().toString():'';fetch(B,{method:'POST',headers:{'Authorization':'Bearer '+T,'Content-Type':'application/json'},body:JSON.stringify({title:document.title,url:location.href,selection:s})}).then(function(r){if(r.status===200)return alert('Zaten arşivde.');if(r.status===201)return alert('Kaydedildi.');return alert('Hata: '+r.status);}).catch(function(e){alert('CepArsiv ulaşılamadı.');});})();
```

`API_TOKEN` yerine `/settings/tokens` sayfasından alınan token'ı, `B` yerine sunucunuzun adresini koyun.

## CORS

`/api/v1` altındaki isteklere her origin'e açık CORS uygulanır; preflight (OPTIONS) desteklenir. Tek kullanıcılı yerel kurulum için yazılmıştır; başkalarını ağırlayan bir dağıtımda origin'leri daraltın.
