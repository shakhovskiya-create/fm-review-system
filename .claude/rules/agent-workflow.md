---
description: Agent workflow rules for plan-implement-fix cycle, GitHub Issues tracking, and task decomposition
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

## GitHub Issues (persistent tracking)

### At start (FIRST action):
- SubagentStart hook injects assigned issues — read them
- `status:in-progress` → continue that task
- `status:planned` → take priority one, `bash scripts/gh-tasks.sh start <N>`

### Decomposition (ОБЯЗАТЕЛЬНО для задач с 2+ шагами):
**Проблема:** одна issue "Сделать всё" — не видно прогресса, непонятно что сделано.

**Правило:** Если задача требует 2+ самостоятельных действий — РАЗБЕЙ на подзадачи.

1. Создай epic (label `type:epic`) с общим описанием
2. Декомпозируй на 3-7 задач, каждая = 1 конкретный deliverable
3. Каждая подзадача: `gh-tasks.sh create --parent <epic_N> --title "..." ...`
4. Закрывай подзадачи по одной с DoD
5. Epic закрывается ПОСЛЕДНИМ, когда все подзадачи done

**Пример:**
```
Epic #90: "Аудит ФМ v1.0.6" (type:epic, agent:1-architect)
  #91: "Проверить бизнес-правила" (--parent 90)
  #92: "Проверить интеграции с SBS" (--parent 90)
  #93: "Проверить UI/UX для УТ 10.2" (--parent 90)
  #94: "Написать audit_summary.json" (--parent 90)
```

**Когда НЕ декомпозировать:**
- Задача имеет 1 действие и 1 результат (пример: "Исправить опечатку в ФМ")
- Задача тривиальна (< 10 минут работы)

### During work:
- New problem → `bash scripts/gh-tasks.sh create --title "..." --agent <name> --sprint <N> --priority <P> --body "..."`
- Blocker → `bash scripts/gh-tasks.sh block <N> --reason "..."`
- Check epic progress → `bash scripts/gh-tasks.sh children <epic_N>`

### At end (LAST action):
- Close done issues: `bash scripts/gh-tasks.sh done <N> --comment "Result: ..."`
- Unfinished → leave `status:in-progress`, add progress comment
- Epic: close ONLY when all children closed (script validates)

**Iron rule:** No agent finishes without updating its GitHub Issues.
