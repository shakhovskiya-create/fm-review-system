---
globs: .claude/agents/**, agents/**
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

### During work:
- New problem → `bash scripts/gh-tasks.sh create --title "..." --agent <name> --sprint <N> --priority <P>`
- Blocker → `bash scripts/gh-tasks.sh block <N> --reason "..."`

### At end (LAST action):
- Close done issues: `bash scripts/gh-tasks.sh done <N> --comment "Result: ..."`
- Unfinished → leave `status:in-progress`, add progress comment

**Iron rule:** No agent finishes without updating its GitHub Issues.
