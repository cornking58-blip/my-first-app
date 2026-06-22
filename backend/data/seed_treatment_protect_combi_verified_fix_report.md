# Protect Combi verified seed-treatment composition fix

## Live failing API example

Before this fix, seed-treatment API responses for `Протект Комби` could expose the imported source fragment as UI-facing `active_substances_raw`:

```text
(48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + ...repeated...)
```

That text was ambiguous because `Пираклостробин - протиоконазол` did not contain a separate concentration for `протиоконазол`, and it was repeated several times in the source field.

## Verified correction

For `Протект Комби` only, the verified final composition is:

- `Пираклостробин` — `55 г/л`
- `протиоконазол` — `48 г/л`
- `Флудиоксонил` — `37,5 г/л`
- `Тебуконазол` — `10 г/л`

## Why a broad dash rule was not used

The fix does **not** introduce a generic rule that treats `A - B` as two substances with the same concentration. In source composition text, a dash can mean different things: a joined name, punctuation, an antidote label, or an ambiguous fragment. Automatically copying the concentration to the right-hand side would invent data for other products.

Instead, the backend has a small explicit verified correction layer keyed to the normalized product name `протект комби`.

## Before / after active_substances_raw

### Before

```text
(48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол ...)
```

### After

```text
(55 г/л Пираклостробин + 48 г/л протиоконазол + 37,5 г/л Флудиоксонил + 10 г/л Тебуконазол)
```

The original imported text is preserved separately as `source_active_substances_raw` when it differs from the clean canonical value.

## Before / after parsed substances

### Before

- `Пираклостробин` — `48 г/л`
- `протиоконазол` — unresolved concentration
- `Флудиоксонил` — `55 г/л`
- `Тебуконазол` — `37,5 г/л`

### After

- `Пираклостробин` — `55 г/л`
- `протиоконазол` — `48 г/л`
- `Флудиоксонил` — `37,5 г/л`
- `Тебуконазол` — `10 г/л`

## Routes affected

The shared seed-treatment composition normalization path is used by:

- `GET /api/seed-treatments/search`
- `GET /api/seed-treatments/{product_key}`
- `POST /api/seed-treatments/compare-advanced`

Endpoint URLs were not changed.

## Frontend changed

No. The backend now returns a clean UI-facing `active_substances_raw`, so no frontend code change was needed.

## Data stores and source files

- MongoDB changed: no
- Excel/import source files changed: no
- HRAC/FRAC/IRAC data changed: no
- Cost formula changed: no
