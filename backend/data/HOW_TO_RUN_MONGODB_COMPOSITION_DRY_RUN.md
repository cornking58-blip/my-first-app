# Как запустить dry run для исправленных составов MongoDB

**Dry run** — это безопасная проверка “что бы изменилось”. Скрипт читает MongoDB и исправленные Excel-файлы, сравнивает составы препаратов и создаёт отчёты. Он **ничего не записывает в MongoDB**.

## Команда

Из корня проекта выполните:

```bash
python backend/dry_run_corrected_compositions.py
```

Если исправленные Excel-файлы лежат в другой папке:

```bash
python backend/dry_run_corrected_compositions.py --input-dir corrected_workbooks
```

Проверить только одну категорию можно так:

```bash
python backend/dry_run_corrected_compositions.py --category herbicides
```

Если переменная с MongoDB называется не `MONGO_URL`:

```bash
python backend/dry_run_corrected_compositions.py --mongo-uri-env MONGO_URL
```

## Где появятся отчёты

По умолчанию отчёты сохраняются сюда:

- `backend/data/mongodb_composition_dry_run_report.csv` — подробная таблица по каждой строке;
- `backend/data/mongodb_composition_dry_run_summary.md` — короткая сводка с итоговыми числами.

## Что означают статусы

- `exact_match_no_change` — в MongoDB уже такой же состав, менять нечего.
- `safe_update_candidate` — найден ровно один документ, отличается только состав, строка выглядит безопасной для будущего обновления.
- `manual_review_skip` — строка требует ручной проверки, автоматически её трогать нельзя.
- `unresolved_concentration_skip` — у вещества нет надёжной концентрации, автоматически её нельзя придумывать.
- `mongo_record_not_found` — подходящая запись в MongoDB не найдена.
- `ambiguous_mongo_match` — найдено несколько разных вариантов после строгого сопоставления строки применения, скрипт не может безопасно выбрать один.
- `true_duplicate_mongo_records` — найдено больше одной MongoDB-записи, и они одинаковые по важным полям препарата и применения; скрипт не угадывает, какую менять.
- `source_row_not_changed` — исходная строка не была исправлена в Excel, поэтому обновление не предлагается.

CSV-отчёт также показывает диагностические поля `match_strategy`, `matched_by_fields`, `candidate_count_before_narrowing`, `candidate_count_after_narrowing`, `row_identity_signature` и `ambiguity_reason`. Они нужны, чтобы видеть, почему строка была сопоставлена, стала неоднозначной или не была найдена.

## Важная безопасность

Скрипт специально блокирует методы записи MongoDB (`insert_one`, `update_one`, `replace_one`, `delete_many` и другие). Если такой метод случайно будет вызван, dry run упадёт с ошибкой вместо записи данных.
