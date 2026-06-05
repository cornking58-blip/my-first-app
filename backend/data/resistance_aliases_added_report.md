# Resistance aliases added report

Source: `backend/data/unresolved_resistance_aliases_report.csv`

Filter used:

- `confidence = high`
- `recommendation = add alias`
- non-empty `possible_english_candidate`
- English candidate must resolve to an existing resistance record in the scoped system:
  - `herbicides` → HRAC / `herbicide`
  - `fungicides` → FRAC / `fungicide`
  - `insecticides` → IRAC / `insecticide`
  - `seed-treatments` → FRAC first, then IRAC

## Summary

- Unique aliases added to `MANUAL_RU_ALIASES`: **31**
- High-confidence category rows covered by those aliases: **35**
- High-confidence rows skipped: **18**
- Unknown fallback behavior unchanged: `resistance_group_name: "группа не определена"`

## Aliases added by category

### Herbicides / HRAC

| Russian alias | Existing target key | Group |
|---|---:|---|
| Изоксафлютол | isoxaflutole | HRAC 27 |
| карфентразон-этил | carfentrazone_ethyl | HRAC 14 |
| Пендиметалин | pendimethalin | HRAC 3 |
| Пиноксаден | pinoxaden | HRAC 1 |
| Прометрин | prometryn | HRAC 5 |
| пропаквизафоп | propaquizafop | HRAC 1 |
| С-Метолахлор | s_metolachlor | HRAC 15 |
| Темботрион | tembotrione | HRAC 27 |
| тербутилазин | terbuthylazine | HRAC 5 |
| флорасулам | florasulam | HRAC 2 |

### Fungicides / FRAC

| Russian alias | Existing target key | Group |
|---|---:|---|
| Изопиразам | isopyrazam | FRAC 7 |
| Пидифлуметофен | pydiflumetofen | FRAC 7 |
| Фамоксадон | famoxadone | FRAC 11 |
| Фенамидон | fenamidone | FRAC 11 |
| фенпропидин | fenpropidin | FRAC 5 |
| цифлуфенамид | cyflufenamid | FRAC U06 |

### Insecticides / IRAC

| Russian alias | Existing target key | Group |
|---|---:|---|
| Бифентрин | bifenthrin | IRAC 3A |
| Зета-циперметрин | zeta_cypermethrin | IRAC 3A |
| Индоксакарб | indoxacarb | IRAC 22A |
| Малатион | malathion | IRAC 1B |
| Пиметрозин | pymetrozine | IRAC 9B |
| Пиримифос-метил | pirimiphos_methyl | IRAC 1B |
| Спиносад | spinosad | IRAC 5 |
| Спиротетрамат | spirotetramat | IRAC 23 |
| Фипронил | fipronil | IRAC 2B |
| Хлорпирифос | chlorpyrifos | IRAC 1B |
| Циантранилипрол | cyantraniliprole | IRAC 28 |
| циперметрин | cypermethrin | IRAC 3A |
| Эмамектин бензоат | emamectin_benzoate | IRAC 6 |
| Эсфенвалерат | esfenvalerate | IRAC 3A |

### Seed treatments / FRAC then IRAC

These rows are covered by the scoped fungicide/insecticide aliases above, because seed-treatment lookup checks FRAC first and then IRAC.

| Russian alias | Existing target key | Group |
|---|---:|---|
| Бифентрин | bifenthrin | IRAC 3A |
| пенфлуфен | penflufen | FRAC 7 |
| Пиримифос-метил | pirimiphos_methyl | IRAC 1B |
| Фипронил | fipronil | IRAC 2B |
| Циантранилипрол | cyantraniliprole | IRAC 28 |

## High-confidence rows skipped

Rows below matched the `high` + `add alias` filter, but were not added because the candidate did not resolve to an existing record in the scoped system. Adding them would require guessing a different category, different spelling, or a different mechanism, so they were left unknown.

| Category | Russian alias | CSV candidate | Reason |
|---|---|---|---|
| herbicides | Бентазон | bentazone | No exact HRAC target for the CSV candidate in current resistance data. |
| herbicides | Клотианидин | clothianidin | Candidate resolves only outside the herbicide/HRAC scope. |
| herbicides | лямбда-цигалотрин | lambda-cyhalothrin | Candidate resolves only outside the herbicide/HRAC scope. |
| herbicides | Пираклостробин | pyraclostrobin | Candidate resolves only outside the herbicide/HRAC scope. |
| herbicides | феноксапроп-П-этил | fenoxaprop-P-ethyl | No exact HRAC target for the CSV candidate in current resistance data. |
| herbicides | Флуазифоп-П-бутил | fluazifop-P-butyl | No exact HRAC target for the CSV candidate in current resistance data. |
| fungicides | Эмамектин бензоат | emamectin benzoate | Candidate resolves only outside the fungicide/FRAC scope. |
| insecticides | Азоксистробин | azoxystrobin | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Дифеноконазол | difenoconazole | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Ипродион | iprodione | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Протиоконазол | prothioconazole | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Прохлораз | prochloraz | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | седаксан | sedaxane | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Тебуконазол | tebuconazole | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | тритиконазол | triticonazole | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Флудиоксонил | fludioxonil | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Флутриафол | flutriafol | Candidate resolves only outside the insecticide/IRAC scope. |
| insecticides | Ципроконазол | cyproconazole | Candidate resolves only outside the insecticide/IRAC scope. |
