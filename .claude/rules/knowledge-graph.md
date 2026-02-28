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

## Local RAG (semantic search over knowledge base)
- **MCP server:** `local-rag` (mcp-local-rag, LanceDB + Xenova/all-MiniLM-L6-v2)
- **Tools:** `query_documents` (semantic search), `ingest_file`, `list_files`, `status`
- **Data:** `knowledge-base/*.md` → `.rag-db/` (auto-indexed on first query)
- **Index script:** `scripts/index-rag.sh` (status, manual trigger)

## 5-уровневая иерархия поиска

| # | Инструмент | Что ищем | Когда |
|---|-----------|---------|------|
| 1 | **KB файлы** (`Read knowledge-base/*.md`) | Точный lookup | Знаешь какой файл нужен |
| 2 | **Local RAG** (`mcp__local-rag__query_documents`) | Семантический поиск по KB | Не знаешь где, ищешь по смыслу |
| 3 | **Graphiti** (`mcp__graphiti__search_nodes/facts`) | Сущности, связи, хронология | Нужны связи между объектами |
| 4 | **MCP memory** (`mcp__memory__search_nodes`) | Оперативные заметки агентов | Решения, findings, контекст прошлых сессий |
| 5 | **Confluence** (`confluence_search/get_page`) | Свежие данные ФМ | Нужна актуальная версия ФМ |

**Правило:** Начинай с уровня 1 (дёшево), спускайся ниже только если не нашёл.

## Agent Memory (personal per-agent memory)
Each subagent uses `memory: project` — personal memory in `.claude/agent-memory/<name>/MEMORY.md`.
Orchestrator restores context from HANDOFF.md + CONTEXT.md + Knowledge Graph + Graphiti.
