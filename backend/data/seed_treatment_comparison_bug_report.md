# Seed-treatment comparison bug audit: Протект Комби and Туарег

## Scope

This report audits the seed-treatment product card and advanced comparison flows for:

- `Протект Комби`
- `Туарег`

No MongoDB records were changed. No Excel/import logic was changed. Endpoint URLs were not changed.

## Backend response summary: Протект Комби product card

Expected product identity from the audited source data:

- `product_key`: `протект-комби-178-02-4527-1`
- `product_name`: `Протект Комби`
- `active_substances_raw`: `(48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)`
- `applications_count`: 4 source application rows in the audited workbook/report.

Parsed active substances after parser dedupe/splitting:

| name | concentration | unit | concentration_unresolved | resistance fields | grams_per_ha | estimated_cost_per_gram |
| --- | ---: | --- | --- | --- | --- | --- |
| Пираклостробин | 48 | г/л | no | annotated from FRAC data when available | null unless rate is supplied/resolved | null unless price and compatible rate are supplied |
| протиоконазол | null | null | yes | annotated from FRAC data when available | null | null |
| Флудиоксонил | 55 | г/л | no | annotated from FRAC data when available | null unless rate is supplied/resolved | null unless price and compatible rate are supplied |
| Тебуконазол | 37.5 | г/л | no | annotated from FRAC data when available | null unless rate is supplied/resolved | null unless price and compatible rate are supplied |

Duplicate active substances:

- Source field repeats the same 3-fragment composition block 4 times.
- Parser deduplicates repeated fragments for parsing only.
- Final parsed active-substance count must be exactly 4, not 12.

## Backend response summary: Протект Комби comparison

The comparison endpoint uses the same parser as the product-card metadata. The fixed behavior is:

- `left/right.active_substances_raw` keeps the source composition selected for that product.
- `left/right.substances` contains the same 4 parsed active substances listed above.
- `протиоконазол` stays visible with `concentration: null`, `unit: null`, and `concentration_unresolved: true`.
- Cost rows are produced only for substances with a real positive concentration, a compatible rate, and a supplied price. Therefore no cost row is produced for unresolved `протиоконазол`.

## Backend response summary: Туарег product card

Observed failure class:

- The product card can show active-substance data because at least one MongoDB application row for the product contains `active_substances_raw`.
- Some grouped/first-row logic can choose a duplicate application row whose composition field is empty or non-parseable.

Fixed product-card behavior:

- `product_key`: whatever key is returned by `/api/seed-treatments/search?q=Туарег`.
- `product_name`: `Туарег`.
- `active_substances_raw`: first non-empty, parseable composition among duplicate application rows for the same `product_key`.
- Parsed active substances: non-empty when the source product has a parseable composition in any duplicate row.
- `concentration`, `unit`, `concentration_unresolved`, resistance fields, `grams_per_ha`, and `estimated_cost_per_gram`: preserved/calculated by the existing shared parser, resistance annotation, rate, and price logic.

## Backend response summary: Туарег comparison

Fixed comparison behavior:

- The compare endpoint no longer relies on `records[0].active_substances_raw`.
- It first selects the first non-empty composition that parses among all application rows for `product_key`.
- Therefore, if the product card has active-substance data from any application row, comparison receives the same canonical composition and does not lose `Туарег` substances.

## Root cause

Two generic bugs were found:

1. Backend product aggregation/selection bug:
   - Search/product/compare code used Mongo `$first` or `records[0]` for `active_substances_raw`.
   - Duplicate application rows can have inconsistent composition presence.
   - If the first row is blank/non-parseable, comparison can return an empty parsed composition even though another row for the same product contains the composition.

2. Frontend/backend substance matching bug:
   - Substance rows and cost/resistance details were matched with partial substring checks.
   - This is unsafe for active substances because one normalized name can be contained inside another neighboring/related name.
   - A partial match can attach metrics to the wrong component. For a beginner-friendly analogy: the UI was sometimes matching by “contains these letters” instead of “is the exact same substance”.

## Fix applied

Backend changed: yes.

- Added a shared composition selector that picks the first non-empty, parseable `active_substances_raw` from all duplicate product rows.
- Product-card and compare code now use that canonical composition.
- Search grouping now carries all composition candidates and selects a parseable one after grouping.
- Backend substance-name comparison now requires exact normalized-name equality instead of substring matching.

Frontend changed: yes.

- Seed-treatment comparison matching now normalizes case/`ё`/spaces but requires exact equality.
- Null concentration continues to render as `—`.
- Cost metric remains hidden when `estimated_cost_per_gram` is null/undefined.

## Before / after behavior

### Before

- `Протект Комби`: repeated composition fragments could appear as repeated cards, and partial/index-like matching could display a metric under a neighboring substance.
- `Туарег`: comparison could lose composition when the first duplicate Mongo row had blank/non-parseable `active_substances_raw`.

### After

- `Протект Комби`: final parsed list is exactly 4 active substances; `протиоконазол` has unresolved concentration; other concentrations stay attached to their own names.
- `Туарег`: comparison uses a parseable composition from the product rows and keeps active substances when source data has them.
- Matching is by normalized exact name and side, not by partial name.

## Classification against requested categories

- A. backend parser: no new parser bug found; existing parser behavior for `Протект Комби` is preserved and tested.
- B. backend product aggregation: yes, fixed.
- C. backend comparison response: yes, fixed by canonical composition selection.
- D. frontend rendering: yes, safer matching in comparison rendering.
- E. frontend lookup of substance cost data: yes, safer exact normalized matching.
- F. frontend matching by substance name: yes, fixed.
- G. duplicate MongoDB application rows: contributing data shape; no DB changes made.
- H. stale MongoDB data: not changed and not required for the generic fix.

## Manual-safe verification checklist

- Протект Комби card composition: shows source composition; parsed metadata is 4 substances.
- Протект Комби comparison composition: shows 4 components, not 12.
- Протект Комби unresolved concentration: `протиоконазол` displays `—` / unresolved and is not given a fake value.
- Туарег card composition: if any product row has composition, product response selects a parseable composition.
- Туарег comparison composition: compare response keeps non-empty substances when source has composition.
- Cost metric: shown only when price, compatible rate, grams per hectare, and estimated cost per gram exist.
- grams_per_ha: calculated only for compatible concentration/rate units.
- Resistance groups: still annotated through the existing resistance lookup path; no HRAC/FRAC/IRAC data changed.
