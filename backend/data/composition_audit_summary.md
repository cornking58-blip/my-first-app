# Active-substance composition audit summary

Total unique product compositions checked: 2235
Clean count: 2184
Suspicious count: 51
Automatically corrected count: 6
Manual-review count: 51

## Warning counts
- malformed_delimiters: 45
- repeated_fragment: 6
- joined_known_substances: 1
- unresolved_concentration: 1

## Counts by pesticide category
- fungicides: 478
- herbicides: 956
- insecticides: 471
- seed-treatments: 330

## Top suspicious products
- seed-treatments / Протект Комби / joined_known_substances;repeated_fragment;unresolved_concentration / automatic parser dedupe: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол); unresolved concentration: протиоконазол
- fungicides / БФТИМ КС-2 / repeated_fragment / automatic parser dedupe: 1х10⁹ КОЕ / Мл Bacillus amyloliquefaciens КС - 2
- seed-treatments / БФТИМ КС-2 / repeated_fragment / automatic parser dedupe: (1х10⁹ КОЕ / Мл Bacillus amyloliquefaciens КС - 2)
- fungicides / Бисолбицид / repeated_fragment / automatic parser dedupe: 0,108 КОЕ / Мл Bacillus subtilis, штамм ВL01
- seed-treatments / Бисолбицид / repeated_fragment / automatic parser dedupe: (0,108 КОЕ / Мл Bacillus subtilis, штамм ВL01)
- insecticides / Доктор Харвест Форте Про / repeated_fragment / automatic parser dedupe: (30 г/л Пиретрины натуральные масляный экстракт)
- herbicides / Агритокс / malformed_delimiters /
- herbicides / Агроксон / malformed_delimiters /
- herbicides / Агрошанс / malformed_delimiters /
- herbicides / Аметил / malformed_delimiters /
- herbicides / Анкор-85 / malformed_delimiters /
- herbicides / Антарес / malformed_delimiters /
- herbicides / Ассолюта / malformed_delimiters /
- seed-treatments / Бактофит / malformed_delimiters /
- seed-treatments / Бактофит / malformed_delimiters /
- fungicides / Биокомпозит-Про / malformed_delimiters /
- insecticides / Биостоп / malformed_delimiters /
- herbicides / Властелин / malformed_delimiters /
- herbicides / Гербикс / malformed_delimiters /
- herbicides / Гербитокс / malformed_delimiters /

## Exact details for Протект Комби
- Category: seed-treatments
  Product key: протект-комби-178-02-4527-1
  Raw composition: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)
  Parsed component count: 4
  Parsed substances: [{"name": "Пираклостробин", "concentration": 48.0, "unit": "г/л", "is_antidote": false, "source_fragment": "Пираклостробин - протиоконазол"}, {"name": "протиоконазол", "concentration": null, "unit": null, "is_antidote": false, "concentration_unresolved": true, "concentration_note": "Концентрация не указана в исходном поле состава", "source_fragment": "Пираклостробин - протиоконазол"}, {"name": "Флудиоксонил", "concentration": 55.0, "unit": "г/л", "is_antidote": false}, {"name": "Тебуконазол", "concentration": 37.5, "unit": "г/л", "is_antidote": false}]
  Warning codes: joined_known_substances;repeated_fragment;unresolved_concentration
  Notes: automatic parser dedupe: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол); unresolved concentration: протиоконазол
