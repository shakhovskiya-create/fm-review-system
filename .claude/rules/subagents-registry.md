# Реестр субагентов и маршрутизация

15 агентов зарегистрированы как Claude Code subagents в `.claude/agents/`:

| Subagent | Модель | Протокол | Фаза |
|----------|--------|----------|------|
| `helper-architect` | opus | `agents/ORCHESTRATOR_HELPER.md` | — |
| `agent-0-creator` | opus | `agents/AGENT_0_CREATOR.md` | review |
| `agent-1-architect` | opus | `agents/AGENT_1_ARCHITECT.md` | review |
| `agent-2-simulator` | sonnet | `agents/AGENT_2_ROLE_SIMULATOR.md` | review |
| `agent-5-tech-architect` | opus | `agents/AGENT_5_TECH_ARCHITECT.md` | review |
| `agent-7-publisher` | opus | `agents/AGENT_7_PUBLISHER.md` | review |
| `agent-8-bpmn-designer` | sonnet | `agents/AGENT_8_BPMN_DESIGNER.md` | review |
| `agent-9-se-go` | opus | `agents/AGENT_9_SE_GO.md` | review |
| `agent-10-se-1c` | opus | `agents/AGENT_10_SE_1C.md` | review |
| `agent-11-dev-1c` | opus | `agents/dev/AGENT_11_DEV_1C.md` | dev |
| `agent-12-dev-go` | opus | `agents/dev/AGENT_12_DEV_GO.md` | dev |
| `agent-13-qa-1c` | sonnet | `agents/dev/AGENT_13_QA_1C.md` | dev |
| `agent-14-qa-go` | sonnet | `agents/dev/AGENT_14_QA_GO.md` | dev |
| `agent-15-trainer` | sonnet | `agents/dev/AGENT_15_TRAINER.md` | review |

**DEPRECATED:** Agent 3 (Defender → merged into Agent 1), Agent 4 (QA → Agent 13+14), Agent 6 (Presenter → Agent 15)

Каждый subagent при запуске читает свой протокол из `agents/` или `agents/dev/` и `agents/COMMON_RULES.md`.

Шаблон для создания нового агента: `docs/AGENT_TEMPLATE.md`

## Маршрутизация (Natural Language → Agent)

| Фраза | Агент | Команда |
|-------|-------|---------|
| "Создай ФМ", "Новая ФМ", "Опиши процесс" | Agent 0 (Creator) | /new |
| "Запусти аудит", "Проверь ФМ", "Проблемы в ФМ" | Agent 1 (Architect) | /audit |
| "Покажи UX", "Симулируй", "Как для пользователя" | Agent 2 (Simulator) | /simulate-all |
| "Бизнес-критика", "ROI контролей", "Глазами владельца" | Agent 2 (Simulator) | /business |
| "Замечания от бизнеса", "Проанализируй замечания" | Agent 1 (Architect: Defense) | /defense-all |
| "Спроектируй архитектуру", "Сделай ТЗ" | Agent 5 (Tech Architect) | /full |
| "Опубликуй в Confluence", "Залей в конф" | Agent 7 (Publisher) | /publish |
| "Создай BPMN", "Диаграмма процесса" | Agent 8 (BPMN Designer) | /bpmn |
| "Ревью кода Go", "Проверь план Go", "SE ревью Go" | Agent 9 (SE Go+React) | /review |
| "Ревью кода 1С", "Проверь расширение", "SE ревью 1С" | Agent 10 (SE 1С) | /review |
| "Напиши код 1С", "Сгенерируй расширение" | Agent 11 (Dev 1С) | /auto |
| "Напиши код Go", "Сгенерируй сервис", "React компонент" | Agent 12 (Dev Go+React) | /auto |
| "Протестируй 1С", "Vanessa тесты", "YAxUnit" | Agent 13 (QA 1С) | /auto |
| "Протестируй Go", "Тесты React", "E2E тесты" | Agent 14 (QA Go+React) | /auto |
| "Инструкции", "Обучение", "User guide", "FAQ" | Agent 15 (Trainer) | /auto |
| "Почини", "Настрой MCP", "Добавь хук" | Оркестратор | agents/ORCHESTRATOR_HELPER.md |
| "Полный цикл", "Конвейер", "Запусти все" | Pipeline | workflows/PIPELINE_AUTO.md |
| "Эволюция", "/evolve" | Evolve | agents/EVOLVE.md |

Если непонятно — спросить через AskUserQuestion: "Вы хотите [вариант 1] или [вариант 2]?"
