# Insecticide missing-composition review

## Result

- Workbook rows checked: 3,700
- Importable rows with a product name: 3,608
- Product cards checked: 541
- Cards with an empty `active_substances_raw` source field: 69
- Safely recoverable from an explicit composition in `product_name`: 47
- Still requiring source-data review: 22
- Additional cards with a non-empty biological composition in `КОЕ`, spores, or viral particles: 20

The backend fallback is deliberately limited to insecticide titles containing an explicit numeric concentration and a supported unit (`г/л`, `г/кг`, or `%`). Existing non-empty composition fields always remain authoritative. MongoDB and Excel are not modified.

The 20 biological compositions are preserved unchanged. Supporting biological units in the structured concentration parser is a separate task and is not part of this fix.

## Manual-review cards

- `Биостоп Супер, микроконте (3х10⁶ КОЕ/г Bacillus thuringiensis Hi + 3х10⁶ КОЕ/г Beauveriabassiana BB1)` — `805-01-4071-1`
- `Bacillus thuringiensis, var. kurstaki Z-52(спорово-кристаллический комплекс)` — no registration number
- `Bacillus thuringiensis, var. Thuringiensis, штамм 98` — no registration number
- `Bacillus thuringiensis, var. Thuringiensis, штамм В-501` — no registration number
- `Bacillusthuringiensissubsp. kurstakiZ-52 (споро-кристаллическийкомплекс)` — no registration number
- `Beauveria bassiana + bacillus thuringiensis + streptomycessp.` — no registration number
- `thuringiensis + 10х10⁸ КОЕ/Мл Streptomycessp.)` — no registration number
- `Metarhiziumanisopliae штамм 3873/18Л + beauveriabassiana штамм 119/ЛТ + bacillusthuringiensisvar. thuringiensis штамм БФ/15Л + streptomycessp.` — no registration number
- `17.12.2020 16.12.2030` — no registration number
- `184(026)-01-2445-1/411 30.10.2029` — no registration number
- `18.01.2032` — no registration number
- `03.02.2021 02.02.2031` — no registration number
- `Груп»` — `178-01-2216-1`
- `10.07.2027` — no registration number
- `27.04.2028` — no registration number
- `26.05.2025 25.05.2035` — no registration number
- `г/л Клотианидин)` — no registration number
- `04.08.2028` — no registration number
- `16.01.2034` — no registration number
- `150 г/л Фипронил)` — `866-01-4166-1`
- `31.03.2034` — no registration number
- `Молния Экстра` — no registration number

These entries are not changed automatically because their title does not contain a complete, safely parseable chemical composition or the row is visibly shifted/corrupted.
