#!/usr/bin/env python3
"""
Seed the MCP Knowledge Graph memory with FM Review System metadata.

Populates .claude-memory/memory.jsonl with:
- Agent roles and capabilities
- Project metadata (name, PAGE_ID, FM version)
- Pipeline stages and dependencies
- Cross-agent data flow

Usage:
    python3 scripts/seed_memory.py [--reset]
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_FILE = PROJECT_ROOT / ".claude-memory" / "memory.jsonl"

# ── Agent definitions ──────────────────────────────────────────
AGENTS = [
    {
        "name": "Agent0_Creator",
        "entityType": "agent",
        "observations": [
            "Creates FM from scratch via interview",
            "Commands: /new, /apply",
            "Writes to Confluence via Agent 7",
            "File: agents/AGENT_0_CREATOR.md",
            "Tools: Read, Write, Edit, Grep, Glob, Bash, WebFetch",
        ],
    },
    {
        "name": "Agent1_Architect",
        "entityType": "agent",
        "observations": [
            "Full FM audit + defense mode (merged with Agent 3)",
            "Commands: /audit, /apply, /auto, /defense-all",
            "Two pipeline passes: audit (pass 1) → defense (pass 2 after Agent 2)",
            "Defense: A-I classification of findings from other agents",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_1_ARCHITECT/ (audit-report-v*.md, _summary.json)",
            "File: agents/AGENT_1_ARCHITECT.md (v2.0.0)",
            "Priority: highest in conflict resolution",
        ],
    },
    {
        "name": "Agent2_RoleSimulator",
        "entityType": "agent",
        "observations": [
            "Simulates user roles (manager, warehouse, accountant)",
            "Commands: /simulate-all, /simulate-role",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_2_ROLE_SIMULATOR/",
            "Uses Agent 1 findings for focus",
        ],
    },
    {
        "name": "Agent3_Defender",
        "entityType": "agent",
        "observations": [
            "DEPRECATED: merged into Agent 1 (Architect+Defender), 2026-02-27",
            "Defense mode now in Agent 1: /defense-all command",
            "Classification A-I preserved in Agent 1 protocol",
        ],
    },
    {
        "name": "Agent4_QATester",
        "entityType": "agent",
        "observations": [
            "DEPRECATED: replaced by Agent 13 (QA 1С) + Agent 14 (QA Go), 2026-02-27",
        ],
    },
    {
        "name": "Agent5_TechArchitect",
        "entityType": "agent",
        "observations": [
            "Designs 1C implementation architecture",
            "Commands: /full, /tz, /arch",
            "Creates TS-FM-* (technical specification) and ARC-FM-* (architecture)",
            "Publishes to Confluence",
            "Output: AGENT_5_TECH_ARCHITECT/",
        ],
    },
    {
        "name": "Agent6_Presenter",
        "entityType": "agent",
        "observations": [
            "DEPRECATED: replaced by Agent 15 (Trainer), 2026-02-27",
        ],
    },
    {
        "name": "Agent7_Publisher",
        "entityType": "agent",
        "observations": [
            "ONLY agent that writes to Confluence",
            "Commands: /publish, /sync, /update",
            "Uses confluence_utils.py (lock, backup, retry, audit log)",
            "Requires Quality Gate before publishing",
            "Has quality-gate skill preloaded",
            "Output: AGENT_7_PUBLISHER/",
        ],
    },
    {
        "name": "Agent8_BPMNDesigner",
        "entityType": "agent",
        "observations": [
            "Creates BPMN diagrams for Confluence",
            "Commands: /bpmn",
            "Attaches .drawio files to Confluence pages",
            "Output: AGENT_8_BPMN_DESIGNER/",
        ],
    },
    {
        "name": "Agent9_SE_Go",
        "entityType": "agent",
        "observations": [
            "Senior Engineer for Go + React projects",
            "Commands: /review",
            "Architecture review, code review, test review, performance review",
            "Has Playwright and Agentation MCP tools for UI verification",
            "File: agents/AGENT_9_SE_GO.md",
        ],
    },
    {
        "name": "Agent10_SE_1C",
        "entityType": "agent",
        "observations": [
            "Senior Engineer for 1C (UT/ERP/KA) projects",
            "Commands: /review",
            "Architecture review, code review, Vanessa Automation tests, performance review",
            "File: agents/AGENT_10_SE_1C.md",
        ],
    },
    {
        "name": "Agent11_Dev1C",
        "entityType": "agent",
        "observations": [
            "Developer 1С: generates BSL code for extensions (.cfe)",
            "Commands: /generate, /generate-module, /generate-form, /validate, /kafka, /auto",
            "SDD methodology, ITS Standard 455, extension patterns",
            "Multi-config: УТ 10.2, УТ 11.5, ERP 2.5, БП 3.0, ЗУП 3.1, УХ, ДО 3.0",
            "Kafka: Outbox pattern, NativeAPI components, REST Proxy, HTTP gateway",
            "File: agents/dev/AGENT_11_DEV_1C.md",
            "Phase: dev (on demand, after FM review)",
            "Reads: Agent 5 (TZ), Agent 10 (SE findings)",
        ],
    },
    {
        "name": "Agent12_DevGo",
        "entityType": "agent",
        "observations": [
            "Developer Go+React: generates Go services and React components",
            "Commands: /generate, /generate-service, /generate-component, /generate-api, /generate-kafka, /auto",
            "Clean Architecture, oapi-codegen+chi, sqlc, React 19+, Next.js 15+",
            "Kafka: franz-go (pure Go), GroupTransactSession EOS, DLQ+retry, Schema Registry",
            "File: agents/dev/AGENT_12_DEV_GO.md",
            "Phase: dev (on demand, after FM review)",
            "Reads: Agent 5 (TZ), Agent 9 (SE findings)",
        ],
    },
    {
        "name": "Agent13_QA1C",
        "entityType": "agent",
        "observations": [
            "QA 1С: generates tests for 1С code (YAxUnit, Vanessa, Coverage41C)",
            "Commands: /generate-unit, /generate-bdd, /generate-smoke, /generate-kafka, /coverage-report, /auto",
            "Multi-config testing: adapts tests per configuration (УТ/ERP/БП/ЗУП/УХ/ДО)",
            "Kafka testing: Outbox YAxUnit, HTTP mock, Vanessa BDD flows",
            "File: agents/dev/AGENT_13_QA_1C.md",
            "Phase: dev",
            "Reads: Agent 11 (1С code), Agent 5 (TZ)",
        ],
    },
    {
        "name": "Agent14_QAGo",
        "entityType": "agent",
        "observations": [
            "QA Go+React: generates tests for Go/React (testify, Vitest, Playwright)",
            "Commands: /generate-go-tests, /generate-react-tests, /generate-e2e, /generate-kafka, /auto",
            "Kafka testing: testcontainers-go (KRaft), franz-go consumer/producer, DLQ, contract tests",
            "File: agents/dev/AGENT_14_QA_GO.md",
            "Phase: dev",
            "Reads: Agent 12 (Go/React code), Agent 5 (TZ)",
        ],
    },
    {
        "name": "Agent15_Trainer",
        "entityType": "agent",
        "observations": [
            "Trainer: generates user documentation and training materials",
            "Commands: /user-guide, /quick-start, /admin-guide, /faq, /release-notes, /auto",
            "7-step documentation framework, FM-to-docs mapping",
            "File: agents/dev/AGENT_15_TRAINER.md",
            "Replaces deprecated Agent 6 (Presenter)",
            "Reads: FM (Confluence), Agent 13 (BDD scenarios for instructions)",
        ],
    },
    {
        "name": "Orchestrator_Helper",
        "entityType": "agent",
        "observations": [
            "Main Claude Code session role - NOT a subagent",
            "Dual role: FM agent router + project infrastructure architect",
            "Protocol: agents/ORCHESTRATOR_HELPER.md",
            "Subagent file: .claude/agents/helper-architect.md",
            "Manages: hooks, scripts, MCP servers, CI/CD, tests, agent protocols",
            "Delegates FM content work to agents 0-8",
            "Has Episodic Memory access (subagents do not)",
        ],
    },
]

# ── Scripts ────────────────────────────────────────────────────
SCRIPTS = [
    {"name": "run_agent_py", "entityType": "script", "observations": [
        "Main entry: scripts/run_agent.py",
        "Claude Code SDK-based agent executor",
        "Supports: --pipeline, --agent, --resume, --parallel, --dry-run",
        "Per-agent budgets, prompt injection protection, Langfuse tracing",
    ]},
    {"name": "publish_to_confluence_py", "entityType": "script", "observations": [
        "scripts/publish_to_confluence.py",
        "Two modes: --from-file (XHTML update) or .docx import (legacy)",
        "Uses ConfluenceClient (lock + backup + retry)",
        "XHTML sanitizer before publishing",
    ]},
    {"name": "export_from_confluence_py", "entityType": "script", "observations": [
        "scripts/export_from_confluence.py",
        "Exports Confluence page to local XHTML file",
        "Used by agents to read FM for offline processing",
    ]},
    {"name": "quality_gate_sh", "entityType": "script", "observations": [
        "scripts/quality_gate.sh",
        "Mandatory before Agent 7 publishing",
        "Checks: _summary.json exists, findings covered, no CRITICAL unresolved",
        "Exit codes: 0=ready, 1=critical block, 2=warnings",
    ]},
    {"name": "gh_tasks_sh", "entityType": "script", "observations": [
        "scripts/gh-tasks.sh",
        "CLI wrapper for GitHub Issues: create/start/done/block/list/sprint",
        "Enforces --body on create, --comment on done (DoD)",
        "Artifact cross-check: warns if files from git diff not mentioned in comment",
    ]},
    {"name": "orchestrate_sh", "entityType": "script", "observations": [
        "scripts/orchestrate.sh",
        "Interactive menu (14 options) for pipeline management",
        "Includes resume, secret check, agent selection",
    ]},
    {"name": "load_secrets_sh", "entityType": "script", "observations": [
        "scripts/load-secrets.sh",
        "Priority: Infisical Universal Auth -> keyring -> .env",
        "Sets 7+ env vars: CONFLUENCE_TOKEN, ANTHROPIC_API_KEY, etc.",
    ]},
    {"name": "check_secrets_sh", "entityType": "script", "observations": [
        "scripts/check-secrets.sh --verbose",
        "Verifies all secrets available from configured sources",
    ]},
    {"name": "notify_sh", "entityType": "script", "observations": [
        "scripts/notify.sh",
        "Alert system: Slack webhook + email + JSONL log",
        "Levels: INFO/WARN/ERROR/CRITICAL",
    ]},
    {"name": "cost_report_sh", "entityType": "script", "observations": [
        "scripts/cost-report.sh",
        "Monthly cost breakdown by agent via Langfuse API",
        "Budget alerts when threshold exceeded",
    ]},
    {"name": "tg_report_py", "entityType": "script", "observations": [
        "scripts/tg-report.py",
        "Telegram cost report: --yesterday, --today, --days N, --month",
    ]},
    {"name": "seed_memory_py", "entityType": "script", "observations": [
        "scripts/seed_memory.py",
        "Populates Knowledge Graph (.claude-memory/memory.jsonl)",
        "Discovers projects, agents, relations automatically",
    ]},
]

# ── Hooks ──────────────────────────────────────────────────────
HOOKS = [
    {"name": "hook_inject_project_context", "entityType": "hook", "observations": [
        "SessionStart hook: .claude/hooks/inject-project-context.sh",
        "Injects active projects, KG entity count, GitHub Issues into session",
    ]},
    {"name": "hook_subagent_context", "entityType": "hook", "observations": [
        "SubagentStart hook: .claude/hooks/subagent-context.sh",
        "Injects project context + assigned GitHub Issues into subagent",
        "Writes .current-subagent marker for guard hooks",
    ]},
    {"name": "hook_guard_confluence_write", "entityType": "hook", "observations": [
        "PreToolUse hook: .claude/hooks/guard-confluence-write.sh",
        "Blocks Bash-based Confluence writes (curl PUT/POST)",
        "All writes must go through publish_to_confluence.py",
    ]},
    {"name": "hook_guard_mcp_confluence", "entityType": "hook", "observations": [
        "PreToolUse hook: .claude/hooks/guard-mcp-confluence-write.sh",
        "Blocks MCP confluence_update_page/delete_page",
        "Exception: Agent 7 (Publisher) is allowed",
    ]},
    {"name": "hook_guard_destructive_bash", "entityType": "hook", "observations": [
        "PreToolUse hook: .claude/hooks/guard-destructive-bash.sh",
        "Blocks: rm -rf system dirs, git push --force main, git reset --hard, git clean -f",
        "Uses CMD_POS anchor to avoid false positives in strings",
    ]},
    {"name": "hook_guard_agent_write_scope", "entityType": "hook", "observations": [
        "PreToolUse hook: .claude/hooks/guard-agent-write-scope.sh",
        "Ensures agents write only to their own AGENT_X_* directory",
        "Orchestrator (helper-architect) exempt",
    ]},
    {"name": "hook_block_secrets", "entityType": "hook", "observations": [
        "PreToolUse hook: .claude/hooks/block-secrets.sh",
        "Blocks Write/Edit to .env, credentials, key files",
    ]},
    {"name": "hook_validate_summary", "entityType": "hook", "observations": [
        "SubagentStop hook: .claude/hooks/validate-summary.sh",
        "Checks _summary.json created and valid after agent run",
        "Reminds DoD template for unclosed issues",
    ]},
    {"name": "hook_validate_xhtml_style", "entityType": "hook", "observations": [
        "PostToolUse hook: .claude/hooks/validate-xhtml-style.sh",
        "Checks XHTML output for style compliance (header colors, etc.)",
    ]},
    {"name": "hook_langfuse_trace", "entityType": "hook", "observations": [
        "Stop hook: .claude/hooks/langfuse-trace.sh",
        "Sends session trace to Langfuse for observability",
    ]},
]

# ── MCP Servers ────────────────────────────────────────────────
MCP_SERVERS = [
    {"name": "mcp_confluence", "entityType": "mcp_server", "observations": [
        "Confluence MCP server via scripts/mcp-confluence.sh",
        "Tools: get_page, update_page, create_page, search, comments, labels",
        "Secrets loaded from Infisical",
    ]},
    {"name": "mcp_memory", "entityType": "mcp_server", "observations": [
        "Knowledge Graph: @modelcontextprotocol/server-memory",
        "Data: .claude-memory/memory.jsonl",
        "Tools: search_nodes, create_entities, add_observations, create_relations",
    ]},
    {"name": "mcp_github", "entityType": "mcp_server", "observations": [
        "GitHub MCP server via scripts/mcp-github.sh",
        "Tools: issues, PRs, code search, repository management",
    ]},
    {"name": "mcp_langfuse", "entityType": "mcp_server", "observations": [
        "Langfuse observability MCP via scripts/mcp-langfuse.sh",
        "Tools: get_traces, get_observations",
    ]},
    {"name": "mcp_playwright", "entityType": "mcp_server", "observations": [
        "Playwright MCP: @playwright/mcp (headless Chromium)",
        "Used by Agent 9 for runtime UI verification",
    ]},
    {"name": "mcp_agentation", "entityType": "mcp_server", "observations": [
        "Agentation MCP: visual React UI annotation",
        "9 tools for Agent 9 workflow",
    ]},
]

# ── Skills ─────────────────────────────────────────────────────
SKILLS = [
    {"name": "skill_evolve", "entityType": "skill", "observations": [
        "/evolve: Analyzes .patches/ and updates agent instructions",
        "Self-improvement loop for the system",
    ]},
    {"name": "skill_quality_gate", "entityType": "skill", "observations": [
        "Pre-loaded for Agent 7: runs quality_gate.sh before publishing",
    ]},
    {"name": "skill_fm_audit", "entityType": "skill", "observations": [
        "Pre-loaded for Agent 1: FM audit checklist",
    ]},
    {"name": "skill_test", "entityType": "skill", "observations": [
        "/test: runs pytest tests/ -v --tb=short",
    ]},
    {"name": "skill_run_pipeline", "entityType": "skill", "observations": [
        "/run-pipeline: runs scripts/run_agent.py --pipeline --project $ARGS",
    ]},
    {"name": "skill_run_agent", "entityType": "skill", "observations": [
        "/run-agent: runs scripts/run_agent.py --agent $0 --project $1 --command $2",
    ]},
]

# ── Key Modules ────────────────────────────────────────────────
MODULES = [
    {"name": "confluence_utils", "entityType": "module", "observations": [
        "src/fm_review/confluence_utils.py",
        "ConfluenceClient: lock + backup + retry + audit log",
        "Shared: _get_page_id(), _make_ssl_context(), create_client_from_env()",
    ]},
    {"name": "xhtml_sanitizer", "entityType": "module", "observations": [
        "src/fm_review/xhtml_sanitizer.py",
        "sanitize_xhtml(): removes scripts, event handlers, js URLs",
        "Checks: forbidden tags, blue headers, unknown macros, well-formedness",
    ]},
    {"name": "pipeline_tracer", "entityType": "module", "observations": [
        "src/fm_review/pipeline_tracer.py",
        "AgentResult dataclass: agent_id, status, cost_usd, duration, etc.",
        "PipelineTracer: Langfuse tracing for pipeline runs",
    ]},
    {"name": "langfuse_tracer", "entityType": "module", "observations": [
        "src/fm_review/langfuse_tracer.py",
        "Stop hook tracer: sends session data to Langfuse",
    ]},
]

# ── Architectural Decisions ────────────────────────────────────
DECISIONS = [
    {"name": "decision_confluence_only", "entityType": "decision", "observations": [
        "ADR: Confluence is the single source of truth for FM",
        "Rationale: business users read in Confluence, not in git",
        "Consequence: all agents read from Confluence, only Agent 7 writes",
    ]},
    {"name": "decision_lock_backup_retry", "entityType": "decision", "observations": [
        "ADR: All Confluence writes via lock + backup + retry (FC-01)",
        "Prevents concurrent write corruption, enables rollback",
    ]},
    {"name": "decision_infisical_secrets", "entityType": "decision", "observations": [
        "ADR: Infisical Universal Auth for secrets management",
        "Priority: Infisical -> keyring -> .env fallback",
        "Machine Identity: fm-review-pipeline, TTL 10 years",
    ]},
    {"name": "decision_no_ai_mentions", "entityType": "decision", "observations": [
        "ADR: Author always Shahovsky A.S., never mention AI/Agent/Claude/GPT",
        "Business requirement: FM appears human-authored to stakeholders",
    ]},
    {"name": "decision_quality_gate", "entityType": "decision", "observations": [
        "ADR: Mandatory Quality Gate before publishing to Confluence",
        "Checks: summary exists, CRITICAL findings addressed, tests pass",
    ]},
    {"name": "decision_github_issues", "entityType": "decision", "observations": [
        "ADR: GitHub Issues as persistent task tracking for agents",
        "Labels: agent:*, sprint:*, status:*, priority:*, type:*",
        "DoD enforcement: --comment required on close",
    ]},
    {"name": "decision_dod_enforcement", "entityType": "decision", "observations": [
        "ADR: Definition of Done checklist mandatory for every issue closure",
        "8 points: tests, regression, AC, artifacts, docs, debt",
        "Enforced by gh-tasks.sh: rejects close without comment",
    ]},
]

# ── Rules ──────────────────────────────────────────────────────
RULES = [
    {"name": "rule_smoke_testing", "entityType": "rule", "observations": [
        ".claude/rules/smoke-testing.md",
        "Mandatory smoke tests before delivery: pytest, scripts, secrets, CI",
        "Path-scoped: scripts/**, .claude/hooks/**, .github/workflows/**",
    ]},
    {"name": "rule_dod", "entityType": "rule", "observations": [
        ".claude/rules/dod.md",
        "Definition of Done: 8 mandatory points for issue closure",
        "Path-scoped: scripts/gh-tasks.sh, .claude/agents/**",
    ]},
    {"name": "rule_subagents_registry", "entityType": "rule", "observations": [
        ".claude/rules/subagents-registry.md",
        "12 agents: natural language routing table",
        "Maps user phrases to agent + command",
    ]},
    {"name": "rule_project_file_map", "entityType": "rule", "observations": [
        ".claude/rules/project-file-map.md",
        "Complete file map of the system: scripts, modules, hooks, MCP, skills",
    ]},
    {"name": "rule_confluence_mcp", "entityType": "rule", "observations": [
        ".claude/rules/confluence-mcp.md",
        "MCP tools table: which agent can use which Confluence tool",
    ]},
    {"name": "rule_agent_workflow", "entityType": "rule", "observations": [
        ".claude/rules/agent-workflow.md",
        "Plan -> Implement -> Fix cycle, deviation rules, GitHub Issues workflow",
    ]},
    {"name": "rule_knowledge_graph", "entityType": "rule", "observations": [
        ".claude/rules/knowledge-graph.md",
        "KG + Episodic Memory usage: what to record, when to search",
    ]},
    {"name": "rule_pipeline", "entityType": "rule", "observations": [
        ".claude/rules/pipeline.md",
        "Pipeline stages, budgets, resume, parallel execution details",
    ]},
    {"name": "rule_project_structure", "entityType": "rule", "observations": [
        ".claude/rules/project-structure.md",
        "Template for new projects, active projects list",
    ]},
    {"name": "rule_hooks_inventory", "entityType": "rule", "observations": [
        ".claude/rules/hooks-inventory.md",
        "All hooks: trigger, script, matcher, purpose",
    ]},
]

# ── CI/CD ──────────────────────────────────────────────────────
CICD = [
    {"name": "ci_pipeline", "entityType": "ci_cd", "observations": [
        ".github/workflows/ci.yml",
        "Steps: ruff -> ShellCheck -> pytest+coverage -> bandit -> pip-audit",
        "Coverage threshold: 50% (actual: 74%)",
        "Runs on push to main and PRs",
    ]},
    {"name": "ci_claude_review", "entityType": "ci_cd", "observations": [
        ".github/workflows/claude.yml",
        "Claude-powered PR review workflow",
    ]},
    {"name": "ci_security_review", "entityType": "ci_cd", "observations": [
        ".github/workflows/security-review.yml",
        "Security scanning workflow for PRs",
    ]},
]

# ── Key Documents ──────────────────────────────────────────────
DOCUMENTS = [
    {"name": "doc_claude_md", "entityType": "document", "observations": [
        "CLAUDE.md: main project instructions (~55 lines)",
        "Orchestrator role, routing table, pipeline, secrets, business cycle",
    ]},
    {"name": "doc_common_rules", "entityType": "document", "observations": [
        "agents/COMMON_RULES.md: compact agent rules (~47 lines)",
        "26 rules covering communication, Confluence, format, governance",
    ]},
    {"name": "doc_agent_protocol", "entityType": "document", "observations": [
        "AGENT_PROTOCOL.md: formal agent behavior protocol",
    ]},
    {"name": "doc_handoff", "entityType": "document", "observations": [
        "HANDOFF.md: session-to-session context handoff",
    ]},
    {"name": "doc_changelog", "entityType": "document", "observations": [
        "docs/CHANGELOG.md: system change history",
    ]},
    {"name": "doc_confluence_template", "entityType": "document", "observations": [
        "docs/CONFLUENCE_TEMPLATE.md: XHTML template for FM pages",
    ]},
    {"name": "doc_contract_confluence", "entityType": "document", "observations": [
        "docs/CONTRACT_CONFLUENCE_FM.md: Confluence integration contract",
    ]},
    {"name": "doc_model_selection", "entityType": "document", "observations": [
        "docs/MODEL_SELECTION.md: model and budget selection per agent",
    ]},
    {"name": "doc_agent_template", "entityType": "document", "observations": [
        "docs/AGENT_TEMPLATE.md: template for creating new agents",
    ]},
    {"name": "doc_bootstrap_prompt", "entityType": "document", "observations": [
        "docs/ORCHESTRATOR_BOOTSTRAP_PROMPT.md: initial system prompt",
    ]},
]

# ── Infrastructure ─────────────────────────────────────────────
INFRA = [
    {"name": "infra_langfuse", "entityType": "infrastructure", "observations": [
        "infra/langfuse/: self-hosted Langfuse v3 (Docker Compose)",
        "Observability: traces, costs, agent performance",
    ]},
    {"name": "infra_infisical", "entityType": "infrastructure", "observations": [
        "Infisical hosted: https://infisical.shakhoff.com",
        "Machine Identity: fm-review-pipeline (Universal Auth, TTL 10 years)",
        "infra/infisical/.env.machine-identity (in .gitignore)",
    ]},
    {"name": "infra_tg_bot", "entityType": "infrastructure", "observations": [
        "scripts/tg-bot.py + infra/fm-tg-bot.service (systemd)",
        "Telegram bot: responds to /report in chat",
    ]},
    {"name": "infra_cron", "entityType": "infrastructure", "observations": [
        "scripts/cron-tg-report.sh: 9:00 yesterday report, 18:00 today report",
    ]},
    {"name": "schema_agent_contracts", "entityType": "schema", "observations": [
        "schemas/agent-contracts.json (v2.2)",
        "Multi-platform support, _summary.json and _findings.json schemas",
    ]},
    {"name": "infisical_json", "entityType": "config", "observations": [
        "infisical.json: project config for Infisical CLI",
    ]},
    {"name": "pyproject_toml", "entityType": "config", "observations": [
        "pyproject.toml: Python project config",
        "Dependencies, ruff config, pytest config, bandit config",
    ]},
]

# ── Patch Patterns ─────────────────────────────────────────────
PATCHES = [
    {"name": "patch_boundary_conditions", "entityType": "patch_pattern", "observations": [
        "Pattern: business rules lack boundary conditions (0, negative, max)",
        "Agent 1 must always check for edge cases",
    ]},
    {"name": "patch_broken_crossref", "entityType": "patch_pattern", "observations": [
        "Pattern: section A references B but B doesn't reference A",
        "Cross-references must be bidirectional",
    ]},
    {"name": "patch_misleading_name", "entityType": "patch_pattern", "observations": [
        "Pattern: field/entity name doesn't match actual semantics",
        "Names must be self-explanatory",
    ]},
    {"name": "patch_note_contradiction", "entityType": "patch_pattern", "observations": [
        "Pattern: exception note contradicts the main business rule",
        "Notes must be consistent with rules",
    ]},
    {"name": "patch_missing_terminal_state", "entityType": "patch_pattern", "observations": [
        "Pattern: approval workflow lacks reject/cancel/timeout states",
        "All workflows must define terminal states",
    ]},
    {"name": "patch_untestable_approval", "entityType": "patch_pattern", "observations": [
        "Pattern: approval flow has no max iteration or timeout",
        "Must define exit conditions for approval cycles",
    ]},
]

# ── Business Concepts ──────────────────────────────────────────
BUSINESS = [
    {"name": "concept_fm", "entityType": "concept", "observations": [
        "Functional Model (FM): main deliverable describing business process",
        "Structure: meta, code system, rules, tables, history, warnings",
        "Versioned: X.Y.Z, stored in Confluence",
    ]},
    {"name": "concept_business_review", "entityType": "concept", "observations": [
        "Business review cycle: DRAFT -> PUBLISHED -> BUSINESS REVIEW -> REWORK -> APPROVED",
        "Max 5 iterations, timeout 7 business days",
        "Agent 2 does preventive critique before business sees it",
    ]},
    {"name": "concept_1c_platform", "entityType": "concept", "observations": [
        "1C:Enterprise platform: UT (Trade Management), ERP, KA",
        "Extension-based customization, Vanessa Automation for testing",
    ]},
    {"name": "concept_code_system", "entityType": "concept", "observations": [
        "Code system in FM: prefixed identifiers (LS-BR-XXX, LS-DOC-XXX, etc.)",
        "Each code has unique prefix per domain (BR=business rule, DOC=document)",
    ]},
    {"name": "concept_quality_gate", "entityType": "concept", "observations": [
        "Quality Gate: mandatory check before publishing FM to Confluence",
        "Ensures all CRITICAL findings addressed, tests pass, summaries valid",
        "Exit codes: 0=ready, 1=block, 2=warnings (can skip with --reason)",
    ]},
    {"name": "concept_kafka_bus", "entityType": "concept", "observations": [
        "Kafka: data exchange bus between 1С and Go services",
        "Architecture: 1С → Outbox → HTTP Gateway → Kafka → Go consumers",
        "Topics: 1c.<domain>.<event>.v<N>, cmd.*, evt.*, *.dlq, *.retry.*",
        "1С side: Outbox pattern (transactional), NativeAPI or REST Proxy",
        "Go side: franz-go (pure Go, fastest), GroupTransactSession for EOS",
        "DLQ + 3-level retry for error handling",
        "Schema Registry: Protobuf/Avro via franz-go/pkg/sr",
        "See: knowledge-base/integrations.md (TO BE section)",
    ]},
    {"name": "concept_1c_multiconfig", "entityType": "concept", "observations": [
        "1С multi-config support: not just УТ 10.2",
        "УТ 10.2: ordinary forms only, no client/server, compatibility 8.3.9",
        "УТ 11.5: managed forms, full extensions, BSP 3.1.x",
        "ERP 2.5: 14+ subsystems, full extension support, don't break BSP",
        "БП 3.0: DON'T touch chart of accounts, regulated reporting",
        "ЗУП 3.1: DON'T change calculation registers, 5-level hierarchy",
        "УХ: group-aware extensions, DON'T touch IFRS consolidation",
        "ДО 3.0: DON'T break business process chains, digital signatures",
        "See: knowledge-base/1c-landscape.md",
    ]},
    {"name": "concept_pipeline_stages", "entityType": "concept", "observations": [
        "Review Pipeline: Agent 1(audit) -> 2 -> 1(defense) -> 5 -> [9|10] -> QG -> 7 -> [8,15]",
        "Dev Pipeline: [11|12] -> [13|14] -> 7",
        "Parallel stages: [8,15] and conditional [9|10], [11|12], [13|14]",
        "Per-agent budgets, resume support, Langfuse tracing",
        "Three modes: quick ($25), standard ($35), full ($55)",
    ]},
]

# ── Pipeline stages ────────────────────────────────────────────
PIPELINE = {
    "name": "FM_Pipeline",
    "entityType": "pipeline",
    "observations": [
        "Two phases: FM Review + Development (on demand)",
        "Review: [[1], [2], [1:defense], [5], [9|10], [quality_gate], [7], [8,15]]",
        "Dev: [[11|12], [13|14], [7]]",
        "Agent 1 runs twice: audit (pass 1) then defense (pass 2 after Agent 2)",
        "Agents 8 and 15 run in parallel",
        "Agents 9/10 are conditional based on platform (go/1c)",
        "Agents 11/12 and 13/14 are conditional based on platform (dev phase)",
        "Three modes: quick ($25), standard ($35), full ($55)",
        "Quality Gate mandatory before Agent 7",
        "Managed by scripts/run_agent.py (Claude Code SDK)",
        "Langfuse tracing: PipelineTracer in run_agent.py",
    ],
}

# ── Relations ──────────────────────────────────────────────────
RELATIONS = [
    ("Agent1_Architect", "Agent2_RoleSimulator", "provides_findings_to"),
    ("Agent2_RoleSimulator", "Agent1_Architect", "provides_findings_for_defense"),
    ("Agent2_RoleSimulator", "Agent5_TechArchitect", "provides_ux_to"),
    ("Agent7_Publisher", "FM_Pipeline", "publishes_for"),
    ("Agent0_Creator", "Agent7_Publisher", "sends_content_to"),
    ("Agent5_TechArchitect", "Agent7_Publisher", "sends_docs_to"),
    ("Agent15_Trainer", "FM_Pipeline", "documents_for"),
    ("Orchestrator_Helper", "FM_Pipeline", "orchestrates"),
    ("Orchestrator_Helper", "Agent0_Creator", "delegates_fm_to"),
    ("Orchestrator_Helper", "Agent1_Architect", "delegates_fm_to"),
    # Agent 9-10 (conditional SE review)
    ("Agent9_SE_Go", "FM_Pipeline", "extends"),
    ("Agent10_SE_1C", "FM_Pipeline", "extends"),
    # Agent 11-14 (dev phase)
    ("Agent5_TechArchitect", "Agent11_Dev1C", "provides_tz_to"),
    ("Agent5_TechArchitect", "Agent12_DevGo", "provides_tz_to"),
    ("Agent11_Dev1C", "Agent13_QA1C", "provides_code_to"),
    ("Agent12_DevGo", "Agent14_QAGo", "provides_code_to"),
    ("Agent10_SE_1C", "Agent11_Dev1C", "provides_review_to"),
    ("Agent9_SE_Go", "Agent12_DevGo", "provides_review_to"),
    ("Agent13_QA1C", "Agent15_Trainer", "provides_bdd_to"),
    # Kafka relations
    ("concept_kafka_bus", "Agent11_Dev1C", "implemented_by"),
    ("concept_kafka_bus", "Agent12_DevGo", "implemented_by"),
    ("concept_kafka_bus", "Agent13_QA1C", "tested_by"),
    ("concept_kafka_bus", "Agent14_QAGo", "tested_by"),
    ("concept_1c_multiconfig", "Agent11_Dev1C", "supported_by"),
    ("concept_1c_multiconfig", "Agent13_QA1C", "tested_by"),
    # Scripts
    ("run_agent_py", "FM_Pipeline", "executes"),
    ("publish_to_confluence_py", "confluence_utils", "uses"),
    ("export_from_confluence_py", "confluence_utils", "uses"),
    ("quality_gate_sh", "FM_Pipeline", "gates"),
    ("gh_tasks_sh", "mcp_github", "wraps"),
    # Hooks to scripts
    ("hook_guard_confluence_write", "publish_to_confluence_py", "enforces_use_of"),
    ("hook_validate_summary", "quality_gate_sh", "prepares_for"),
    # MCP to agents
    ("mcp_confluence", "Agent7_Publisher", "used_by"),
    ("mcp_memory", "Orchestrator_Helper", "used_by"),
    ("mcp_playwright", "Agent9_SE_Go", "used_by"),
    # Skills to agents
    ("skill_quality_gate", "Agent7_Publisher", "preloaded_for"),
    ("skill_fm_audit", "Agent1_Architect", "preloaded_for"),
    # Decisions
    ("decision_confluence_only", "Agent7_Publisher", "affects"),
    ("decision_lock_backup_retry", "confluence_utils", "implemented_in"),
    ("decision_quality_gate", "quality_gate_sh", "implemented_in"),
    ("decision_github_issues", "gh_tasks_sh", "implemented_in"),
]


def discover_projects() -> list[dict]:
    """Discover active projects from projects/ directory."""
    entities = []
    projects_dir = PROJECT_ROOT / "projects"
    if not projects_dir.exists():
        return entities

    for project_dir in sorted(projects_dir.glob("PROJECT_*")):
        if not project_dir.is_dir():
            continue

        name = project_dir.name
        observations = [f"Directory: projects/{name}"]

        # PAGE_ID
        page_id_file = project_dir / "CONFLUENCE_PAGE_ID"
        if page_id_file.exists():
            page_id = page_id_file.read_text().strip()
            if page_id:
                observations.append(f"Confluence PAGE_ID: {page_id}")

        # FM version from PROJECT_CONTEXT.md
        ctx_file = project_dir / "PROJECT_CONTEXT.md"
        if ctx_file.exists():
            import re

            content = ctx_file.read_text(encoding="utf-8")
            ver_match = re.search(r"v(\d+\.\d+\.\d+)", content)
            if ver_match:
                observations.append(f"FM version: v{ver_match.group(1)}")

            # FM code
            code_match = re.search(r"FM-[\w-]+", content)
            if code_match:
                observations.append(f"FM code: {code_match.group(0)}")

        # Agent results
        agent_dirs = sorted(project_dir.glob("AGENT_*"))
        completed = [d.name for d in agent_dirs if any(d.glob("*.md"))]
        if completed:
            observations.append(f"Completed agents: {', '.join(completed)}")

        # Changes
        changes_dir = project_dir / "CHANGES"
        if changes_dir.exists():
            changes = list(changes_dir.glob("*-CHANGES.md"))
            if changes:
                observations.append(f"Change logs: {len(changes)}")

        entities.append(
            {
                "name": name,
                "entityType": "project",
                "observations": observations,
            }
        )

    return entities


def write_memory(entities: list[dict], relations: list[tuple], reset: bool = False):
    """Write entities and relations to memory.jsonl."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if reset and MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
        print("Reset: existing memory.jsonl deleted")

    # Read existing data to avoid duplicates
    # Handles both old format (no "type" field) and MCP format (with "type" field)
    existing_names = set()
    existing_rels = set()
    if MEMORY_FILE.exists():
        for line in MEMORY_FILE.read_text().splitlines():
            if line.strip():
                try:
                    obj = json.loads(line)
                    obj_type = obj.get("type", "")
                    if obj_type == "entity" or ("name" in obj and "entityType" in obj):
                        existing_names.add(obj["name"])
                    elif obj_type == "relation" or ("from" in obj and "to" in obj):
                        existing_rels.add((obj["from"], obj["to"], obj["relationType"]))
                except json.JSONDecodeError:
                    pass

    added = 0
    rels_added = 0
    with open(MEMORY_FILE, "a") as f:
        for entity in entities:
            if entity["name"] not in existing_names:
                # MCP server-memory requires "type" field to load entries
                record = {"type": "entity", **entity}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                added += 1
                existing_names.add(entity["name"])

        for from_name, to_name, rel_type in relations:
            rel_key = (from_name, to_name, rel_type)
            if rel_key not in existing_rels:
                rel = {"type": "relation", "from": from_name, "to": to_name, "relationType": rel_type}
                f.write(json.dumps(rel, ensure_ascii=False) + "\n")
                rels_added += 1
                existing_rels.add(rel_key)

    return added


def main():
    reset = "--reset" in sys.argv

    # Collect all entities
    entities = (AGENTS + [PIPELINE] + SCRIPTS + HOOKS + MCP_SERVERS + SKILLS
                + MODULES + DECISIONS + RULES + CICD + DOCUMENTS + INFRA + PATCHES + BUSINESS)
    projects = discover_projects()
    entities.extend(projects)

    # Project-to-pipeline relations
    project_relations = list(RELATIONS)
    for proj in projects:
        project_relations.append((proj["name"], "FM_Pipeline", "uses_pipeline"))

    added = write_memory(entities, project_relations, reset=reset)

    print(f"Knowledge graph: {MEMORY_FILE}")
    print(f"  Entities added: {added}")
    print(f"  Relations added: {len(project_relations)}")
    print(f"  Projects found: {len(projects)}")

    # Summary
    if MEMORY_FILE.exists():
        lines = MEMORY_FILE.read_text().splitlines()
        print(f"  Total lines: {len(lines)}")


if __name__ == "__main__":
    main()
