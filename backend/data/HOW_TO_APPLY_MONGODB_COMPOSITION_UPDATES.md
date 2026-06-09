# Как безопасно применить исправления состава в MongoDB

Этот документ — инструкция для начинающего разработчика. Скрипт меняет **только поля состава препарата** и специально защищён от случайного запуска.

## 1. Сначала смените пароль

Перед любыми живыми операциями смените пароль/секрет доступа к MongoDB, если он мог попасть в чат, логи или чужие руки. Никогда не коммитьте пароль в Git.

## 2. Укажите `MONGO_URL`

В терминале задайте переменную окружения. Значение ниже — пример, вместо него нужен реальный Railway MongoDB URL:

```bash
export MONGO_URL='mongodb+srv://USER:PASSWORD@HOST/herbicides_db?retryWrites=true&w=majority'
```

Если база называется не `herbicides_db`, скрипт откажется работать. Это нужно, чтобы случайно не изменить не ту базу.

## 3. Запустите проверку без записи

Без флага `--apply` скрипт ничего не записывает:

```bash
python backend/apply_corrected_compositions.py
```

Ожидаемое поведение: скрипт напишет, что apply mode отключён, выполнит проверки и сделает **0 записей** в MongoDB.

## 4. Запустите реальное применение только после проверки

Живая запись требует сразу два предохранителя: `--apply` и точный текст подтверждения.

```bash
python backend/apply_corrected_compositions.py --apply --confirm APPLY_184_APPROVED_COMPOSITION_UPDATES
```

Скрипт применяет только строки со статусом `safe_update_candidate`. Строки manual review, unresolved concentration и Протект Комби не обновляются.

## 5. Где появится backup

Перед первой записью скрипт создаёт JSON backup в папке:

```text
mongodb_backups/
```

Имя похоже на:

```text
mongodb_backups/composition_backup_YYYYMMDD_HHMMSS.json
```

Backup содержит исходные MongoDB-документы целиком. Это «страховочная копия», чтобы можно было вернуть поля состава назад.

## 6. Как проверить результат

После apply скрипт создаёт локальные отчёты:

```text
backend/data/mongodb_composition_apply_report.csv
backend/data/mongodb_composition_apply_summary.md
```

В summary проверьте:

- сколько документов ожидалось (`expected safe updates`);
- сколько попыток было (`attempted`);
- сколько реально изменено (`modified`);
- что количество документов в коллекциях до/после не изменилось;
- что Протект Комби остался без изменений;
- путь к backup-файлу;
- команду rollback.

Эти отчёты не коммитятся, потому что они генерируются локально и могут содержать данные живой базы.

## 7. Как откатиться

Rollback тоже защищён подтверждением. Подставьте путь к backup-файлу из summary:

```bash
python backend/rollback_corrected_compositions.py --backup-file mongodb_backups/composition_backup_YYYYMMDD_HHMMSS.json --apply --confirm ROLLBACK_COMPOSITION_UPDATES
```

Rollback не удаляет документы. Он восстанавливает только поля состава из backup.

## 8. Какие поля можно менять

Скрипт обновляет только поля состава:

- `active_substances_raw`
- `active_substances` — только если поле уже было в документе
- `composition` — только если поле уже было в документе
- `composition_warnings` — только если поле уже было в документе
- `has_composition_warning` — только если поле уже было в документе

Скрипт не меняет URL endpoint-ов, импорт, цены, нормы расхода, культуры, производителей, регистрации, HRAC/FRAC/IRAC и другие несвязанные поля.
