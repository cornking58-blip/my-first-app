# Composition review classification summary

This report classifies the 54 suspicious records from the pre-fix full composition audit and compares them with the fresh post-fix audit. Parser changes were limited to generic safe normalization rules; source Excel files were not edited.

## Totals

- Total suspicious records reviewed: 54
- Suspicious count before fixes: 54
- Suspicious count after fixes: 51
- Automatically corrected count before fixes: 7
- Automatically corrected count after fixes: 6
- Remaining manual-review count: 51
- Source-data corruption count: 51
- False-positive warnings removed: 3

## Category counts

- malformed_delimiters: 45
- repeated_fragment: 5
- false_positive_warning: 3
- unresolved_concentration: 1

## Generic fixes implemented

- Preserved multiplication signs inside scientific notation such as `2,5×10⁹` instead of treating them as `+` composition separators.
- Suppressed `malformed_delimiters` warnings caused only by harmless dash-character normalization, for example `антидот – клоквинтосет-мексил`.
- Kept existing exact repeated-fragment deduplication for parser output while leaving warnings on genuinely duplicated source rows.
- Kept existing joined-known-substance splitting only when every split part is an exact known active substance; unresolved concentrations remain `None`.

## Warning counts before and after

| warning code | before | after |
| --- | ---: | ---: |
| joined_known_substances | 1 | 1 |
| malformed_delimiters | 47 | 45 |
| repeated_fragment | 7 | 6 |
| unresolved_concentration | 1 | 1 |

## Top recurring error patterns

- Unbalanced parentheses / truncated source composition text: 45 records remain flagged as `malformed_delimiters`.
- Exact duplicate composition fragments: 5 records remain flagged as `repeated_fragment` because the source text is duplicated, even though parser output is deduplicated.
- Joined known substances sharing one concentration: 1 record remains flagged because the second substance concentration is unresolved.
- Harmless punctuation false positives: 3 records were removed from suspicious results.

## Products still requiring manual review

- herbicides / Фортиссимо / malformed_delimiters / malformed_delimiters
- herbicides / Илион / malformed_delimiters / malformed_delimiters
- herbicides / Репер / malformed_delimiters / malformed_delimiters
- herbicides / Репер Трио / malformed_delimiters / malformed_delimiters
- herbicides / Эфилон / malformed_delimiters / malformed_delimiters
- herbicides / Корнкордия / malformed_delimiters / malformed_delimiters
- herbicides / Агроксон / malformed_delimiters / malformed_delimiters
- herbicides / Дикопур М / malformed_delimiters / malformed_delimiters
- herbicides / Горгон / malformed_delimiters / malformed_delimiters
- herbicides / Дикогерб Супер / malformed_delimiters / malformed_delimiters
- herbicides / Горгон / malformed_delimiters / malformed_delimiters
- herbicides / МЦПА кислоты (калиевая, натриевая соль) Гербитокс-Л / malformed_delimiters / malformed_delimiters
- herbicides / МЦПА кислоты (смесь диметиламинной, калиевой, натриевой солей) Линтаплант / malformed_delimiters / malformed_delimiters
- herbicides / Линтаплант / malformed_delimiters / malformed_delimiters
- herbicides / Гербитокс / malformed_delimiters / malformed_delimiters
- herbicides / Агритокс / malformed_delimiters / malformed_delimiters
- herbicides / Аметил / malformed_delimiters / malformed_delimiters
- herbicides / Агрошанс / malformed_delimiters / malformed_delimiters
- herbicides / Антарес / malformed_delimiters / malformed_delimiters
- herbicides / Властелин / malformed_delimiters / malformed_delimiters
- herbicides / Гербикс / malformed_delimiters / malformed_delimiters
- herbicides / Момус / malformed_delimiters / malformed_delimiters
- herbicides / Царумин / malformed_delimiters / malformed_delimiters
- herbicides / Момус / malformed_delimiters / malformed_delimiters
- herbicides / Милагро Плюс / malformed_delimiters / malformed_delimiters
- herbicides / Анкор-85 / malformed_delimiters / malformed_delimiters
- herbicides / Тербутилазин + 2,4-Д кислота (2-этилгексиловый эфир) + клопиралид (2-этилгексиловый эфир) + никосульфурон Корнеги Плюс / malformed_delimiters / malformed_delimiters
- herbicides / Тербутилазин + 2,4-Д кислота (2-этилгексиловый эфир) + никосульфурон Корнеги / malformed_delimiters / malformed_delimiters
- herbicides / Зеагран 350 / malformed_delimiters / malformed_delimiters
- herbicides / Камаро / malformed_delimiters / malformed_delimiters
- herbicides / Флорасулам + 2,4-Д кислоты (2-этилгексиловый эфир) Премьера / malformed_delimiters / malformed_delimiters
- herbicides / Ассолюта / malformed_delimiters / malformed_delimiters
- herbicides / Флекс / malformed_delimiters / malformed_delimiters
- fungicides / БФТИМ КС-2 / repeated_fragment / repeated_fragment
- fungicides / Биокомпозит-Про / malformed_delimiters / malformed_delimiters
- fungicides / Бисолбицид / repeated_fragment / repeated_fragment
- fungicides / Кагатник / malformed_delimiters / malformed_delimiters
- fungicides / Фитолекарь / malformed_delimiters / malformed_delimiters
- insecticides / Инсетим / malformed_delimiters / malformed_delimiters
- insecticides / Биостоп / malformed_delimiters / malformed_delimiters
- insecticides / Клотиамет Дуо / malformed_delimiters / malformed_delimiters
- insecticides / Доктор Харвест Форте Про / repeated_fragment / repeated_fragment
- insecticides / Фипроксам / malformed_delimiters / malformed_delimiters
- seed-treatments / Респекта / malformed_delimiters / malformed_delimiters
- seed-treatments / БФТИМ КС-2 / repeated_fragment / repeated_fragment
- seed-treatments / Бисолбицид / repeated_fragment / repeated_fragment
- seed-treatments / Бактофит / malformed_delimiters / malformed_delimiters
- seed-treatments / Бактофит / malformed_delimiters / malformed_delimiters
- seed-treatments / Метабактерин / malformed_delimiters / malformed_delimiters
- seed-treatments / Протект Комби / unresolved_concentration / joined_known_substances;repeated_fragment;unresolved_concentration
- seed-treatments / Фипроксам / malformed_delimiters / malformed_delimiters

## Notes

- No active substances, concentrations, or resistance groups were invented.
- No endpoint URLs or frontend files were changed.
- No source Excel files were modified.
