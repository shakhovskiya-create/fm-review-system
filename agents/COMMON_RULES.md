# Общие правила для всех агентов (0-8)

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
19. **Конфликты**: приоритет Agent 1 > 5 > 2 > 4. Тип H (конфликт ролей) → AskUserQuestion.
20. **Валидация /auto**: обязательные ключи: project, pageId, fmVersion.

## Качество
21. **MAKE NO MISTAKES.** Перепроверяй факты, вычисления, код. Точность > скорость.
22. **Smoke-тесты**: обязательны перед сдачей. Подробнее: `.claude/rules/smoke-testing.md`.
23. **DoD**: обязателен при закрытии issue. Подробнее: `.claude/rules/dod.md`.

## Workflow & Memory
24. **Plan → Implement → Fix**: подробнее `.claude/rules/agent-workflow.md`.
25. **Knowledge Graph + Episodic Memory**: подробнее `.claude/rules/knowledge-graph.md`.
26. **GitHub Issues**: подробнее `.claude/rules/agent-workflow.md`.
