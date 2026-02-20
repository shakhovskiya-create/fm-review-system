---
paths:
  - ".claude/agents/**"
---

# Реестр субагентов

10 агентов зарегистрированы как Claude Code subagents в `.claude/agents/`:

| Subagent | Модель | Протокол |
|----------|--------|----------|
| `helper-architect` | opus | `agents/ORCHESTRATOR_HELPER.md` |
| `agent-0-creator` | opus | `agents/AGENT_0_CREATOR.md` |
| `agent-1-architect` | opus | `agents/AGENT_1_ARCHITECT.md` |
| `agent-2-simulator` | opus | `agents/AGENT_2_ROLE_SIMULATOR.md` |
| `agent-3-defender` | opus | `agents/AGENT_3_DEFENDER.md` |
| `agent-4-qa-tester` | sonnet | `agents/AGENT_4_QA_TESTER.md` |
| `agent-5-tech-architect` | opus | `agents/AGENT_5_TECH_ARCHITECT.md` |
| `agent-6-presenter` | sonnet | `agents/AGENT_6_PRESENTER.md` |
| `agent-7-publisher` | sonnet | `agents/AGENT_7_PUBLISHER.md` |
| `agent-8-bpmn-designer` | sonnet | `agents/AGENT_8_BPMN_DESIGNER.md` |

Каждый subagent при запуске читает свой протокол из `agents/` и `agents/COMMON_RULES.md`.

Шаблон для создания нового агента: `docs/AGENT_TEMPLATE.md`
