# FM Review System

Система из 9 AI-агентов для полного жизненного цикла Функциональных Моделей (ФМ) проектов 1С: создание, аудит, публикация в Confluence, визуализация BPMN-диаграмм в Confluence.

## Быстрый старт

```bash
# Главное меню — единая точка входа
./scripts/orchestrate.sh

# Или напрямую в Claude Code:
# "Прочитай свою роль из AGENT_1_ARCHITECT.md и проведи /audit"
```

## Агенты

| # | Агент | Назначение | Ключевая команда |
|---|-------|-----------|-----------------|
| 0 | Creator | Создание ФМ с нуля | `/new` |
| 1 | Architect | Полный аудит (бизнес + 1С) | `/audit`, `/auto` |
| 2 | Role Simulator | Симуляция ролей / UX | `/simulate-all`, `/auto` |
| 3 | Defender | Защита от замечаний | `/respond-all`, `/auto` |
| 4 | QA Tester | Генерация тест-кейсов | `/generate-all`, `/auto` |
| 5 | Tech Architect | Архитектура + ТЗ + оценка | `/full`, `/auto` |
| 6 | Presenter | Презентации и отчёты | `/present`, `/auto` |
| 7 | Publisher | Управление ФМ в Confluence | `/publish`, `/verify` |
| 8 | BPMN Designer | BPMN-диаграммы в Confluence (drawio) | `/bpmn`, `/bpmn-validate` |

## Pipeline (Конвейер)

```
Agent 0 (Creator)     → создание ФМ
       ↓
Agent 1 (Architect)   → аудит → /apply → ФМ v+0.0.1
       ↓
Agent 2 (Simulator)   → UX → /apply → ФМ v+0.0.1
       ↓
Agent 4 (QA Tester)   → тесты → /apply → ФМ v+0.0.1
       ↓
Agent 5 (Tech Arch)   → архитектура + ТЗ
       ↓
Quality Gate          → проверка готовности
       ↓
Agent 7 (Publisher)   → обновление ФМ в Confluence
       ↓
Agent 8 (BPMN Designer) → BPMN в Confluence (drawio)
       ↓
Agent 6 (Presenter)   → финальная презентация
```

Agent 3 (Defender) вызывается по запросу при получении замечаний.

Каждый агент поддерживает `/auto` — конвейерный режим без интервью, с автоматическим чтением результатов предыдущих агентов.

## Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `orchestrate.sh` | Главное меню - единая точка входа (9 агентов) |
| `new_project.sh` | Создание нового проекта |
| `quality_gate.sh` | Проверка готовности ФМ к передаче |
| `fm_version.sh` | Управление версиями ФМ |
| `agent[0-5]_*.sh` | Интервью для агентов 0-5 |
| `publish_to_confluence.py` | Обновление Confluence (v3.0, lock+backup+retry) |
| `import_docx.py` | Одноразовый импорт DOCX в Confluence (symlink) |
| `export_from_confluence.py` | Экспорт ФМ из Confluence (PDF/Word) |
| `lib/confluence_utils.py` | Confluence API клиент (блокировки, бекапы, retry) |
| `experimental/run_agent.py` | Автономный запуск через Claude API (отложен) |

## Структура проекта

```
fm-review-system/
├── CLAUDE.md              ← Правила для всех агентов (9 агентов)
├── .env.example           ← Шаблон переменных окружения
├── agents/                ← Инструкции агентов (AGENT_0..8_*.md)
├── docs/                  ← Документация (актуальная)
│   ├── PROMPTS.md         ← Промпты для копирования
│   ├── CHANGELOG.md       ← История изменений
│   ├── CONTRACT_CONFLUENCE_FM.md ← Контракт Confluence-only
│   └── archive/           ← Устаревшие документы (НЕ ЧИТАТЬ)
├── schemas/               ← JSON-схемы (agent-contracts.json v2.1)
├── templates/             ← Шаблоны Confluence-страниц
├── workflows/             ← Сквозные сценарии
├── scripts/               ← Скрипты и утилиты
│   ├── publish_to_confluence.py ← Обновление Confluence (v3.0)
│   ├── import_docx.py     ← Импорт DOCX (symlink)
│   ├── lib/confluence_utils.py ← Confluence API клиент
│   ├── lib/common.sh      ← Общие bash-функции
│   └── experimental/      ← Неактивные модули
├── projects/PROJECT_[NAME]/ ← Проекты с ФМ
│   ├── CONFLUENCE_PAGE_ID ← ID страницы ФМ в Confluence
│   ├── AGENT_*/           ← Результаты агентов
│   └── CHANGES/           ← Логи изменений
└── ...
```

