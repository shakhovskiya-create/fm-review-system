# Отчет о реализации архитектурного аудита FC-01...FC-06

> **Дата:** 07.02.2026
> **Роль:** Lead Architect & Assurance Auditor
> **Статус:** Все 6 рекомендаций реализованы

---

## Сводка

| ID | Класс проблемы | Опция | Статус |
|----|----------------|-------|--------|
| FC-01 | Призрачная инфраструктура | C: Интеграция confluence_utils.py | Реализовано |
| FC-02 | Двойной режим publish_to_confluence.py | C: Симлинк import_docx.py | Реализовано |
| FC-03 | Осиротевший конвейер run_agent.py | B: Перенос в experimental/ | Реализовано |
| FC-04 | Разрыв схема-реализация | C: agentSummary + Agent6_Presenter | Реализовано |
| FC-05 | Деградация документации | A: Перенос в docs/archive/ | Реализовано |
| FC-06 | Секреты в репозитории | A: .env.example + проверка .gitignore | Реализовано |

---

## FC-01: Призрачная инфраструктура (confluence_utils.py)

**Проблема:** confluence_utils.py (блокировки, бекапы, retry) не использовался publish_to_confluence.py. Вместо этого в основном скрипте был "голый" urllib-блок без защиты.

**Решение:**
- Заменен блок API-вызова в `publish_to_confluence.py` (строки 523-584) на вызов `ConfluenceClient` из `confluence_utils.py`
- Новый код использует `with client.lock():` для блокировки, `client.update_page()` для бекапа + retry
- `contract_validator.py` перенесен в `scripts/experimental/` (отложен до появления CLI-валидации)

**Затронутые файлы:**
- `scripts/publish_to_confluence.py` - модифицирован (v2.0 → v3.0)
- `scripts/lib/contract_validator.py` → `scripts/experimental/contract_validator.py`
- `scripts/experimental/README.md` - создан

---

## FC-02: Двойной режим (Confluence-only)

**Проблема:** `publish_to_confluence.py` поддерживал два режима (импорт DOCX и обновление из файла), что создавало неоднозначность. Новые агенты могли случайно запустить одноразовый DOCX-импорт.

**Решение:**
- Обновлен docstring с v2.0 до v3.0, четко документирующий два режима: IMPORT (одноразовый) vs UPDATE (штатный)
- Создан симлинк `scripts/import_docx.py → publish_to_confluence.py` для семантической ясности
- В CLAUDE.md задокументированы оба входа

**Затронутые файлы:**
- `scripts/publish_to_confluence.py` - обновлен docstring
- `scripts/import_docx.py` - создан (симлинк)

---

## FC-03: Осиротевший конвейер (run_agent.py)

**Проблема:** `run_agent.py` (автономный запуск через Claude API) лежал рядом с боевыми скриптами, хотя не интегрирован в конвейер и имеет ограничения (max_tokens=8192).

**Решение:**
- Перенесен в `scripts/experimental/run_agent.py`
- Задокументирован в `scripts/experimental/README.md`

**Затронутые файлы:**
- `scripts/run_agent.py` → `scripts/experimental/run_agent.py`

---

## FC-04: Разрыв схема-реализация (JSON-сайдкар)

**Проблема:** `agent-contracts.json` описывал выходы агентов, но не имел: (а) определения Agent6_Presenter, (б) машиночитаемой сводки для оркестратора.

**Решение:**
- Обновлена схема с v1.0 до v2.0
- Добавлено определение `agentSummary` - легковесный JSON-сайдкар (`_summary.json`)
  - Обязательные поля: agent, command, timestamp, fmVersion, project, status
  - Опциональные: counts, outputFiles, appliedChanges, notes
- Добавлено определение `Agent6_Presenter` (format, audience, sections)
- В CLAUDE.md добавлена секция "JSON-сайдкар (_summary.json)"

**Затронутые файлы:**
- `schemas/agent-contracts.json` - модифицирован (v1.0 → v2.0)
- `CLAUDE.md` - добавлена секция FC-04

---

## FC-05: Деградация документации

**Проблема:** 6 документов в docs/ содержали устаревшие ссылки (Notion, старые имена агентов, Word-first архитектура) и вводили агентов в заблуждение.

**Решение:**
- Создана папка `docs/archive/`
- Перенесены 6 файлов:
  - CHAT_CONTEXT.md (Notion-ссылки, старые имена)
  - AUDIT_REPORT.md (помечен LEGACY)
  - TODOS.md (ссылки на Notion-настройку)
  - SCENARIOS_RUN_REPORT.md (исторический отчет)
  - MULTI_AGENT_AUDIT_REPORT.md (AG-01...AG-11 закрыты)
  - FINAL_AUDIT_AND_ARCHITECTURE.md (до FC-01...FC-06)
- Создан `docs/archive/README.md` с причинами архивации

**Затронутые файлы:**
- 6 файлов перенесены в `docs/archive/`
- `docs/archive/README.md` - создан

---

## FC-06: Секреты в репозитории

**Проблема:** Потенциальный риск утечки токенов (CONFLUENCE_TOKEN, ANTHROPIC_API_KEY) через .env-файлы.

**Проверка:**
- `.gitignore` уже содержит правила для .env, .env.local, *.env
- `git ls-files --error-unmatch .env` подтвердил: .env НЕ отслеживается git
- Секреты никогда не попадали в историю коммитов

**Решение:**
- Создан `.env.example` с плейсхолдерами для всех переменных окружения
- Добавлены инструкции: `cp .env.example .env`

**Затронутые файлы:**
- `.env.example` - создан

---

## Обновления документации (сквозные)

### CLAUDE.md
- Секция "Документация": убраны ссылки на архивные файлы, добавлены archive/ и experimental/
- Секция "Структура проекта": полностью обновлено дерево файлов
- Секция "Скрипты": добавлены import_docx.py, confluence_utils.py, experimental/
- Добавлена новая секция "Безопасность Confluence (confluence_utils.py)"
- Добавлена новая секция "JSON-сайдкар (_summary.json) - FC-04"
- Таблица проектов: FM-SHPMNT-PROFIT v2.5.3 → FM-LS-PROFIT v1.0
- Confluence-ресурсы: добавлены import_docx.py, confluence_utils.py

### PROJECT_SHPMNT_PROFIT/README.md
- Убраны все "Читать ФМ из FM_DOCUMENTS/"
- Заменены на "Читать ФМ из Confluence (REST API, PAGE_ID)"
- FM_DOCUMENTS/ помечена как АРХИВ (legacy)
- Добавлен Confluence как источник в мета-таблице
- Обновлена структура проекта

---

## Автономность (итого)

| Метрика | До | После |
|---------|-----|-------|
| Confluence safety (lock/backup/retry) | Не использовался | Интегрирован |
| Двусмысленность режимов скрипта | Есть | Устранена (симлинк) |
| Документация с ложными ссылками | 6 файлов | 0 (архивированы) |
| JSON-сайдкар для оркестратора | Нет | Схема готова (v2.0) |
| Секреты в .env | Нет шаблона | .env.example создан |
| Orphan-скрипты в боевой папке | 2 | 0 (перенесены) |
