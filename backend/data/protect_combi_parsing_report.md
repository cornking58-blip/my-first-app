# Protect Combi active-substance parsing audit

## Source inspected

- File inspected: `seed_treatments_FINAL_v2.xlsx`
- Sheet XML inspected directly: `xl/worksheets/sheet1.xml`
- Sheet range: `A1:U1457`
- Backend import header row: Excel row 4
- Composition-related columns present in the source: only `active_substances_raw`
- Separate `composition`, active-ingredient-name, or concentration columns: not present
- Merge ranges in the sheet: `A1:U1`, `A2:U2`; no merged cells affect the `Протект Комби` data rows
- Matching product-name variants found:
  - `Протект Комби`: 4 rows
  - `Protect Combi`: 0 rows
  - `protect combi`: 0 rows
  - Other `Протект` variants: `Протект`, `Протект Форте`

## Exact original Excel values for `Протект Комби`

All four source rows share the Mongo-compatible key created by import code:

```text
Протект Комби|178-02-4527-1
```

### Common values in rows 504-507 / record_id 500-503

```text
product_name: Протект Комби
formulation: СЭ
active_substances_raw: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)
manufacturer: ООО «Агро Эксперт Груп» ОГРН 1027708006996
registration_number: 178-02-4527-1
registration_start_date: 24.04.2024
registration_end_date: 23.04.2034
registration_status: Действует
application_method: Предпосевная обработка семян с увлажнением перед посевом или заблаговременно; Расход рабочей жидкости - 10 л/т
waiting_period: -(1)
reentry_period_manual: -(-)
source_page: 441
source_type: official_registry_pdf
notes: Пираклостробин - протиоконазол + флудиоксонил + тебуконазол + пираклостробин - протиоконазол + флудиоксонил + тебуконазол + пираклостро
pesticide_type: fungicide_seed
```

### Row-specific registration/application values

| Excel row | record_id | rate_raw | crop | target_object |
|---:|---:|---|---|---|
| 504 | 500 | `1,0` | `Пшеница озимая` | `Пыльная головня, фузариозная снежная плесень, тифулезная снежная плесень, церкоспореллезная гниль корневой шейки` |
| 505 | 501 | `0,8-1,0` | `Ячмень озимый, яровой` | `Каменная головня, пыльная головня, фузариозная корневая гниль, гельминтоспориозная корневая гниль, плесневение семян, сетчатая пятнистость` |
| 506 | 502 | `1,0` | `Пшеница яровая` | `Пыльная головня` |
| 507 | 503 | `0,8-1,0` | `Пшеница озимая, яровая` | `Твёрдая головня, фузариозная корневая гниль, гельминтоспориозная корневая гниль, плесневение семян` |

## Neighbouring column check

The source row has these relevant neighbouring columns:

```text
C: formulation = СЭ
D: active_substances_raw = repeated composition shown above
E: manufacturer = ООО «Агро Эксперт Груп» ОГРН 1027708006996
F: registration_number = 178-02-4527-1
...
T: notes = repeated/truncated names without separate concentrations
U: pesticide_type = fungicide_seed
```

There are no populated columns after `U` for these rows. Therefore the Excel file does not contain a separate reliable concentration cell for `протиоконазол`.

## Is the source corrupted?

Yes. The source composition is corrupted in two ways:

1. The same composition fragment is repeated four times inside `active_substances_raw`.
2. `Пираклостробин - протиоконазол` joins two real active substances with a spaced hyphen. `Пираклостробин` and `протиоконазол` are separate active substances, but the source field does not provide a separate concentration before `протиоконазол`.

The available Excel source does not prove whether this came from a broken Excel column merge, a lost delimiter, or OCR/PDF extraction. The XML check shows no row-level merged cells around `D504:D507`, so the corruption is already inside the `active_substances_raw` text rather than caused by adjacent Excel columns being merged at import time.

## Same corruption pattern in other seed-treatment records

Searching all `active_substances_raw` values for the pattern `<text> - <text>` found:

- `Протект Комби`, rows 504-507: `Пираклостробин - протиоконазол`; both sides are known active substances, so the parser splits them and marks the second concentration unresolved.
- `Стандак Топ`, row 1445: `Тиофанат - метил`; this is a hyphenated single active-substance name, not two active substances, so the parser does not split it.

## Parser output before this correction

The previous fix deduplicated repeated fragments but still returned this incorrect 3-item output:

```text
1. Пираклостробин - протиоконазол — 48 г/л
2. Флудиоксонил — 55 г/л
3. Тебуконазол — 37,5 г/л
```

That was still wrong because `Пираклостробин - протиоконазол` is not one active substance.

## Parser output after this correction

The corrected parser returns four real active-substance names and does not invent the missing concentration:

```text
1. Пираклостробин — 48 г/л
2. протиоконазол — concentration unresolved; no separate source concentration found
3. Флудиоксонил — 55 г/л
4. Тебуконазол — 37,5 г/л
```

## Expected real active substances and concentrations

Expected real number of active substances based on the source text: 4.

Reliable concentrations from the exact Excel composition:

| Active substance | Reliable concentration |
|---|---:|
| `Пираклостробин` | `48 г/л` |
| `Флудиоксонил` | `55 г/л` |
| `Тебуконазол` | `37,5 г/л` |

Unresolved value:

| Active substance | Status |
|---|---|
| `протиоконазол` | Separate concentration is not present in the available Excel source; parser returns the name with `concentration = None` and `concentration_unresolved = true`. |

## What changed

- Backend parser changed: yes.
- Import data changed: no.
- HRAC / FRAC / IRAC assignments changed: no.
- Endpoint URLs changed: no.
- Frontend changed: no.

The fix is still generic and is not a product-name special case. The parser splits a spaced-hyphen name only when all sides are independently known active-substance lookup keys. This keeps `Тиофанат - метил` as one substance while preventing `Пираклостробин - протиоконазол` from being treated as one.

## Tests added/updated

Regression tests cover:

- exact `Протект Комби` source composition;
- deduplication of repeated composition fragments;
- splitting two real substances joined by a spaced separator;
- no fake concentration for the separated `протиоконазол`;
- no formulation/manufacturer/crop/disease/rate/registration/application fragments in parsed active substances;
- duplicate composition values from repeated registration/grouped rows;
- normal multi-component seed-treatment parsing;
- `%`, `г/л`, and `г/кг` concentration preservation;
- hyphenated single-substance names such as `Тиофанат - метил` not being split;
- herbicide, fungicide, and insecticide parser compatibility;
- endpoint URL stability through the existing endpoint-list regression test.
