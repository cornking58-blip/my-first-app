# Seed treatment full bugfix report

Total seed-treatment records audited: 1435

## Issue counts
- empty_composition_warning: 277
- manual_review_required: 277
- repeated_fragment_warning: 11
- safe_auto_fix_possible: 1158
- product_name_contains_composition_warning: 51

## Root cause
Seed-treatment composition was sometimes repeated in active_substances_raw or embedded in product_name, while backend selection previously only trusted active_substances_raw and comparison used unsafe substring matching.

## Протект Комби
- Before: repeated source fragments in active_substances_raw.
- After: Пираклостробин — 48,0 г/л; протиоконазол — —; Флудиоксонил — 55,0 г/л; Тебуконазол — 37,5 г/л

## Туарег
- Before: composition stored in product_name caused zero parsed active substances when active_substances_raw was empty.
- After display name: Туарег, СМЭ
- After composition: Имидаклоприд — 280,0 г/л; Имазалил — 34,0 г/л; Тебуконазол — 20,0 г/л

MongoDB changed: no. Excel/import changed: no.
