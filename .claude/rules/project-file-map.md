---
description: "Карта всех файлов системы fm-review-system — навигация по проекту"
---

# Карта файлов системы

## Субагенты и протоколы
- **Subagents:** `.claude/agents/agent-0-creator.md` ... `.claude/agents/agent-15-trainer.md`
- **Протоколы:** `agents/AGENT_0_CREATOR.md` ... `agents/AGENT_8_BPMN_DESIGNER.md`
- **Протоколы (dev):** `agents/dev/AGENT_11_DEV_1C.md`, `agents/dev/AGENT_12_DEV_GO.md`, `agents/dev/AGENT_13_QA_1C.md`, `agents/dev/AGENT_14_QA_GO.md`, `agents/dev/AGENT_15_TRAINER.md`
- **Оркестратор:** `agents/ORCHESTRATOR_HELPER.md`
- **Общие правила:** `agents/COMMON_RULES.md`

## Confluence
- `docs/CONFLUENCE_TEMPLATE.md` — шаблон XHTML
- `docs/ARCHIVE/CONFLUENCE_REQUIREMENTS-2026-02-05.md` — архив требований
- `scripts/publish_to_confluence.py` — обновление (v3.0, lock+backup+retry)
- `src/fm_review/confluence_utils.py` — API клиент

## Документация
- `docs/CHANGELOG.md`, `docs/CONTRACT_CONFLUENCE_FM.md`
- `docs/LEAD_AUDITOR_FULL_AUDIT.md`, `docs/FC_IMPLEMENTATION_REPORT.md`
- **Артефакты Lead Architect (НЕ затирать!):** `docs/FINDINGS_LEDGER.md`, `docs/ARCHITECT_WORKPLAN.md`

## Self-Improvement
- `.patches/` — паттерны ошибок
- `agents/EVOLVE.md` — /evolve

## Governance
- `AGENT_PROTOCOL.md`, `HANDOFF.md`, `DECISIONS.md`, `logs/`
- `.claude/rules/dod.md` — Definition of Done (DoD) checklist + шаблоны комментариев

## Скрипты
- `scripts/orchestrate.sh` — главное меню (14 пунктов, включая resume и проверку секретов)
- `scripts/run_agent.py` — автономный запуск (Claude Code SDK + Langfuse, --resume, per-agent budgets, prompt injection protection)
- `scripts/quality_gate.sh`, `scripts/fm_version.sh`, `scripts/new_project.sh`
- `scripts/check-secrets.sh` — верификация секретов (Infisical/keyring/.env)
- `scripts/export_from_confluence.py`
- `scripts/queue-graphiti-episode.sh` — очередь эпизодов Graphiti (SubagentStop → `.graphiti-queue/`)

## Observability
- `src/fm_review/langfuse_tracer.py` — Stop hook трейсер
- `infra/langfuse/` — self-hosted Langfuse v3
- `scripts/notify.sh` — alert system: Slack webhook + email + JSONL log (levels: INFO/WARN/ERROR/CRITICAL)
- `scripts/cost-report.sh` — monthly cost breakdown по агентам (Langfuse API, budget alert)
- `scripts/tg-report.py` — Telegram-отчёт по расходам (--yesterday, --today, --days N, --month)
- `scripts/tg-bot.py` — Telegram-бот: отвечает на /report в чате (systemd: fm-tg-bot)
- `scripts/cron-tg-report.sh` — cron wrapper (9:00 вчера, 18:00 сегодня)
- `infra/fm-tg-bot.service` — systemd unit для Telegram-бота

## Secrets
- **Infisical** (hosted): `https://infisical.shakhoff.com`, проект `fm-review-system`, Machine Identity `fm-review-pipeline` (Universal Auth, TTL 10 лет)
- `infra/infisical/.env.machine-identity` — credentials Machine Identity (в .gitignore)
- `infra/infisical/docker-compose.yml` — self-hosted fallback (Docker Compose)
- `scripts/load-secrets.sh` — загрузка секретов (Infisical Universal Auth → keyring → .env)
- `scripts/mcp-confluence.sh` — MCP wrapper с Infisical fallback
- `scripts/check-secrets.sh` — верификация секретов из всех источников
- `infisical.json` — конфиг проекта для CLI

