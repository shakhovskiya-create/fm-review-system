# Общие правила для всех агентов (0-15)

> Краткая выжимка. Детали: `.claude/rules/` (загружаются автоматически по контексту).

## Коммуникация
1. **Вопросы** = AskUserQuestion. Варианты + рекомендация + "Другое".
2. **Автор** = "Шаховский А.С." ВСЕГДА. НИКОГДА: Agent, Claude, GPT, ИИ, AI, Bot, LLM.

## Confluence = единственный источник ФМ
3. ВСЕ агенты ЧИТАЮТ ФМ из Confluence. Правки — только Agent 7 (PUT).
   MCP-инструменты: `.claude/rules/confluence-mcp.md`. Fallback: REST API + `confluence_utils.py`.
4. **Версия ФМ**: проверять через `confluence_get_page`. Формат X.Y.Z.
5. **Инкремент**: Патч (Z) = исправления, Минор (Y) = новые разделы, Мажор (X) = переделка.
   Если дата последней строки истории = сегодня — дополнить, иначе Z+1.

## Формат и текст
6. Дефис (-) не тире, "е" не "ё", русский без англицизмов. Тест: "Менеджер продаж это поймет?"
7. **Структуру** ФМ менять нельзя, содержание — можно.
8. **XHTML**: заголовки `rgb(255,250,230)`, копировать стили соседних строк, TOC в `expand`.
9. **Безопасная замена**: ТОЛЬКО в мета-блоке (первые 500 символов). Запрещено replace_all для версий/дат.

## Процесс /apply
10. Показать план (Где-Было-Станет) → AskUserQuestion → Интегрировать → Обновить мета + историю.
11. **Верификация**: после PUT → GET → проверить отсутствие старых + наличие новых значений.
12. **CHANGES.md**: при /apply создавать `projects/PROJECT_[NAME]/CHANGES/FM-[NAME]-v[X.Y.Z]-CHANGES.md`.

## Артефакты
13. Результаты в `projects/PROJECT_[NAME]/AGENT_X_[ROLE]/`. Не хранить в корне.
14. **JSON-сайдкар** `_summary.json`: обязателен. Поля: agent, command, timestamp, fmVersion, project, status. Схема: `schemas/agent-contracts.json`.
15. **_findings.json** (Agent 1,2,4): `{"findings": [{"id", "severity", "category", "fmSection", "description", "recommendation"}]}`.
16. **Автосохранение**: после каждой команды → `PROJECT_CONTEXT.md`. Не спрашивать.

## Governance
17. При старте: прочитать AGENT_PROTOCOL.md, PROJECT_CONTEXT.md, WORKPLAN.md. Паттерны ошибок → `.patches/`.
18. **Публикация**: FM/TS/ARC/TC/RPT документы. Существующая страница → обновить, НЕ дубликат.
19. **Конфликты**: приоритет Agent 1 > 5 > 2. Тип H (конфликт ролей) → AskUserQuestion.
20. **Валидация /auto**: обязательные ключи: project, pageId, fmVersion.

## Качество
21. **MAKE NO MISTAKES.** Перепроверяй факты, вычисления, код. Точность > скорость.
22. **Smoke-тесты**: обязательны перед сдачей. Подробнее: `.claude/rules/smoke-testing.md`.
23. **DoD**: обязателен при закрытии issue. Подробнее: `.claude/rules/dod.md`.

## Workflow & Memory
24. **Plan → Implement → Fix**: подробнее `.claude/rules/agent-workflow.md`.
25. **Knowledge Graph (Memory MCP)**: `mcp__memory__search_nodes` при старте, `mcp__memory__add_observations` при завершении. Правила KG:
    - **KG-1**: Включай ISO-дату в наблюдения: `[2026-02-27] Finding: ...`
    - **KG-2**: Записывай ТОЛЬКО: audit findings (CRIT/HIGH), решения (что+почему), версии ФМ, блокеры
    - **KG-3**: НЕ записывай: промежуточные шаги, текст ФМ, полные отчёты (используй файлы)
    - **KG-4**: Решения = отдельные сущности: `decision_<topic>` с entityType `decision`
    - **KG-5**: Связи версий: используй `SUPERSEDES` для цепочек версий ФМ
    - Подробнее: `.claude/rules/knowledge-graph.md`
25a. **Graphiti (общий граф с CIO-assistant)**: `mcp__graphiti__search_nodes` / `mcp__graphiti__search_memory_facts` для поиска, `mcp__graphiti__add_memory` для записи.
    - **group_id**: `ekf-shared` — общий для fm-review-system и cio-assistant
    - **Записывай**: факты о проекте, решения, версии ФМ, audit findings, изменения архитектуры
    - **Не записывай**: промежуточные шаги, полные тексты документов
    - **Формат source**: `text` для текста, `json` для структурированных данных
    - **CIO-assistant читает наши данные** — пиши понятно для стороннего контекста
26. **GitHub Issues**: подробнее `.claude/rules/agent-workflow.md`.
29. **Декомпозиция**: задача с 2+ шагами → разбей на подзадачи (`--parent N`). 1 issue = 1 deliverable. Подробнее: `.claude/rules/agent-workflow.md`.
31. **ЗАПРЕТ `Closes/Fixes/Resolves #N` в коммитах.** GitHub автозакрывает issues при push — это обходит DoD.
    - В commit message используй **`Refs #N`** (ссылка без закрытия)
    - Закрывай ТОЛЬКО через: `scripts/gh-tasks.sh done <N> --comment "...DoD..."`
    - Hook `guard-issue-autoclose.sh` заблокирует коммит с `Closes #N`
    - CI workflow `dod-check.yml` переоткроет issue если DoD отсутствует

