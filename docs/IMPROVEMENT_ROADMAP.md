# Roadmap улучшений системы FM Review Agents

> Результаты исследования (февраль 2026). Актуализируется по мере выполнения.

---

## Приоритетная матрица

| # | Технология | Зрелость | Effort | Приоритет | Статус |
|---|-----------|---------|--------|-----------|--------|
| 1 | mcp-atlassian (MCP-сервер Confluence) | Production | Low | P0 | DONE |
| 2 | Hooks (расширение PostToolUse валидации) | Production | Low | P0 | DONE |
| 3 | Confluence Agent Skill (mastering-confluence) | Beta | Low | P1 | SKIP (Cloud-only) |
| 4 | Episodic Memory (obra/episodic-memory) | Beta | Low | P1 | DONE |
| 5 | Langfuse (observability, self-hosted) | Production | Medium | P2 | TODO |
| 6 | GitHub Actions (anthropics/claude-code-action) | Production | Low | P2 | TODO |
| 7 | Adaptive Thinking/Effort (разные уровни по агентам) | Production | Low | P2 | TODO |
| 8 | Agent Teams (параллельная работа агентов) | Experimental | High | P3 | TODO |
| 9 | Agent SDK (Python, замена run_agent.py) | Beta | High | P3 | TODO |

---

## P0 - ВЫПОЛНЕНО (17.02.2026)

### 1. mcp-atlassian
- Установлен: `pip install mcp-atlassian`
- Настроен: `.mcp.json` (confluence URL, PAT, SSL)
- 11 MCP-инструментов доступны всем агентам
- Протоколы агентов обновлены (COMMON_RULES.md + все AGENT_*.md)
- Коммит: bb00614

### 2. Hooks
- `validate-xhtml-style.sh` (PostToolUse) - проверка XHTML стилей и AI-упоминаний
- `auto-save-context.sh` (Stop) - обновление timestamp в PROJECT_CONTEXT.md
- Коммит: 6fd61e6

---

## P1 - ВЫПОЛНЕНО (17.02.2026)

### 3. Confluence Agent Skill
- ПРОПУЩЕН: mastering-confluence-agent-skill поддерживает ТОЛЬКО Confluence Cloud
- Наш сервер (https://confluence.ekf.su) - on-premise Confluence Server
- Используем mcp-atlassian вместо этого

### 4. Episodic Memory
- Установлен как плагин Claude Code (`/plugin install episodic-memory@superpowers-marketplace`)
- Семантическая память между сессиями
- Локальные эмбеддинги (Transformers.js), SQLite + sqlite-vec
- Коммит: 0a7f336

---

## P2 - ЗАПЛАНИРОВАНО

### 5. Langfuse (observability)
- **Что:** Open-source LLM observability платформа, self-hosted
- **Зачем:** Мониторинг работы агентов, метрики качества, стоимость токенов
- **Effort:** Medium (нужен Docker, настройка сервера)
- **Как:** Langfuse SDK + трейсинг вызовов Claude API

### 6. GitHub Actions (claude-code-action)
- **Что:** anthropics/claude-code-action - Claude Code в CI/CD
- **Зачем:** Автоматический PR review, проверка качества кода агентов
- **Effort:** Low (GitHub Action, yaml конфиг)
- **Как:** `.github/workflows/claude-review.yml`

### 7. Adaptive Thinking/Effort
- **Что:** Разные уровни "думания" для разных агентов
- **Зачем:** Agent 1 (аудит) нужен глубокий анализ, Agent 6 (презентации) - быстрый
- **Effort:** Low (параметр model/thinking в subagent конфигах)
- **Как:** Настройка model (opus/sonnet/haiku) и thinking budget per agent

---

## P3 - БУДУЩЕЕ

### 8. Agent Teams (параллельная работа)
- **Что:** Запуск нескольких агентов параллельно
- **Зачем:** Ускорение pipeline (Agent 1+2+4 одновременно)
- **Effort:** High (оркестрация, merge результатов, конфликты)
- **Риски:** Параллельная запись в Confluence, конфликты версий

### 9. Agent SDK (Python)
- **Что:** Anthropic Agent SDK для Python, замена run_agent.py
- **Зачем:** Более надежный оркестратор, structured output, tool use
- **Effort:** High (переписать оркестрацию)
- **Зависимости:** SDK должен стабилизироваться

---

## Дополнительно: Дедупликация агентов

**Не из исследования, но выявлено при обновлении:**
- 9 файлов агентов содержат ~1100 строк дублей (22% от объема)
- Дубли: СТРУКТУРА ПРОЕКТОВ, ПРАВИЛО ФОРМАТА, XHTML, АВТОСОХРАНЕНИЕ, _summary.json
- Все уже есть в COMMON_RULES.md, но повторяются в каждом агенте
- Рефакторинг: заменить дубли на ссылки "см. COMMON_RULES.md правило N"
- Приоритет: после P2, перед P3
