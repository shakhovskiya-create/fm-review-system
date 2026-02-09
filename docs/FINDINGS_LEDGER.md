# Реестр находок (Findings Ledger)

> **Назначение:** Единственный источник правды по всем находкам аудитов системы.
> **Правила:** CLOSED и ACCEPTED_RISK повторно НЕ поднимаются. Новая запись = новый класс проблемы или доказанная регрессия.
> **Обновление:** Lead Architect дописывает новые записи в конец таблицы. Статус обновляется на месте.

---

## Статусы

| Статус | Значение |
|--------|----------|
| OPEN | Обнаружена, не решена |
| CLOSED | Решена и верифицирована |
| ACCEPTED_RISK | Принят риск, обоснование зафиксировано |

---

## AG-01...AG-11 (Первый аудит, закрыты 06.02.2026)

| ID | Серьезность | Класс проблемы | Статус | Дата закрытия | Решение |
|----|-------------|----------------|--------|---------------|---------|
| AG-01 | H | Несогласованность имен агентов | CLOSED | 06.02.2026 | Переименование агентов 7/8 |
| AG-02 | M | FM_DOCUMENTS обязателен в quality_gate | CLOSED | 06.02.2026 | Сделан опциональным |
| AG-03 | M | Устаревшие ссылки на Notion | CLOSED | 06.02.2026 | Замена на Confluence |
| AG-04 | L | Контекст интервью - глобальный файл | CLOSED | 06.02.2026 | Per-project контекст |
| AG-05 | M | PROJECT_CONTEXT.md в docs/ вместо проекта | CLOSED | 06.02.2026 | Приоритет проектного файла |
| AG-06 | L | CHANGES/ отсутствует в шаблоне проекта | CLOSED | 06.02.2026 | Добавлена в new_project.sh |
| AG-07 | M | Статус замечаний: только английский | CLOSED | 06.02.2026 | Добавлен русский паттерн |
| AG-08 | H | Word как источник правды | CLOSED | 06.02.2026 | Confluence-only контракт |
| AG-09 | M | Нет export_from_confluence.py | CLOSED | 06.02.2026 | Скрипт создан |
| AG-10 | L | Устаревшие TODO в коде | CLOSED | 06.02.2026 | Очистка |
| AG-11 | M | quality_gate не учитывает Agent 7/8 | CLOSED | 06.02.2026 | Обновлен |

---

## AG-12...AG-15 (Второй аудит, 06.02.2026)

| ID | Серьезность | Класс проблемы | Статус | Дата закрытия | Решение |
|----|-------------|----------------|--------|---------------|---------|
| AG-12 | M | Меню 11.4 падает для Confluence-only | CLOSED | 09.02.2026 | Добавлена ветка с подсказкой --from-file (уже в коде publish_to_confluence.py v3.0) |
| AG-13 | L | Библиотеки lib без использования | CLOSED | 07.02.2026 | FC-01: confluence_utils интегрирован; contract_validator в experimental/ |
| AG-14 | L | Глобальный pipeline state | CLOSED | 09.02.2026 | Per-project через get_pipeline_state_file(); убран глобальный fallback |
| AG-15 | M | Нет режима обновления без docx | CLOSED | 09.02.2026 | Режим --from-file в publish_to_confluence.py v3.0 уже реализован |

---

## FC-01...FC-06 (Архитектурный аудит, 07.02.2026)

| ID | Серьезность | Класс проблемы | Вариант | Статус | Дата закрытия | Решение |
|----|-------------|----------------|---------|--------|---------------|---------|
| FC-01 | H | Призрачная инфраструктура (confluence_utils) | C | CLOSED | 07.02.2026 | Интеграция в publish_to_confluence.py v3.0 |
| FC-02 | M | Двойной режим publish скрипта | C | CLOSED | 07.02.2026 | Симлинк import_docx.py |
| FC-03 | L | Осиротевший run_agent.py | B | CLOSED | 07.02.2026 | Перенос в experimental/ |
| FC-04 | M | Разрыв схема-реализация (agentSummary) | C | CLOSED | 07.02.2026 | Схема v2.0 с agentSummary |
| FC-05 | M | Деградация документации | A | CLOSED | 07.02.2026 | Перенос в docs/archive/ |
| FC-06 | L | Секреты в репозитории | A | CLOSED | 07.02.2026 | .env.example + проверка .gitignore |

---

## FC-07...FC-12 (Третий аудит, 09.02.2026)

