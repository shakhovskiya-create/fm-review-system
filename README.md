# FM Review System

Система из 9 AI-агентов для полного жизненного цикла Функциональных Моделей (ФМ) проектов 1С: создание, аудит, публикация в Confluence, визуализация ePC в Miro.

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
| 6 | Presenter | Презентации, Confluence, Miro | `/present`, `/auto` |
| 7 | Publisher | Управление ФМ в Confluence | `/publish`, `/verify` |
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
Agent 7 (Publisher)   → обновление ФМ в Confluence
       ↓
Agent 8 (EPC Designer)→ ePC в Miro (embed → Confluence)
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
| `export_confluence.sh` | Экспорт в Confluence |
| `export_miro.sh` | Экспорт ePC в Miro |
| `agent[0-5]_*.sh` | Интервью для агентов 0-5 |
| `agent7_publish.sh` | Интервью для управления ФМ в Confluence |
| `agent8_epc.sh` | Интервью для ePC-диаграмм в Miro |

## Структура проекта

```
fm-review-system/
├── CLAUDE.md           ← Правила для всех агентов (9 агентов)
├── AGENT_[0-8]_*.md    ← Инструкции агентов
├── PROMPTS.md          ← Промпты для копирования
├── CONFLUENCE_REQUIREMENTS.md ← Требования к Confluence
├── CHAT_CONTEXT.md     ← Подробный контекст всех чатов
├── TODOS.md            ← Реалтайм-трекер задач
├── schemas/            ← JSON-схемы Confluence
├── templates/          ← Шаблоны Confluence-страниц
├── workflows/          ← Сквозные сценарии (create, migrate, review, update, export)
├── scripts/            ← Bash-скрипты (gum)
│   ├── lib/common.sh   ← Общие функции
│   └── ...
├── PROJECT_[NAME]/     ← Проекты с ФМ
│   ├── CONFLUENCE_PAGE_ID ← ID страницы ФМ в Confluence
│   ├── AGENT_*/        ← Результаты агентов
│   └── CHANGES/        ← Логи изменений
└── ...
```

## Принципы

- **Скорость > Контроль**: контроль не должен тормозить продажи
- **Умный контроль**: авторправила вместо ручных согласований
- **Молчание = согласие**: для позитивных сделок, отказ для негативных
- **Дефолты на все**: таймауты, действия по умолчанию, эскалации
- **Нулевой ручной труд**: `/auto` режим, конвейер, автоэкспорт
