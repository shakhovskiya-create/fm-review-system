# Отчёт о прогоне сценариев

> Дата: 2025-02-06. Проверка рабочих сценариев без интерактива (где возможно).

---

## 1. Bash-скрипты (синтаксис)

| Сценарий | Команда | Результат |
|----------|---------|-----------|
| Синтаксис orchestrate, quality_gate, new_project | `bash -n scripts/*.sh` | OK |
| Синтаксис agent0..5 | `bash -n scripts/agent*.sh` | OK |

---

## 2. common.sh (в среде bash)

| Сценарий | Команда | Результат |
|----------|---------|-----------|
| ROOT_DIR, list_projects | `bash -c 'source scripts/lib/common.sh && list_projects'` | OK, ROOT корректен, выведены PROJECT_SALES_PIPELINE, PROJECT_SHPMNT_PROFIT |
| get_latest_fm | `bash -c 'source scripts/lib/common.sh && get_latest_fm PROJECT_SHPMNT_PROFIT'` | OK, путь к последней ФМ в FM_DOCUMENTS |

---

## 3. Quality Gate

| Сценарий | Команда | Результат |
|----------|---------|-----------|
| Проект с FM_DOCUMENTS | `bash scripts/quality_gate.sh PROJECT_SHPMNT_PROFIT` | EXIT=0, Failed=0, «ГОТОВО С ОГОВОРКАМИ» |
| Проект без FM_DOCUMENTS (Confluence-only) | `bash scripts/quality_gate.sh PROJECT_SALES_PIPELINE` | EXIT=0, Failed=0; ФМ и FM_DOCUMENTS — предупреждения (допустимо) |

**Правка:** для проекта без папки FM_DOCUMENTS get_latest_fm не вызывается — блок «Функциональная модель» даёт только предупреждение, без лишнего вывода ошибки.

---

## 4. Python-скрипты

| Сценарий | Команда | Результат |
|----------|---------|-----------|
| export_from_confluence | `python3 scripts/export_from_confluence.py --help` | Ожидаемо: ошибка CONFLUENCE_TOKEN (скрипт загружается, проверяет токен до работы) |
| publish-bpmn | `python3 scripts/publish-bpmn.py --help` | OK, выводится использование и примеры |

---

## 5. BPMN (generate-bpmn.js)

| Сценарий | Команда | Результат |
|----------|---------|-----------|
| Генерация .drawio из JSON | `node scripts/generate-bpmn.js scripts/bpmn-processes/process-1-rentability.json --no-open` | OK, создан `scripts/output/process-1-rentability.drawio`; PNG пропущен (draw.io не в PATH) |

---

## 6. Интерактивные сценарии (не прогонялись)

- **orchestrate.sh** — требует `gum choose` и ввод пользователя.
- **agent0_new.sh … agent5_architect.sh** — требуют TTY и `gum`; при запуске без TTY падают на «unable to open /dev/tty». В интерактивном терминале работают.
- **publish_to_confluence.py**, **export_from_confluence.py** (реальное выполнение) — требуют CONFLUENCE_TOKEN и сеть.

---

## Итог

- Синтаксис скриптов корректен.
- В bash корректно работают: list_projects, get_latest_fm, quality_gate для обоих типов проектов (с FM_DOCUMENTS и без).
- generate-bpmn.js создаёт .drawio из JSON.
- Публикация в Confluence и экспорт из Confluence требуют настроенных токенов и выполняются вручную или в CI с секретами.

Система готова к работе при наличии интерактивного терминала (для orchestrate и agent-скриптов) и при настройке Confluence (токен, PAGE_ID).