| ID | Серьезность | Класс проблемы | Вариант | Статус | Дата закрытия | Решение |
|----|-------------|----------------|---------|--------|---------------|---------|
| FC-07 | M | Призрачный контракт _summary.json | A | CLOSED | 09.02.2026 | quality_gate.sh проверяет _summary.json; инструкции агентов обновлены; CLAUDE.md документирован |
| FC-08 | H | Нет принудительного Quality Gate | C | CLOSED | 09.02.2026 | quality_gate.sh v2.0 с --reason; orchestrate.sh вызывает Gate перед Agent 7; CRITICAL блокирует |
| FC-09 | H | Недетерминированный /auto | C | CLOSED | 09.02.2026 | contextSchema в agent-contracts.json v2.1; обязательные: project, pageId, fmVersion; опциональные с дефолтами |
| FC-10 | M | Разрыв трассируемости | A | CLOSED | 09.02.2026 | traceabilityMatrix/traceabilityEntry в agent-contracts.json v2.1; quality_gate.sh проверяет; Agent 4 инструктирован |
| FC-11 | M | Неопределенная семантика версий | C | CLOSED | 09.02.2026 | fm_version.sh auto-patch для Z; bump для Y/X; CLAUDE.md документирован |
| FC-12 | M | Риск нарушения единственного писателя | B | CLOSED | 09.02.2026 | _audit_log() в confluence_utils.py v1.1; JSONL в .audit_log/; quality_gate.sh проверяет; Agent 7 инструктирован |

---

## FC-13...FC-21 (Четвертый аудит, 09.02.2026)

| ID | Серьезность | Класс проблемы | Вариант | Статус | Дата закрытия | Решение |
|----|-------------|----------------|---------|--------|---------------|---------|
| FC-13 | H | _summary.json отсутствует в агентах 3, 6, 8 | A | CLOSED | 09.02.2026 | Добавлены секции JSON-сайдкар в AGENT_3_DEFENDER.md, AGENT_6_PRESENTER.md, AGENT_8_BPMN_DESIGNER.md |
| FC-14 | H | Quality Gate ищет atlassian.net вместо ekf.su | A | CLOSED | 09.02.2026 | Секция 9 quality_gate.sh переписана: проверяет CONFLUENCE_PAGE_ID файл + URL ekf.su; добавлена проверка BPMN |
| FC-15 | H | Битые пути в fm_version.sh (нет /projects/) | A | CLOSED | 09.02.2026 | Исправлены 4 пути: list, diff, bump, log — добавлен /projects/ |
| FC-16 | H | PIPELINE_NAMES не совпадает с gum choice | A | CLOSED | 09.02.2026 | "Тесты" заменено на "Тест-кейсы" в PIPELINE_NAMES для grep-совместимости |
| FC-17 | M | Agent 7 использует requests вместо confluence_utils | A | CLOSED | 09.02.2026 | Пример кода обновлен на ConfluenceClient из confluence_utils.py |
| FC-18 | M | APPLY_MODE отсутствует в агентах 0, 3, 5 | A | CLOSED | 09.02.2026 | Добавлен блок APPLY_MODE/APPLY_SCOPE в AGENT_0, AGENT_3, AGENT_5 |
| FC-19 | M | Устаревшие данные (Notion/Miro, v2.0) | A | CLOSED | 09.02.2026 | PROJECT_CONTEXT: Notion/Miro заменены на Confluence/BPMN; CLAUDE.md/README: v2.0→v2.1; CONTRACT: раздел 8 обновлен |
| FC-20 | M | agent_name не передается в publish_to_confluence.py | A | CLOSED | 09.02.2026 | Добавлен agent_name="Agent7_Publisher" в вызов update_page() |
| FC-21 | L | Мелкие правки документации | A | CLOSED | 09.02.2026 | PROMPTS.md: убраны фантомные agent7_publish.sh/agent8_bpmn.sh; READINESS_CHECK/CONTRACT: дата 2025→2026 |

---

## FC-22 (Пятый аудит, 09.02.2026)

| ID | Серьезность | Класс проблемы | Вариант | Статус | Дата закрытия | Решение |
|----|-------------|----------------|---------|--------|---------------|---------|
| FC-22 | H | run_agent.py: one-shot API без инструментов, конвейер не автоматизирован | A | CLOSED | 09.02.2026 | Переписан на claude -p CLI с полным доступом к инструментам; перенесен из experimental/ в scripts/; добавлен --pipeline режим |

---

## Правила ведения реестра

1. **Новая запись** = только новый класс проблем или доказанная регрессия
2. **Закрытие** = реализация + верификация (GET после PUT, проверка отсутствия старых/наличия новых значений)
3. **ACCEPTED_RISK** = обоснование записано в колонке "Решение"
4. **НЕ переоткрывать** CLOSED/ACCEPTED_RISK без доказательства регрессии
5. **Нумерация**: AG-XX (аудит агентов), FC-XX (архитектурный аудит)
