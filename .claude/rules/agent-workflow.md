---
description: Agent workflow rules for plan-implement-fix cycle, Jira task tracking, and task decomposition
---

# Agent Workflow: Plan -> Implement -> Fix

## Cycle (mandatory for non-trivial tasks)
1. **PLAN** — write to WORKPLAN.md: tasks, files, expected result, risks
2. **IMPLEMENT** — mark tasks in_progress → done; blocked with reason if stuck
3. **FIX** — update WORKPLAN.md, git commit, update HANDOFF.md

Trivial edits (typos, one-liners) — allowed without plan.

## Deviation Rules
1. **Cosmetic** (whitespace, formatting) — fix silently
2. **Minor** (rename var, clarify comment) — fix, note in report
3. **Scope change** (new feature, extra file) — warn user, proceed only with confirmation
4. **Contradicts plan** — **STOP**. AskUserQuestion.

## Jira Tasks (persistent tracking)

**Project:** EKFLAB | **CLI:** `scripts/jira-tasks.sh` | **MCP:** `mcp__jira__*`

### At start (FIRST action):
- SubagentStart hook injects assigned Jira issues — read them
- Status "В работе" → continue that task
- Status "Сделать" → take priority one, `bash scripts/jira-tasks.sh start EKFLAB-N`

### Decomposition (ОБЯЗАТЕЛЬНО для задач с 2+ шагами):
**Проблема:** одна issue "Сделать всё" — не видно прогресса, непонятно что сделано.

**Правило:** Если задача требует 2+ самостоятельных действий — РАЗБЕЙ на подзадачи.

1. Создай epic (type=Epic) с общим описанием
2. Декомпозируй на 3-7 задач, каждая = 1 конкретный deliverable
3. Каждая подзадача: `jira-tasks.sh create --parent EKFLAB-N --title "..." ...`
4. Закрывай подзадачи по одной с DoD
5. Epic закрывается ПОСЛЕДНИМ, когда все подзадачи done

**Пример:**
```
Epic EKFLAB-3: "Phase 3A: Project Scaffold"
  EKFLAB-28: "3.1 Repository init" (--parent EKFLAB-3)
  EKFLAB-29: "3.2 Go tooling setup" (--parent EKFLAB-3)
  EKFLAB-30: "3.3 React project setup" (--parent EKFLAB-3)
  EKFLAB-31: "3.4 Docker infrastructure" (--parent EKFLAB-3)
```

**Когда НЕ декомпозировать:**
- Задача имеет 1 действие и 1 результат (пример: "Исправить опечатку в ФМ")
- Задача тривиальна (< 10 минут работы)

### During work:
- New problem → `bash scripts/jira-tasks.sh create --title "..." --agent <name> --sprint <N> --priority <P> --body "..."`
- Blocker → `bash scripts/jira-tasks.sh block EKFLAB-N --reason "..."`
- Check epic progress → `bash scripts/jira-tasks.sh children EKFLAB-N`

### At end (LAST action):
- Close done issues: `bash scripts/jira-tasks.sh done EKFLAB-N --comment "Result: ..."`
- Unfinished → leave "В работе", add progress comment via MCP
- Epic: close ONLY when all children closed (check via `jira-tasks.sh children`)

**Iron rule:** No agent finishes without updating its Jira tasks.

### Commit messages:
- Reference Jira: `Refs EKFLAB-N` (NOT `Closes #N`)
- Example: `feat: add domain entities (Refs EKFLAB-28)`
