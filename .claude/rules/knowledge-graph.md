---
globs: .claude/agents/**, agents/**, scripts/seed_memory.py
---

# Knowledge Graph & Memory

## Knowledge Graph (cross-session memory)
- **At start:** `mcp__memory__search_nodes` — find project entities, agents, decisions
- **At end:** `mcp__memory__add_observations` — record key findings, decisions, facts

**Record:** audit findings (CRIT/HIGH), decisions (what + why), FM versions (after /apply), blockers
**Don't record:** intermediate steps, FM content (use Confluence), full report texts (use files)

Data: `.claude-memory/memory.jsonl`. Seed: `python3 scripts/seed_memory.py`

## Episodic Memory (session history search)
Plugin `episodic-memory@superpowers-marketplace` — semantic search over Claude Code conversation history.
Used by orchestrator to restore context before launching agents.
Subagents use Knowledge Graph + `memory: project` (personal agent memory).
