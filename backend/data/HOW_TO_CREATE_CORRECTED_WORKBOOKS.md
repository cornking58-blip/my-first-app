# Как создать исправленные Excel-копии

Этот репозиторий не хранит готовые исправленные `.xlsx` файлы, потому что это бинарные файлы: их трудно проверять в Pull Request, и GitHub/Codex может блокировать такой PR.

Вместо этого в репозитории хранится скрипт-рецепт. Он берёт оригинальные Excel-файлы, применяет текстовый отчёт исправлений и создаёт исправленные копии у вас локально.

## Как запустить

Из корня проекта выполните:

```bash
python backend/create_corrected_workbooks.py
```

## Где появятся файлы

По умолчанию исправленные файлы появятся в папке:

```text
corrected_workbooks/
```

Ожидаемые файлы:

```text
corrected_workbooks/fungicides_raw_FINAL_corrected.xlsx
corrected_workbooks/herbicides_raw_FINAL_checked_corrected.xlsx
corrected_workbooks/insecticides_raw_FINAL_v2_corrected.xlsx
corrected_workbooks/seed_treatments_FINAL_v2_corrected.xlsx
```

Если нужно выбрать другую папку, используйте:

```bash
python backend/create_corrected_workbooks.py --output-dir my_corrected_files
```

## Важно

- Оригинальные Excel-файлы не изменяются и не перезаписываются.
- Скрипт создаёт только копии с исправлениями.
- Неизвестные концентрации не придумываются. Например, у `Протект Комби` концентрация `протиоконазол` остаётся нерешённой.
- Сгенерированные `.xlsx` файлы специально не хранятся в GitHub и не должны попадать в коммит.
- Папка `corrected_workbooks/` добавлена в `.gitignore`, чтобы случайно не закоммитить бинарные Excel-файлы.