## Memory
- **Knowledge Graph** (`@modelcontextprotocol/server-memory`): `.claude-memory/memory.jsonl`, seed: `scripts/seed_memory.py`
- **Graphiti** (общий с cio-assistant): `scripts/mcp-graphiti.sh`, Neo4j + OpenAI embeddings, group_id=`ekf-shared`
- **Agent Memory** (`memory: project`): `.claude/agent-memory/<name>/MEMORY.md`

## Skills
- `.claude/skills/evolve/` (/evolve)
- `.claude/skills/quality-gate/` (предзагрузка Agent 7)
- `.claude/skills/fm-audit/` (чеклист аудита, предзагрузка Agent 1)
- `.claude/skills/test/` (/test)
- `.claude/skills/run-pipeline/` (/run-pipeline)
- `.claude/skills/run-agent/` (/run-agent)
- `.claude/skills/vercel-react-best-practices/` (57 правил React/Next.js performance, Agent 9, Agent 12)

## MCP Servers
- `confluence` — Confluence API (scripts/mcp-confluence.sh, Infisical secrets)
- `memory` — Knowledge Graph (@modelcontextprotocol/server-memory)
- `github` — GitHub API (scripts/mcp-github.sh)
- `langfuse` — Observability (scripts/mcp-langfuse.sh)
- `playwright` — Runtime UI verification (@playwright/mcp, headless Chromium, Agent 9, Agent 12, Agent 14)
- `agentation` — Visual React UI annotation (agentation-mcp, 9 tools, Agent 9)
- `graphiti` — Temporal Knowledge Graph (Graphiti + Neo4j, scripts/mcp-graphiti.sh, group_id=ekf-shared, все агенты)
- `local-rag` — Semantic search по knowledge-base/ (mcp-local-rag, LanceDB + MiniLM embeddings, scripts/index-rag.sh)
- `jira` — Jira Server API (scripts/mcp-jira.sh, PAT через Infisical)

## Task Tracking (Jira EKFLAB)
- **Проект:** `EKFLAB` на `https://jira.ekf.su`
- **Доска #38:** Доска EKFLAB (все задачи)
- **Доска #39:** Profitability Service (фильтр `product:profitability`)
- `scripts/jira-tasks.sh` — CLI обёртка для Jira (create/start/done/block/list/sprint/children/my-tasks)
  - `create`: `--body` ОБЯЗАТЕЛЕН (образ результата + Acceptance Criteria)
  - `done`: `--comment` ОБЯЗАТЕЛЕН (результат + DoD checklist, правила 27-28)
- Labels: `agent:*`, `product:*` (спринты через customfield_10104)
- SubagentStart-хук инжектирует назначенные задачи из Jira при запуске агента
- SubagentStop-хук проверяет что все задачи агента закрыты с DoD
- `.claude/rules/dod.md` — Definition of Done: 8 пунктов, шаблоны комментариев
- `scripts/migrate-gh-to-jira.py` — скрипт миграции из GitHub Issues в Jira
- `projects/PROJECT_SHPMNT_PROFIT/gh_to_jira_mapping.json` — маппинг GH#→EKFLAB-N
- `scripts/gh-tasks.sh` — DEPRECATED (оставлен как fallback для GitHub Issues)

## Прочее
- `CONTEXT.md` — эфемерный session state (в .gitignore, генерируется хуками)
- `.github/workflows/claude.yml` (PR review), `.github/workflows/security-review.yml`, `.github/workflows/dod-check.yml` (переоткрывает issues без DoD), `.github/workflows/jira-sync.yml` (коммиты с EKFLAB-N → комментарий в Jira)
- `.claude/hooks/guard-issue-autoclose.sh` — блокирует `Closes/Fixes/Resolves #N` в git commit (PreToolUse)
- `schemas/agent-contracts.json` (v2.2, multi-platform)
- `docs/MODEL_SELECTION.md` — модели и бюджеты по агентам
