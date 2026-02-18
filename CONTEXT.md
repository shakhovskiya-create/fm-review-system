# CONTEXT.md - Progress File

> Инкрементальный лог прогресса для длительных сессий.
> Читается при старте (SessionStart hook) и перед компакцией (PreCompact hook).
> Обновляется автоматически при завершении (Stop hook).

---

## Текущая сессия

**Дата:** 18.02.2026
**Задача:** Интеграция памяти и контекста (Knowledge Graph, Episodic Memory, hooks, skills)

### Что сделано
- [x] Episodic Memory установлен и проиндексирован (140 exchanges, 6 conversations)
- [x] server-memory MCP настроен (.mcp.json), Knowledge Graph засеян (11 entities)
- [x] PreCompact hook создан (сохраняет контекст перед компакцией)
- [x] memory: project добавлен во все 9 агентов
- [x] MODEL_SELECTION.md создан (обоснование opus/sonnet по агентам)
- [x] COMMON_RULES.md: правило 21 (Knowledge Graph)
- [x] CONTEXT.md (этот файл)
- [x] .claude/skills/fm-audit/ (skill для аудита ФМ, привязан к Agent 1)
- [x] .github/workflows/security-review.yml
- [x] seed_memory.py: исправлена дедупликация relations
- [x] Полная верификация: 9 hooks, 3 skills, 2 MCP, 9 agents, 182 теста

### Блокеры
- Нет

### Открытые вопросы
- Нет

---

## Предыдущие сессии

### 18.02.2026 - Deep audit fix
- Исправлены 11 проблем из глубокого аудита (HIGH + MEDIUM)
- 176 тестов, все прошли
- Коммит: f2b2dc3

### 18.02.2026 - SDK + Langfuse
- Pipeline переписан на Claude Code SDK (claude-code-sdk v0.0.25)
- Langfuse трейсинг интегрирован (PipelineTracer)
- 44 теста pipeline, все прошли
- Коммит: f298060

### 18.02.2026 - Stale references
- 10 файлов с устаревшими ссылками обновлены
- Коммит: 2cf991d

### 18.02.2026 - Audit blocks A+B+C
- 15 проблем из повторного аудита исправлены
- Субагенты: maxTurns, disallowedTools, permissionMode, mcpServers
- Hooks: 8 штук (SessionStart, SubagentStart/Stop, PreToolUse, PostToolUse, Stop)
- Skills: evolve, quality-gate
- Коммиты: 6720bd7, 28a4ac8
