# Active-substance composition audit report

This concise Markdown report lists suspicious compositions. The full row-level report is in `composition_audit_report.csv`.

| category | product | warnings | severity | notes |
| --- | --- | --- | --- | --- |
| herbicides | Фортиссимо | malformed_delimiters | warning |  |
| herbicides | Илион | malformed_delimiters | warning |  |
| herbicides | Репер | malformed_delimiters | warning |  |
| herbicides | Репер Трио | malformed_delimiters | warning |  |
| herbicides | Эфилон | malformed_delimiters | warning |  |
| herbicides | Корнкордия | malformed_delimiters | warning |  |
| herbicides | Агроксон | malformed_delimiters | warning |  |
| herbicides | Дикопур М | malformed_delimiters | warning |  |
| herbicides | Горгон | malformed_delimiters | warning |  |
| herbicides | Дикогерб Супер | malformed_delimiters | warning |  |
| herbicides | Горгон | malformed_delimiters | warning |  |
| herbicides | МЦПА кислоты (калиевая, натриевая соль) Гербитокс-Л | malformed_delimiters | warning |  |
| herbicides | МЦПА кислоты (смесь диметиламинной, калиевой, натриевой солей) Линтаплант | malformed_delimiters | warning |  |
| herbicides | Линтаплант | malformed_delimiters | warning |  |
| herbicides | Гербитокс | malformed_delimiters | warning |  |
| herbicides | Агритокс | malformed_delimiters | warning |  |
| herbicides | Аметил | malformed_delimiters | warning |  |
| herbicides | Агрошанс | malformed_delimiters | warning |  |
| herbicides | Антарес | malformed_delimiters | warning |  |
| herbicides | Властелин | malformed_delimiters | warning |  |
| herbicides | Гербикс | malformed_delimiters | warning |  |
| herbicides | Момус | malformed_delimiters | warning |  |
| herbicides | Царумин | malformed_delimiters | warning |  |
| herbicides | Момус | malformed_delimiters | warning |  |
| herbicides | Милагро Плюс | malformed_delimiters | warning |  |
| herbicides | Анкор-85 | malformed_delimiters | warning |  |
| herbicides | Тербутилазин + 2,4-Д кислота (2-этилгексиловый эфир) + клопиралид (2-этилгексиловый эфир) + никосульфурон Корнеги Плюс | malformed_delimiters | warning |  |
| herbicides | Тербутилазин + 2,4-Д кислота (2-этилгексиловый эфир) + никосульфурон Корнеги | malformed_delimiters | warning |  |
| herbicides | Зеагран 350 | malformed_delimiters | warning |  |
| herbicides | Камаро | malformed_delimiters | warning |  |
| herbicides | Флорасулам + 2,4-Д кислоты (2-этилгексиловый эфир) Премьера | malformed_delimiters | warning |  |
| herbicides | Ассолюта | malformed_delimiters | warning |  |
| herbicides | Флекс | malformed_delimiters | warning |  |
| fungicides | БФТИМ КС-2 | repeated_fragment | error | automatic parser dedupe: 1х10⁹ КОЕ / Мл Bacillus amyloliquefaciens КС - 2 |
| fungicides | Биокомпозит-Про | malformed_delimiters | warning |  |
| fungicides | Бисолбицид | repeated_fragment | error | automatic parser dedupe: 0,108 КОЕ / Мл Bacillus subtilis, штамм ВL01 |
| fungicides | Кагатник | malformed_delimiters | warning |  |
| fungicides | Фитолекарь | malformed_delimiters | warning |  |
| insecticides | Инсетим | malformed_delimiters | warning |  |
| insecticides | Биостоп | malformed_delimiters | warning |  |
| insecticides | Клотиамет Дуо | malformed_delimiters | warning |  |
| insecticides | Доктор Харвест Форте Про | repeated_fragment | error | automatic parser dedupe: (30 г/л Пиретрины натуральные масляный экстракт) |
| insecticides | Фипроксам | malformed_delimiters | warning |  |
| seed-treatments | Респекта | malformed_delimiters | warning |  |
| seed-treatments | БФТИМ КС-2 | repeated_fragment | error | automatic parser dedupe: (1х10⁹ КОЕ / Мл Bacillus amyloliquefaciens КС - 2) |
| seed-treatments | Бисолбицид | repeated_fragment | error | automatic parser dedupe: (0,108 КОЕ / Мл Bacillus subtilis, штамм ВL01) |
| seed-treatments | Бактофит | malformed_delimiters | warning |  |
| seed-treatments | Бактофит | malformed_delimiters | warning |  |
| seed-treatments | Метабактерин | malformed_delimiters | warning |  |
| seed-treatments | Протект Комби | joined_known_substances;repeated_fragment;unresolved_concentration | error | automatic parser dedupe: (48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + 37,5 г/л Тебуконазол); unresolved concentration: протиоконазол |
| seed-treatments | Фипроксам | malformed_delimiters | warning |  |
