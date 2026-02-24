# Реестр субагентов и маршрутизация

12 агентов зарегистрированы как Claude Code subagents в `.claude/agents/`:

| Subagent | Модель | Протокол |
|----------|--------|----------|
| `helper-architect` | opus | `agents/ORCHESTRATOR_HELPER.md` |
| `agent-0-creator` | opus | `agents/AGENT_0_CREATOR.md` |
| `agent-1-architect` | opus | `agents/AGENT_1_ARCHITECT.md` |
| `agent-2-simulator` | opus | `agents/AGENT_2_ROLE_SIMULATOR.md` |
| `agent-3-defender` | opus | `agents/AGENT_3_DEFENDER.md` |
| `agent-4-qa-tester` | sonnet | `agents/AGENT_4_QA_TESTER.md` |
| `agent-5-tech-architect` | opus | `agents/AGENT_5_TECH_ARCHITECT.md` |
| `agent-6-presenter` | opus | `agents/AGENT_6_PRESENTER.md` |
| `agent-7-publisher` | opus | `agents/AGENT_7_PUBLISHER.md` |
| `agent-8-bpmn-designer` | sonnet | `agents/AGENT_8_BPMN_DESIGNER.md` |
| `agent-9-se-go` | opus | `agents/AGENT_9_SE_GO.md` |
| `agent-10-se-1c` | opus | `agents/AGENT_10_SE_1C.md` |

Каждый subagent при запуске читает свой протокол из `agents/` и `agents/COMMON_RULES.md`.

Шаблон для создания нового агента: `docs/AGENT_TEMPLATE.md`

## Маршрутизация (Natural Language → Agent)

| Фраза | Агент | Команда |
|-------|-------|---------|
| "Создай ФМ", "Новая ФМ", "Опиши процесс" | Agent 0 (Creator) | /new |
| "Запусти аудит", "Проверь ФМ", "Проблемы в ФМ" | Agent 1 (Architect) | /audit |
| "Покажи UX", "Симулируй", "Как для пользователя" | Agent 2 (Simulator) | /simulate-all |
| "Бизнес-критика", "ROI контролей", "Глазами владельца" | Agent 2 (Simulator) | /business |
| "Замечания от бизнеса", "Проанализируй замечания" | Agent 3 (Defender) | /respond |
| "Создай тесты", "Тест-кейсы", "Протестируй ФМ" | Agent 4 (QA) | /generate-all |
| "Спроектируй архитектуру", "Сделай ТЗ" | Agent 5 (Tech Architect) | /full |
| "Подготовь презентацию", "Отчет для руководства" | Agent 6 (Presenter) | /present |
| "Опубликуй в Confluence", "Залей в конф" | Agent 7 (Publisher) | /publish |
| "Создай BPMN", "Диаграмма процесса" | Agent 8 (BPMN Designer) | /bpmn |
| "Ревью кода Go", "Проверь план Go", "SE ревью Go" | Agent 9 (SE Go+React) | /review |
| "Ревью кода 1С", "Проверь расширение", "SE ревью 1С" | Agent 10 (SE 1С) | /review |
| "Почини", "Настрой MCP", "Добавь хук" | Оркестратор | agents/ORCHESTRATOR_HELPER.md |
| "Полный цикл", "Конвейер", "Запусти все" | Pipeline | workflows/PIPELINE_AUTO.md |
| "Эволюция", "/evolve" | Evolve | agents/EVOLVE.md |

Если непонятно — спросить через AskUserQuestion: "Вы хотите [вариант 1] или [вариант 2]?"
