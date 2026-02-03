# FM Review System

Система из 9 AI-агентов для полного жизненного цикла Функциональных Моделей (ФМ) проектов 1С: создание, аудит, миграция в Notion, визуализация ePC в Miro.

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
| 6 | Presenter | Презентации, Notion, Miro | `/present`, `/auto` |
| 7 | Migrator | Word → Notion (5 БД) | `/migrate`, `/validate` |
| 8 | EPC Designer | ePC-диаграммы в Miro | `/epc`, `/epc-validate` |

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
Agent 7 (Migrator)    → Word → Notion (5 БД + страницы)
       ↓
Agent 8 (EPC Designer)→ ePC в Miro (embed → Notion)
       ↓
Agent 6 (Presenter)   → финальная презентация
```

Agent 3 (Defender) вызывается по запросу при получении замечаний.

Каждый агент поддерживает `/auto` — конвейерный режим без интервью, с автоматическим чтением результатов предыдущих агентов.

## Скрипты

| Скрипт | Назначение |
|--------|-----------|
| `orchestrate.sh` | Главное меню — единая точка входа (9 агентов) |
| `new_project.sh` | Создание нового проекта |
| `quality_gate.sh` | Проверка готовности ФМ |
| `fm_version.sh` | Управление версиями ФМ |
| `export_notion.sh` | Экспорт в Notion |
| `export_miro.sh` | Экспорт ePC в Miro |
| `agent[0-5]_*.sh` | Интервью для агентов 0-5 |
| `agent7_migrate.sh` | Интервью для миграции Word → Notion |
| `agent8_epc.sh` | Интервью для ePC-диаграмм в Miro |

## Структура проекта

```
fm-review-system/
├── CLAUDE.md           ← Правила для всех агентов (9 агентов)
├── AGENT_[0-8]_*.md    ← Инструкции агентов
├── PROMPTS.md          ← Промпты для копирования
├── DOCX_EDIT_SKILL.md  ← Инструкции по редактированию DOCX
├── CHAT_CONTEXT.md     ← Подробный контекст всех чатов
├── TODOS.md            ← Реалтайм-трекер задач
├── schemas/            ← JSON-схемы Notion БД
├── templates/          ← Шаблоны Notion-страниц
├── workflows/          ← Сквозные сценарии (create, migrate, review, update, export)
├── scripts/            ← Bash-скрипты (gum)
│   ├── lib/common.sh   ← Общие функции
│   └── ...
├── PROJECT_[NAME]/     ← Проекты с ФМ
│   ├── FM_DOCUMENTS/   ← Все версии ФМ
│   ├── AGENT_*/        ← Результаты агентов
│   └── tools/NET/      ← .NET OpenXML для DOCX
└── ...
```

## Принципы

- **Скорость > Контроль**: контроль не должен тормозить продажи
- **Умный контроль**: авторправила вместо ручных согласований
- **Молчание = согласие**: для позитивных сделок, отказ для негативных
- **Дефолты на все**: таймауты, действия по умолчанию, эскалации
- **Нулевой ручной труд**: `/auto` режим, конвейер, автоэкспорт
