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

### Time Tracking (ОБЯЗАТЕЛЬНО):
- При создании задачи ВСЕГДА указывать `--estimate Xh` (планируемое время)
- Формат: `1h`, `2h`, `4h`, `1d` (1d = 8h)
- Ориентиры: мелкий фикс = 1h, задача с тестами = 2-4h, крупная задача = 4-8h, epic = сумма children

### Цикл ревью (Agent 12 ↔ Agent 9):
**ОБЯЗАТЕЛЬНО** для любого code review:
1. Agent 12 (Dev) пишет/фиксит код
2. Agent 9 (SE) делает review
3. Если НЕ PASS → Agent 12 фиксит findings → Agent 9 ревьюит снова
4. Повторять до PASS (max 5 итераций)
5. ТОЛЬКО после PASS → переход к тестам (Agent 14)
**Оркестратор** отвечает за запуск цикла. НЕ пропускать ревью!

### During work:
- New problem → `bash scripts/jira-tasks.sh create --title "..." --agent <name> --sprint <N> --priority <P> --estimate Xh --body "..."`
- Blocker → `bash scripts/jira-tasks.sh block EKFLAB-N --reason "..."`
- Check epic progress → `bash scripts/jira-tasks.sh children EKFLAB-N`

### At end (ПОСЛЕДНЕЕ действие перед return):
1. **Проверь:** `bash scripts/jira-tasks.sh my-tasks --agent <name>` — список ВСЕХ твоих задач
2. **Закрой ВСЕ** выполненные: `bash scripts/jira-tasks.sh done EKFLAB-N --comment "Результат: ..."`
3. Незавершённые → оставь "В работе" + добавь комментарий с прогрессом
4. Epic: закрой ТОЛЬКО когда все подзадачи done (`jira-tasks.sh children`)
5. **Контрольная проверка:** снова `my-tasks` — должно быть 0 задач "В работе" (кроме незавершённых)

**БЛОКИРУЮЩЕЕ ПРАВИЛО:** SubagentStop хук проверяет задачи с меткой `agent:<name>`.
Если есть незакрытые задачи → хук блокирует (exit 2) → ты НЕ ЗАВЕРШИШЬСЯ.
Закрой задачи → хук пропустит → ты сможешь вернуть результат.

**Ответственность:** Оркестратор НЕ должен закрывать задачи за тебя. Каждый агент сам.

### Commit messages:
- Reference Jira: `Refs EKFLAB-N` (NOT `Closes #N`)
- Example: `feat: add domain entities (Refs EKFLAB-28)`

### Git workflow (profitability-service):
- **main** = protected. Прямые пуши ЗАПРЕЩЕНЫ (branch protection)
- **Feature branch:** `feat/EKFLAB-N-short-desc` или `fix/EKFLAB-N-short-desc`
- **Workflow:** checkout -b → commit → push -u → gh pr create → CI pass → squash merge
- Agent 12: создаёт feature branch, пушит, создаёт PR. Merge — после CI green
- `gh pr merge --squash --auto` — авто-merge после CI. Или merge вручную оркестратором