## Режимы работы с ФМ

**Confluence — единственный источник правды:** все читают ФМ оттуда, правки вносятся туда (через Agent 7), версионность и дата ведутся в Confluence; при каждом обновлении в таблицу «История версий» на странице добавляется строка с кратким описанием изменений.

- **Confluence-only (рекомендуется):** ФМ живёт только в Confluence. Агенты читают из API; правки в Confluence вносит Agent 7. Версионность — встроенная Confluence; дата в мета-таблице — автоматически при обновлении. Папка `FM_DOCUMENTS/` необязательна; quality_gate при её отсутствии выдаёт предупреждение, но не блокирует.
- **Confluence + FM_DOCUMENTS (legacy):** Дополнительно хранятся копии ФМ в Word/Markdown в `projects/PROJECT_*/FM_DOCUMENTS/`. Удобно для офлайн-экспорта и бэкапов. Источник истины для агентов — по-прежнему Confluence; файлы используются для экспорта и гейта (версия из имени файла).

**Проверка контракта:** чеклист закрепления — `docs/CONTRACT_CONFLUENCE_FM.md`.

**PAGE_ID:** Заполняется в `projects/PROJECT_*/CONFLUENCE_PAGE_ID` (одна строка — число). Скрипты `publish_to_confluence.py`, `export_from_confluence.py`, `publish-bpmn.py` берут PAGE_ID: 1) из файла проекта (если задан env `PROJECT` или аргумент `--project`), 2) из env `CONFLUENCE_PAGE_ID`, 3) fallback только для совместимости.

**Обновление Confluence без docx (Confluence-only):** тело страницы можно обновить так: 1) Agent 7 в Claude Code (ручной шаг), или 2) подготовить XHTML и выполнить `python3 scripts/publish_to_confluence.py --from-file body.xhtml --project PROJECT`. Меню «Управление проектами → Публикация ФМ» при отсутствии docx выводит подсказку с этой командой.

## BPMN-диаграммы

Цепочка: **generate-bpmn.js** (JSON → .drawio + .png) и **publish-bpmn.py** (загрузка .drawio в Confluence как вложение и обновление раздела TO-BE на странице).

```bash
node scripts/generate-bpmn.js scripts/bpmn-processes/process-1.json --no-open
python3 scripts/publish-bpmn.py --all --update-page
```

PAGE_ID для BPMN берётся из `projects/PROJECT/CONFLUENCE_PAGE_ID` при заданном env `PROJECT` или из `.env.local` (CONFLUENCE_PAGE_ID).

## Автономный режим (экспериментальный)

1. Установить зависимости: `pip install -r requirements.txt`
2. Задать переменные: `export ANTHROPIC_API_KEY=sk-...`, `export AUTONOMOUS=1`
3. Запустить полный цикл: `./scripts/orchestrate.sh` - пункт 1, выбрать этапы. Каждый этап будет выполнен через Claude API (`scripts/experimental/run_agent.py`), результат сохранится в `projects/PROJECT/AGENT_X_*/`.
4. При необходимости авто-/apply без запроса пользователя: в контексте проекта или env задать `APPLY_MODE=auto` и `APPLY_SCOPE=critical_high` (или `all`). Агенты 1, 2, 4 тогда применяют правки по этому правилу.

> **Примечание:** `run_agent.py` находится в `scripts/experimental/` (FC-03). Модуль работоспособен, но имеет ограничение max_tokens=8192.

## Принципы

- **Скорость > Контроль**: контроль не должен тормозить продажи
- **Умный контроль**: авторправила вместо ручных согласований
- **Молчание = согласие**: для позитивных сделок, отказ для негативных
- **Дефолты на все**: таймауты, действия по умолчанию, эскалации
- **Нулевой ручной труд**: `/auto` режим, конвейер, автоэкспорт