## Kafka-интеграция
30. **Kafka** — шина обмена данными между 1С и Go-сервисами. Все dev-агенты (11-15) обязаны учитывать.
    - Архитектура: `1С → Outbox → HTTP Gateway → Kafka → Go consumers`
    - Топики: `1c.<domain>.<event>.v<N>`, `cmd.*`, `evt.*`, `*.dlq`, `*.retry.*`
    - Подробнее: `knowledge-base/integrations.md` (раздел TO BE)

## База знаний компании
27. **`knowledge-base/`** — справочник о компании, проектах, процессах EKF. Читай при необходимости:
    - `company-profile.md` — о компании, команды, системы
    - `1c-landscape.md` — ландшафт 1С: 12 баз, версии, ключевые документы и регистры
    - `project-sbs.md` — проект «Себестоимость»: 9 ЧТЗ, формулы НПСС, объекты
    - `project-shpmnt-profit.md` — наша ФМ: пороги, SLA, связь с SBS
    - `business-processes.md` — бизнес-процессы: О9 продажи, О2 ценообразование, закупки
    - `integrations.md` — интеграции между системами (AS IS и TO BE)
    - `teams.md` — продуктовые команды ДИТ
    - `infrastructure.md` — серверы 1С, DWH (Kafka/Airflow/Hasura), бэкапы, целевая архитектура
    - `company-org-ldap.md` — оргструктура компании из AD: руководство, департаменты, ИТ-команды
    - `confluence-index.md` — справочник page ID для Confluence MCP: spaces EKF WIKI и EKF-SUPPORT
    - `security.md` — безопасность: ИБ-команда, 2FA, ПДн, CIS Controls v8, bug bounty
28. **Когда читать KB:** при аудите (совместимость с SBS), при проектировании (интеграции, инфраструктура, безопасность), при UX-проверке (бизнес-процессы), при разработке (серверы, базы, Kafka-топики), при публикации (page ID из confluence-index.md).

## 5-уровневый поиск информации
32. **Иерархия поиска** — 5 инструментов в синергии, от быстрого к глубокому:
    | # | Инструмент | Что ищем | Когда |
    |---|-----------|---------|------|
    | 1 | **KB файлы** (`Read knowledge-base/*.md`) | Точный lookup: компания, проекты, интеграции | Знаешь какой файл нужен |
    | 2 | **Local RAG** (`mcp__local-rag__query_documents`) | Семантический поиск по тексту KB | Не знаешь где именно, ищешь по смыслу |
    | 3 | **Graphiti** (`mcp__graphiti__search_nodes/facts`) | Сущности, связи, хронология, решения | Нужны связи между объектами |
    | 4 | **MCP memory** (`mcp__memory__search_nodes`) | Оперативные заметки между сессиями | Нужен контекст прошлых решений агентов |
    | 5 | **Confluence** (`confluence_search/get_page`) | Свежие данные ФМ, комментарии бизнеса | Нужна актуальная версия ФМ |
    - **Правило каскада**: начинай с уровня 1, спускайся ниже если не нашёл
    - **Синергия**: RAG даёт точный текст, Graphiti — связи и историю, Memory — решения агентов, Confluence — актуальную ФМ
    - **Пример**: "Какой порог маржи?" → RAG найдёт цифру в KB → Graphiti покажет кто и когда решил → Memory покажет что агент 1 это проверял

33. **Запись в память — ОБЯЗАТЕЛЬНО при завершении работы.** Каждый агент перед завершением:
    1. **Graphiti** (`mcp__graphiti__add_memory`): записать ключевые findings, решения, метрики. Формат: текстовый эпизод с project name, agent, command, результаты. group_id = `ekf-shared`.
    2. **MCP memory** (`mcp__memory__add_observations`): обновить entity проекта — статус, версия, ключевые цифры.
    - **Что записывать:** findings (CRIT/HIGH обязательно, MEDIUM/LOW — сводку), решения (что + почему), метрики (counts, coverage, estimate), вердикты (APPROVED/REJECTED).
    - **Что НЕ записывать:** полный текст ФМ (читай из Confluence), промежуточные шаги, содержимое файлов (ссылайся на путь).
    - **Страховка:** SubagentStop хук автоматически ставит `_summary.json` в очередь `.graphiti-queue/`. Оркестратор обработает если агент не записал сам.

## WebSearch (агенты 5, 9-15)
29. **WebSearch** — поиск в интернете для актуальных best practices, документации API/фреймворков, примеров реализации.
    - **КОГДА использовать:** при генерации кода/тестов/ТЗ — проверить актуальность API, найти лучшие практики, уточнить синтаксис
    - **КОГДА НЕ использовать:** для поиска внутренней информации EKF (используй KB или Confluence), для фактов которые уже в knowledge-base/
    - **Формат:** конкретный запрос на английском ("Go chi router middleware best practices 2026", НЕ "как написать middleware")
    - **Лимит:** max 3 поиска за сессию, чтобы не тратить время. Если первый поиск дал ответ — не ищи дальше
