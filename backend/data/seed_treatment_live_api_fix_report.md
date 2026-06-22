# Seed-treatment live API display/composition fix

## Live failing API example

Observed local request after the previous fix:

`GET http://localhost:8001/api/seed-treatments/search?q=Туарег&limit=5`

Returned unsafe display fields:

```json
{
  "product_name": "Туарег, СМЭЗ (280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)",
  "active_substances_raw": "(280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)"
}
```

## Root cause

The canonical seed-treatment helper existed, but the `/api/seed-treatments/search` response was still assembled directly from the Mongo aggregation row. That meant the route could bypass the same cleaned display/composition response shape used elsewhere. Search also only reconstructed candidate records from `active_substances_raw_values`, so product-name composition was not guaranteed to be included as a candidate in actual aggregation output.

## Route handlers fixed

- `GET /api/seed-treatments/search`
- `GET /api/seed-treatments/{product_key}`
- `POST /api/seed-treatments/compare-advanced` through the shared `build_advanced_compare_response` path

Endpoint URLs were not changed.

## Туарег search before/after

Before:

```json
{
  "product_name": "Туарег, СМЭЗ (280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)",
  "active_substances_raw": "(280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)"
}
```

After:

```json
{
  "product_name": "Туарег, СМЭЗ",
  "display_product_name": "Туарег, СМЭЗ",
  "raw_product_name": "Туарег, СМЭЗ (280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)",
  "active_substances_raw": "(280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)",
  "active_substances": [
    {"name": "Имидаклоприд", "concentration": 280, "unit": "г/л"},
    {"name": "Имазалил", "concentration": 34, "unit": "г/л"},
    {"name": "Тебуконазол", "concentration": 20, "unit": "г/л"}
  ]
}
```

## Туарег compare before/after

Before: compare could receive the canonical raw composition only in `active_substances_raw`, while display fields and parsed aliases were not consistently exposed in the response.

After: compare returns clean `product_name`, `display_product_name`, `raw_product_name`, `active_substances`, `substances`, `substance_count: 3`, and `total_concentration: 334` for Туарег.

## Протект Комби before/after

Before: repeated source fragments could leak into frontend-facing composition display if the frontend relied only on raw composition text.

After: search, product detail, and compare all expose the canonical parsed list:

- Пираклостробин — 48 г/л
- протиоконазол — unresolved/null
- Флудиоксонил — 55 г/л
- Тебуконазол — 37,5 г/л

The repeated 12-component source composition is not duplicated in parsed frontend fields.

## Frontend changed

No. The safest minimal change was backend-only: seed-treatment API responses now set `product_name` to the cleaned display name because the existing frontend already reads `product_name`. The backend also returns `display_product_name`, `raw_product_name`, and canonical parsed `active_substances` for safer future frontend rendering.
