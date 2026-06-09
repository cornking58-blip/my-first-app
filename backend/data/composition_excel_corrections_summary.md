# Composition Excel corrections summary

Total records reviewed: 51
Corrected automatically: 42
Left unchanged: 8
Manual-review count: 9
Unresolved concentration count: 1

## Corrected count by category
- fungicides: 5 corrected / 5 reviewed
- herbicides: 33 corrected / 33 reviewed
- insecticides: 1 corrected / 5 reviewed
- seed-treatments: 4 corrected / 8 reviewed

## Validation counts
- Suspicious count before: 51
- Suspicious count after corrected workbooks: 9 effective remaining (8 parser-suspicious rows plus 1 unresolved concentration row marked for manual review).
- Remaining source-data-corruption count: 9
- Unresolved manual-review count: 9

## Exact result for Протект Комби
- Original: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)
- Corrected: (48 г/л Пираклостробин + протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)
- Preserved: пираклостробин — 48 г/л; протиоконазол — concentration unresolved; флудиоксонил — 55 г/л; тебуконазол — 37.5 г/л.

## Output workbooks

Generate these locally with `python backend/create_corrected_workbooks.py`. By default they are written to `corrected_workbooks/`, which is ignored by Git.

- fungicides_raw_FINAL_corrected.xlsx
- herbicides_raw_FINAL_checked_corrected.xlsx
- insecticides_raw_FINAL_v2_corrected.xlsx
- seed_treatments_FINAL_v2_corrected.xlsx

## Original workbook integrity
- Originals were not modified; SHA-256 before/after matched during correction generation.
