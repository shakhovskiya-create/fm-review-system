#!/usr/bin/env python3
"""
Pipeline runner for FM Review agents using Claude Code SDK.

Uses claude-code-sdk for programmatic agent execution with optional
Langfuse tracing for cost, usage, and agent observability.

Usage:
  # Full pipeline:
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT

  # Parallel pipeline (independent agents run concurrently):
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --parallel

  # Selective agents:
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --agents 1,2,4

  # Single agent:
  python3 scripts/run_agent.py --agent 1 --project PROJECT_SHPMNT_PROFIT

  # Dry run (show prompts without execution):
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run

Requirements:
  - Claude Code CLI (claude) installed and authorized
  - pip install claude-code-sdk
  - Optional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY for tracing
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from claude_code_sdk import (
    ClaudeCodeOptions,
    ResultMessage,
    query,
)

from fm_review.pipeline_tracer import AgentResult, PipelineTracer  # noqa: F401

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# --- Configuration ---

CONFIG_PATH = ROOT_DIR / "config" / "pipeline.json"
try:
    _CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError) as e:
    print(f"Error loading pipeline config: {e}", file=sys.stderr)
    sys.exit(1)

AGENT_REGISTRY = {int(k): v for k, v in _CONFIG["AGENT_REGISTRY"].items()}
PIPELINE_BUDGET_USD = _CONFIG.get("PIPELINE_BUDGET_USD", 60.0)
PIPELINE_ORDER = _CONFIG.get("PIPELINE_ORDER", [1, 2, 4, 5, 3, "quality_gate", 7, 8, 6])
PARALLEL_STAGES = _CONFIG.get("PARALLEL_STAGES", [])
CONDITIONAL_STAGES = {int(k): v for k, v in _CONFIG.get("CONDITIONAL_STAGES", {}).items()}


# --- Prompt Injection Protection ---

# Patterns that indicate prompt injection attempts in FM content or user input
_INJECTION_PATTERNS = [
    # Direct instruction overrides
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)disregard\s+(all\s+)?above",
    r"(?i)forget\s+(everything|all|your)\s+(above|instructions|rules)",
    r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|free)",
    r"(?i)system\s*prompt\s*[:=]",
    r"(?i)assistant\s*prompt\s*[:=]",
    # Delimiter injection (trying to close/open system blocks)
    r"</?system>",
    r"</?assistant>",
    r"</?user>",
    r"\[SYSTEM\]",
    r"\[INST\]",
    r"<<SYS>>",
    # Tool/action manipulation
    r"(?i)execute\s+(?:this\s+)?(?:bash|shell)\s+(?:command\s*)?:",
    r"(?i)run\s+(?:the\s+)?following\s+(?:bash|shell)\s+command",
    r"(?i)use\s+(?:the\s+)?(?:bash|write)\s+tool\s+to",
    # Secret extraction
    r"(?i)(?:print|show|reveal|output|display)\s+(?:all\s+)?(?:env|environment|secret|token|key|password)",
    r"(?i)(?:cat|echo|read)\s+\.env",
]

_INJECTION_RE = [re.compile(p) for p in _INJECTION_PATTERNS]


def check_prompt_injection(text: str, source: str = "input") -> list[str]:
    """Check text for prompt injection patterns. Returns list of warnings."""
    warnings = []
    for i, pattern in enumerate(_INJECTION_RE):
        match = pattern.search(text)
        if match:
            # Truncate match context for logging (no secrets)
            ctx = text[max(0, match.start() - 20):match.end() + 20].replace("\n", " ")
            warnings.append(
                f"[INJECTION] Pattern #{i} matched in {source}: ...{ctx}..."
            )
    return warnings


def validate_pipeline_input(project: str, command: str) -> list[str]:
    """Validate pipeline inputs for injection. Returns warnings."""
    warnings = []

    # Check command
    warnings.extend(check_prompt_injection(command, "command"))

    # Check project FM content (if exists on disk)
    project_dir = ROOT_DIR / "projects" / project
    if project_dir.is_dir():
        # Scan FM documents for injection
        for fm_file in project_dir.glob("FM_DOCUMENTS/*.md"):
            try:
                content = fm_file.read_text(encoding="utf-8")[:50000]  # limit scan
                file_warnings = check_prompt_injection(content, f"FM:{fm_file.name}")
                warnings.extend(file_warnings)
            except OSError:
                pass

        # Scan CHANGES for injection
        for change_file in project_dir.glob("CHANGES/*.md"):
            try:
                content = change_file.read_text(encoding="utf-8")[:20000]
                file_warnings = check_prompt_injection(content, f"CHANGES:{change_file.name}")
                warnings.extend(file_warnings)
            except OSError:
                pass

    return warnings


# --- Utilities ---

def log(msg: str):
    """Log with timestamp to stderr."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr)


def find_summary_json(project: str, agent_id: int) -> Path | None:
    """Find the most recent _summary.json for an agent."""
    config = AGENT_REGISTRY[agent_id]
    agent_dir = ROOT_DIR / "projects" / project / config["dir"]
    if not agent_dir.is_dir():
        return None
    summaries = sorted(
        agent_dir.glob("*_summary.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return summaries[0] if summaries else None


def check_agent_status(summary_path: Path) -> str:
    """Read status from _summary.json."""
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        return data.get("status", "completed")
    except (json.JSONDecodeError, OSError):
        return "completed"


# --- Prompt builder ---

def build_prompt(agent_id: int, project: str, command: str) -> str:
    """Build prompt for agent execution."""
    config = AGENT_REGISTRY[agent_id]
    agent_file = ROOT_DIR / "agents" / config["file"]
    project_dir = ROOT_DIR / "projects" / project

    parts = []

    # 1. Role instruction
    parts.append(f"Прочитай и используй роль из {agent_file}")
    parts.append("")

    # 2. Project context
    parts.append(f"Проект: {project}")
    context_file = project_dir / "PROJECT_CONTEXT.md"
    if context_file.exists():
        parts.append(f"Прочитай контекст проекта из {context_file}")

    # 3. Confluence PAGE_ID
    page_id_file = project_dir / "CONFLUENCE_PAGE_ID"
    if page_id_file.exists():
        page_id = page_id_file.read_text(encoding="utf-8").strip()
        if page_id:
            parts.append(f"Confluence PAGE_ID: {page_id}")

    # 4. Previous agent results
    prev_dirs = []
    for agent_dir in sorted(project_dir.glob("AGENT_*")):
        if not agent_dir.is_dir():
            continue
        files = list(agent_dir.glob("*.md")) + list(agent_dir.glob("*_summary.json"))
        if files:
            prev_dirs.append(f"  - {agent_dir.name}/ ({len(files)} файлов)")
    if prev_dirs:
        parts.append("")
        parts.append("Результаты предыдущих агентов:")
        parts.extend(prev_dirs)

    # 5. Autonomous mode instructions
    parts.append("")
    parts.append("ВАЖНО: Это АВТОНОМНЫЙ запуск конвейера.")
    parts.append("- НЕ задавай вопросов. Используй режим /auto.")
    parts.append("- Читай все нужные файлы через инструмент Read.")
    parts.append("- Сохраняй результаты в папку проекта.")
    parts.append(
        f"- После завершения ОБЯЗАТЕЛЬНО создай _summary.json "
        f"в {project_dir / config['dir']}/"
    )
    parts.append(
        "- _summary.json должен содержать: "
        "agent, command, timestamp, fmVersion, project, status"
    )
    parts.append("")

    # 6. Command
    parts.append(command)

    return "\n".join(parts)


# --- Agent execution (SDK) ---

async def run_single_agent(
    agent_id: int,
    project: str,
    command: str = "/auto",
    model: str = "sonnet",
    dry_run: bool = False,
    max_budget: float = 5.0,
    timeout: int = 600,
) -> AgentResult:
    """Run a single agent using Claude Code SDK."""
    config = AGENT_REGISTRY[agent_id]
    prompt = build_prompt(agent_id, project, command)

    if dry_run:
        log(f"[DRY RUN] Agent {agent_id} ({config['name']})")
        log(f"  Команда: {command}")
        log(f"  Промпт ({len(prompt)} символов):")
        for line in prompt.split("\n"):
            log(f"    {line}")
        return AgentResult(agent_id=agent_id, status="dry_run")

    log(f"Agent {agent_id} ({config['name']}): ЗАПУСК")

    # CRITICAL-S2: isolate agent cwd to project directory
    project_dir = ROOT_DIR / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)

    options = ClaudeCodeOptions(
        model=model,
        permission_mode="acceptEdits",
        max_turns=25,
        cwd=str(project_dir),
        append_system_prompt=(
            f"Ты Agent {agent_id} ({config['name']}) в автономном конвейере. "
            f"Проект: {project}. НЕ задавай вопросов. "
            f"Выполни команду полностью и создай _summary.json."
        ),
        extra_args={"max-budget-usd": str(max_budget)},
    )

    start_time = time.time()
    result_msg: ResultMessage | None = None

    try:
        async def _run():
            nonlocal result_msg
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_msg = message

        await asyncio.wait_for(_run(), timeout=timeout)

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        log(f"Agent {agent_id} ({config['name']}): ТАЙМАУТ ({duration:.1f}с)")
        return AgentResult(
            agent_id=agent_id,
            status="timeout",
            duration_seconds=duration,
            exit_code=1,
            error=f"Timeout after {timeout}s",
        )
    except (asyncio.CancelledError, OSError, RuntimeError) as e:
        duration = time.time() - start_time
        log(f"Agent {agent_id} ({config['name']}): ОШИБКА: {e}")
        return AgentResult(
            agent_id=agent_id,
            status="failed",
            duration_seconds=duration,
            error=str(e)[:500],
        )

    duration = time.time() - start_time
    cost = 0.0
    is_error = False
    num_turns = 0
    session_id = ""

    if result_msg:
        cost = result_msg.total_cost_usd or 0.0
        is_error = result_msg.is_error
        num_turns = result_msg.num_turns
        session_id = result_msg.session_id
        duration = result_msg.duration_ms / 1000 if result_msg.duration_ms else duration

    # Check budget exceeded (agent cost > allocated budget)
    if cost > max_budget and max_budget > 0:
        log(f"Agent {agent_id} ({config['name']}): BUDGET EXCEEDED (${cost:.2f} > ${max_budget:.2f})")
        return AgentResult(
            agent_id=agent_id,
            status="budget_exceeded",
            duration_seconds=duration,
            exit_code=1,
            cost_usd=cost,
            num_turns=num_turns,
            session_id=session_id,
            error=f"Budget exceeded: ${cost:.2f} > ${max_budget:.2f}",
        )

    # Check _summary.json
    summary_path = find_summary_json(project, agent_id)
    if summary_path:
        status = check_agent_status(summary_path)
    elif is_error:
        status = "failed"
    else:
        status = "completed"

    log(f"Agent {agent_id} ({config['name']}): {status.upper()} "
        f"({duration:.1f}с, ${cost:.2f}, {num_turns} turns)")

    return AgentResult(
        agent_id=agent_id,
        status=status,
        summary_path=summary_path,
        duration_seconds=duration,
        exit_code=1 if is_error else 0,
        cost_usd=cost,
        num_turns=num_turns,
        session_id=session_id,
        error=(result_msg.result or "")[:500] if result_msg and is_error else "",
    )


# --- Quality Gate ---

def run_quality_gate(project: str) -> tuple[int, str]:
    """Run quality_gate.sh. Returns (exit_code, output)."""
    qg_script = SCRIPT_DIR / "quality_gate.sh"
    if not qg_script.exists():
        return 1, f"quality_gate.sh not found: {qg_script}"
    try:
        result = subprocess.run(
            ["bash", str(qg_script), project],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT_DIR),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Quality Gate: timeout"
    except OSError as e:
        return 1, f"Quality Gate: error: {e}"


def _qg_failure_is_agent4_related(output: str) -> bool:
    """Check if QG failure is caused by missing Agent 4 (QA) results."""
    agent4_patterns = [
        "CRITICAL findings без покрытия тестами",
        "Матрица трассируемости отсутствует",
        "Тест-кейсы: не выполнен",
        "Тест-кейсы: папка есть, отчетов нет",
        "_summary.json не найден",
        "AGENT_4_QA_TESTER",
    ]
    output_lower = output.lower()
    for pattern in agent4_patterns:
        if pattern.lower() in output_lower:
            return True
    return False


def run_quality_gate_with_reason(project: str, reason: str) -> int:
    """Run quality_gate.sh with --reason to skip warnings."""
    qg_script = SCRIPT_DIR / "quality_gate.sh"
    try:
        result = subprocess.run(
            ["bash", str(qg_script), project, "--reason", reason],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT_DIR),
        )
        return result.returncode
    except OSError:
        return 1


# --- Checkpoint ---

def save_checkpoint(project: str, results: dict, total_cost: float, model: str, parallel: bool):
    """Save pipeline checkpoint after each completed step."""
    state_file = ROOT_DIR / "projects" / project / ".pipeline_state.json"
    state = {
        "project": project,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_cost_usd": round(total_cost, 2),
        "model": model,
        "mode": "parallel" if parallel else "sequential",
        "completed_steps": [
            k for k, v in results.items()
            if v.get("status") in ("completed", "passed", "passed_after_retry", "warnings_skipped", "dry_run")
        ],
        "failed_steps": [
            k for k, v in results.items()
            if v.get("status") in ("failed", "timeout", "budget_exceeded", "injection_detected")
        ],
        "results": results,
    }
    state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return state_file


def load_checkpoint(project: str) -> dict | None:
    """Load pipeline checkpoint. Returns None if no checkpoint exists."""
    state_file = ROOT_DIR / "projects" / project / ".pipeline_state.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# --- Pipeline ---

async def run_pipeline(
    project: str,
    agents_filter: list[int] | None = None,
    model: str = "sonnet",
    dry_run: bool = False,
    max_budget_per_agent: float = 5.0,
    timeout_per_agent: int = 600,
    skip_qg_warnings: bool = False,
    parallel: bool = False,
    resume: bool = False,
) -> dict:
    """Run the full agent pipeline with optional Langfuse tracing.

    When parallel=True, independent agents run concurrently
    (e.g., Agent 2 + Agent 4 in one stage).
    """
    results = {}
    total_start = time.time()
    total_cost = 0.0
    pipeline_stopped = False
    _qg_retried: set[int] = set()  # Track QG auto-retry (max 1 per agent)

    # Resume: load checkpoint and skip completed steps
    skip_steps: set = set()
    if resume:
        checkpoint = load_checkpoint(project)
        if checkpoint and checkpoint.get("completed_steps"):
            skip_steps = set(checkpoint["completed_steps"])
            # Restore cost from previous run
            total_cost = checkpoint.get("total_cost_usd", 0.0)
            # Restore completed results
            for step_key in skip_steps:
                if step_key in checkpoint.get("results", {}):
                    results[step_key] = checkpoint["results"][step_key]
            log(f"RESUME: пропуск {len(skip_steps)} завершённых шагов: {sorted(skip_steps, key=str)}")
            # If there were failed steps, report them
            failed = checkpoint.get("failed_steps", [])
            if failed:
                log(f"RESUME: повторный запуск неудавшихся шагов: {failed}")
        else:
            log("RESUME: чекпоинт не найден или пуст, запуск с начала")

    # Initialize Langfuse tracer (no-op if LANGFUSE_PUBLIC_KEY not set)
    tracer = PipelineTracer(project, model, parallel)
    if not dry_run:
        tracer.start_pipeline()
        if tracer.enabled:
            log("Langfuse: трейсинг активен")

    # Build stages (inject conditional agents 9/10 based on platform)
    if parallel:
        stages = _build_parallel_stages(agents_filter, project)
        mode_label = "ПАРАЛЛЕЛЬНЫЙ"
    else:
        stages = _build_sequential_stages(agents_filter, project)
        mode_label = "ПОСЛЕДОВАТЕЛЬНЫЙ"

    # Calculate total pipeline budget
    pipeline_budget = PIPELINE_BUDGET_USD

    log(f"{'=' * 60}")
    log(f"  КОНВЕЙЕР ({mode_label}): {project}")
    log(f"  Стадии: {stages}")
    log(f"  Модель: {model}, Бюджет: ${pipeline_budget:.0f}")
    log(f"{'=' * 60}")

    # Prompt injection scan
    if not dry_run:
        injection_warnings = validate_pipeline_input(project, "/auto")
        if injection_warnings:
            log("")
            log(f"  ВНИМАНИЕ: обнаружено {len(injection_warnings)} подозрительных паттернов:")
            for w in injection_warnings[:5]:
                log(f"    {w}")
            if len(injection_warnings) > 5:
                log(f"    ...и ещё {len(injection_warnings) - 5}")
            # Hard stop on 3+ patterns (likely deliberate injection attack)
            if len(injection_warnings) >= 3:
                log("  КОНВЕЙЕР ОСТАНОВЛЕН: слишком много injection-паттернов (>=3).")
                results["injection_scan"] = {
                    "status": "injection_detected",
                    "warnings_count": len(injection_warnings),
                }
                if not dry_run:
                    save_checkpoint(project, results, total_cost, model, parallel)
                tracer.finish(total_cost, 0.0, results)
                return results
            log("  Конвейер продолжает работу с предупреждением.")
            log("")

    for stage_idx, stage in enumerate(stages, 1):
        if pipeline_stopped:
            break

        # Quality Gate
        if stage == ["quality_gate"]:
            if "quality_gate" in skip_steps:
                log(f"\n--- Стадия {stage_idx}: QUALITY GATE [ПРОПУСК — resume] ---")
                continue

            log("")
            log(f"--- Стадия {stage_idx}: QUALITY GATE ---")

            if dry_run:
                log("  [DRY RUN] quality_gate.sh")
                results["quality_gate"] = {"status": "dry_run"}
                continue

            qg_span = tracer.start_quality_gate()
            exit_code, output = run_quality_gate(project)

            for line in output.strip().split("\n")[-10:]:
                log(f"  {line}")

            # AUTO-RETRY: if QG failed due to Agent 4 (QA) issues, retry Agent 4 once
            if exit_code == 1 and _qg_failure_is_agent4_related(output) and 4 not in _qg_retried:
                _qg_retried.add(4)
                log("")
                log("  AUTO-RETRY: QG failure related to Agent 4 (QA). Перезапуск Agent 4...")
                tracer.end_quality_gate(qg_span, exit_code, "retry_agent4")

                retry_span = tracer.start_agent(4, "QATester-retry")
                agent4_model = model if model != "sonnet" else AGENT_REGISTRY[4].get("model", model)
                agent4_budget = AGENT_REGISTRY[4].get("budget_usd", 3.0)
                agent4_timeout = AGENT_REGISTRY[4].get("timeout_seconds", timeout_per_agent)
                retry_result = await run_single_agent(
                    agent_id=4,
                    project=project,
                    command="/auto --retry: покрой все CRITICAL findings тестами, обнови traceability-matrix.json",
                    model=agent4_model,
                    dry_run=dry_run,
                    max_budget=agent4_budget,
                    timeout=agent4_timeout,
                )
                total_cost += retry_result.cost_usd
                results["agent4_retry"] = {
                    "status": retry_result.status,
                    "duration": round(retry_result.duration_seconds, 1),
                    "cost_usd": round(retry_result.cost_usd, 2),
                    "num_turns": retry_result.num_turns,
                    "session_id": retry_result.session_id,
                }
                tracer.end_agent(retry_span, retry_result)

                if retry_result.status == "failed":
                    log("  AUTO-RETRY Agent 4: FAILED. Останавливаем конвейер.")
                    results["quality_gate"] = {"status": "failed", "exit_code": 1}
                    pipeline_stopped = True
                else:
                    log("  AUTO-RETRY Agent 4: OK. Повторяем Quality Gate...")
                    qg_span2 = tracer.start_quality_gate()
                    exit_code, output = run_quality_gate(project)
                    for line in output.strip().split("\n")[-10:]:
                        log(f"  {line}")
                    if exit_code == 0:
                        log("Quality Gate (retry): все проверки пройдены.")
                        results["quality_gate"] = {"status": "passed_after_retry"}
                        tracer.end_quality_gate(qg_span2, exit_code, "passed_after_retry")
                    elif exit_code == 2 and skip_qg_warnings:
                        log("Quality Gate (retry): предупреждения пропущены.")
                        run_quality_gate_with_reason(project, "Автопропуск после retry Agent 4")
                        results["quality_gate"] = {"status": "warnings_skipped"}
                        tracer.end_quality_gate(qg_span2, exit_code, "warnings_skipped")
                    else:
                        log(f"КОНВЕЙЕР ОСТАНОВЛЕН: Quality Gate (retry) exit={exit_code}.")
                        results["quality_gate"] = {"status": "failed", "exit_code": exit_code}
                        tracer.end_quality_gate(qg_span2, exit_code, "failed")
                        pipeline_stopped = True
            elif exit_code == 1:
                log("КОНВЕЙЕР ОСТАНОВЛЕН: критические ошибки Quality Gate.")
                results["quality_gate"] = {"status": "failed", "exit_code": 1}
                tracer.end_quality_gate(qg_span, exit_code, "failed")
                pipeline_stopped = True
            elif exit_code == 2:
                if skip_qg_warnings:
                    log("Quality Gate: предупреждения пропущены (--skip-qg-warnings).")
                    run_quality_gate_with_reason(
                        project, "Автопропуск в автономном конвейере"
                    )
                    results["quality_gate"] = {"status": "warnings_skipped"}
                    tracer.end_quality_gate(qg_span, exit_code, "warnings_skipped")
                else:
                    log("КОНВЕЙЕР ОСТАНОВЛЕН: предупреждения Quality Gate.")
                    log("  Используйте --skip-qg-warnings для продолжения.")
                    results["quality_gate"] = {"status": "warnings", "exit_code": 2}
                    tracer.end_quality_gate(qg_span, exit_code, "warnings")
                    pipeline_stopped = True
            else:
                log("Quality Gate: все проверки пройдены.")
                results["quality_gate"] = {"status": "passed"}
                tracer.end_quality_gate(qg_span, exit_code, "passed")
            # Save checkpoint after QG
            if not dry_run:
                save_checkpoint(project, results, total_cost, model, parallel)
            continue

        # Agent stage
        agent_ids = [s for s in stage if isinstance(s, int)]
        if not agent_ids:
            continue

        # Skip agents completed in previous run (resume mode)
        remaining_ids = [aid for aid in agent_ids if aid not in skip_steps]
        if not remaining_ids:
            skipped_names = ", ".join(
                f"{aid} ({AGENT_REGISTRY[aid]['name']})" for aid in agent_ids
            )
            log(f"\n--- Стадия {stage_idx}: Agent {skipped_names} [ПРОПУСК — resume] ---")
            continue
        agent_ids = remaining_ids

        names = ", ".join(
            f"{aid} ({AGENT_REGISTRY[aid]['name']})" for aid in agent_ids
        )
        mode = "параллельно" if len(agent_ids) > 1 else "один"
        log("")
        log(f"--- Стадия {stage_idx}: Agent {names} [{mode}] ---")

        # Start Langfuse spans for each agent
        agent_spans = {}
        for aid in agent_ids:
            agent_spans[aid] = tracer.start_agent(aid, AGENT_REGISTRY[aid]["name"])

        # Check total pipeline budget before executing
        if total_cost >= pipeline_budget and not dry_run:
            log(f"КОНВЕЙЕР ОСТАНОВЛЕН: превышен бюджет ${total_cost:.2f} >= ${pipeline_budget:.0f}")
            pipeline_stopped = True
            break

        # Execute agents (use per-agent model and budget from registry).
        # Model override: --model opus forces opus for ALL agents.
        # Default (--model sonnet) uses per-agent models from AGENT_REGISTRY.
        # Budget override: --max-budget N overrides per-agent budgets.
        # Default (5.0) uses per-agent budget_usd from AGENT_REGISTRY.
        if len(agent_ids) == 1:
            aid = agent_ids[0]
            agent_model = model if model != "sonnet" else AGENT_REGISTRY[aid].get("model", model)
            agent_budget = max_budget_per_agent if max_budget_per_agent != 5.0 else AGENT_REGISTRY[aid].get("budget_usd", 5.0)
            # HIGH-X1: per-agent timeout from config (fallback to pipeline default)
            agent_timeout = AGENT_REGISTRY[aid].get("timeout_seconds", timeout_per_agent)
            agent_result = await run_single_agent(
                agent_id=aid,
                project=project,
                command="/auto",
                model=agent_model,
                dry_run=dry_run,
                max_budget=agent_budget,
                timeout=agent_timeout,
            )
            stage_results = {aid: agent_result}
        else:
            # Parallel execution with asyncio.gather
            tasks = [
                run_single_agent(
                    agent_id=aid,
                    project=project,
                    command="/auto",
                    model=model if model != "sonnet" else AGENT_REGISTRY[aid].get("model", model),
                    dry_run=dry_run,
                    max_budget=max_budget_per_agent if max_budget_per_agent != 5.0 else AGENT_REGISTRY[aid].get("budget_usd", 5.0),
                    # HIGH-X1: per-agent timeout from config
                    timeout=AGENT_REGISTRY[aid].get("timeout_seconds", timeout_per_agent),
                )
                for aid in agent_ids
            ]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            stage_results = {}
            for aid, res in zip(agent_ids, task_results):
                if isinstance(res, Exception):
                    log(f"Agent {aid}: исключение: {res}")
                    stage_results[aid] = AgentResult(
                        agent_id=aid, status="failed", error=str(res),
                    )
                else:
                    stage_results[aid] = res

        # Process stage results
        for aid, agent_result in stage_results.items():
            total_cost += agent_result.cost_usd
            results[aid] = {
                "status": agent_result.status,
                "duration": round(agent_result.duration_seconds, 1),
                "cost_usd": round(agent_result.cost_usd, 2),
                "num_turns": agent_result.num_turns,
                "session_id": agent_result.session_id,
                "summary": str(agent_result.summary_path) if agent_result.summary_path else None,
            }

            # End Langfuse span
            tracer.end_agent(agent_spans.get(aid), agent_result)

            if agent_result.status in ("failed", "timeout", "budget_exceeded"):
                log(
                    f"КОНВЕЙЕР ОСТАНОВЛЕН: Agent {aid} "
                    f"({AGENT_REGISTRY[aid]['name']}): {agent_result.status}."
                )
                if agent_result.error:
                    log(f"  {agent_result.error[:200]}")
                pipeline_stopped = True
            elif agent_result.status == "partial":
                log(f"  ВНИМАНИЕ: Agent {aid} завершился частично. Продолжаем.")
            if not agent_result.summary_path and agent_result.status != "dry_run":
                log(f"  ВНИМАНИЕ: _summary.json не найден для Agent {aid}.")

        # Save checkpoint after each stage (for --resume)
        if not dry_run:
            save_checkpoint(project, results, total_cost, model, parallel)

    # Summary
    total_duration = time.time() - total_start
    log("")
    budget_pct = (total_cost / pipeline_budget * 100) if pipeline_budget > 0 else 0
    log(f"{'=' * 60}")
    log(f"  КОНВЕЙЕР ЗАВЕРШЕН ({total_duration:.0f}с, ${total_cost:.2f} / ${pipeline_budget:.0f} [{budget_pct:.0f}%])")
    log(f"{'=' * 60}")

    status_icons = {
        "completed": "OK", "passed": "OK", "passed_after_retry": "OK",
        "partial": "!!", "dry_run": "--",
        "failed": "XX", "timeout": "TO", "budget_exceeded": "B$",
        "injection_detected": "!!", "warnings": "!!", "warnings_skipped": "!!",
    }
    for step_key, step_result in results.items():
        status = step_result.get("status", "?")
        icon = status_icons.get(status, "??")
        extra_parts = []
        if "duration" in step_result:
            extra_parts.append(f"{step_result['duration']}с")
        if step_result.get("cost_usd", 0) > 0:
            extra_parts.append(f"${step_result['cost_usd']}")
        if step_result.get("num_turns", 0) > 0:
            extra_parts.append(f"{step_result['num_turns']}t")
        extra = f" ({', '.join(extra_parts)})" if extra_parts else ""
        log(f"  [{icon}] {step_key}: {status}{extra}")

    # Finish Langfuse trace
    tracer.finish(total_cost, total_duration, results)

    # Save final pipeline state
    if not dry_run:
        state_file = save_checkpoint(project, results, total_cost, model, parallel)
        log(f"  Состояние: {state_file}")

    return results


def _detect_platform(project: str) -> str:
    """Detect project platform from PROJECT_CONTEXT.md.

    Returns normalized platform: 'go', '1c', or '' (unknown).
    """
    ctx_path = ROOT_DIR / "projects" / project / "PROJECT_CONTEXT.md"
    if not ctx_path.is_file():
        return ""
    try:
        text = ctx_path.read_text(encoding="utf-8").lower()
    except OSError:
        return ""
    if "1с" in text or "1c" in text:
        return "1c"
    if "go" in text or "golang" in text:
        return "go"
    return ""


def _inject_conditional(stages: list[list], project: str) -> list[list]:
    """Inject conditional agents (9, 10) into stages based on platform."""
    if not CONDITIONAL_STAGES:
        return stages
    platform = _detect_platform(project)
    if not platform:
        return stages
    for agent_id, cond in CONDITIONAL_STAGES.items():
        if cond.get("platform", "").lower() != platform:
            continue
        if agent_id not in AGENT_REGISTRY:
            continue
        after = cond.get("after")
        # Find the stage index containing the 'after' agent
        insert_idx = None
        for i, stage in enumerate(stages):
            if after in stage:
                insert_idx = i + 1
                break
        if insert_idx is not None:
            stages.insert(insert_idx, [agent_id])
        else:
            stages.append([agent_id])
    return stages


def _build_parallel_stages(agents_filter: list[int] | None, project: str = "") -> list[list]:
    """Build parallel stage list, applying agent filter and conditionals."""
    stages = []
    for stage in PARALLEL_STAGES:
        if agents_filter:
            filtered = [
                s for s in stage
                if s == "quality_gate" or s in agents_filter
            ]
            if "quality_gate" in stage and 7 not in agents_filter:
                filtered = [s for s in filtered if s != "quality_gate"]
            if filtered:
                stages.append(filtered)
        else:
            stages.append(list(stage))
    if project:
        stages = _inject_conditional(stages, project)
    return stages


def _build_sequential_stages(agents_filter: list[int] | None, project: str = "") -> list[list]:
    """Build sequential stage list (each step in its own stage)."""
    pipeline = list(PIPELINE_ORDER)
    if agents_filter:
        pipeline = [
            step for step in PIPELINE_ORDER
            if step == "quality_gate" or step in agents_filter
        ]
        if 7 not in agents_filter:
            pipeline = [s for s in pipeline if s != "quality_gate"]
    stages = [[step] for step in pipeline]
    if project:
        stages = _inject_conditional(stages, project)
    return stages


# --- CLI ---

async def async_main():
    parser = argparse.ArgumentParser(
        description="Pipeline runner for FM Review agents (Claude Code SDK + Langfuse)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --parallel
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --agents 1,2,4
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --resume
  %(prog)s --agent 1 --project PROJECT_SHPMNT_PROFIT --command /audit
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run
""",
    )
    parser.add_argument(
        "--project", default=os.environ.get("PROJECT"),
        help="Project name (or env PROJECT)",
    )
    parser.add_argument(
        "--agent", type=int, choices=range(11), metavar="0-10",
        help="Run a single agent (0-10)",
    )
    parser.add_argument(
        "--command", default="/auto",
        help="Agent command (default: /auto)",
    )
    parser.add_argument(
        "--pipeline", action="store_true",
        help="Run full pipeline (1->2->4->5->3->QG->7->8->6)",
    )
    parser.add_argument(
        "--agents", type=str, default=None,
        help="Agent filter, comma-separated (e.g.: 1,2,4)",
    )
    parser.add_argument(
        "--model", default="sonnet",
        help="Claude model (default: sonnet)",
    )
    parser.add_argument(
        "--max-budget", type=float, default=5.0,
        help="Max budget USD per agent (default: 5.0)",
    )
    parser.add_argument(
        "--timeout", type=int, default=600,
        help="Timeout per agent in seconds (default: 600)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show prompts without execution",
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="Run independent agents in parallel within pipeline",
    )
    parser.add_argument(
        "--skip-qg-warnings", action="store_true",
        help="Skip Quality Gate warnings (non-critical)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume pipeline from last checkpoint (.pipeline_state.json)",
    )
    args = parser.parse_args()

    if not args.project:
        print("ERROR: specify --project or set env PROJECT", file=sys.stderr)
        sys.exit(1)

    project_dir = ROOT_DIR / "projects" / args.project
    if not project_dir.is_dir():
        print(f"ERROR: project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Load .env if exists (for Langfuse keys)
    _load_dotenv()

    if args.pipeline:
        agents_filter = None
        if args.agents:
            agents_filter = [int(x.strip()) for x in args.agents.split(",")]

        results = await run_pipeline(
            project=args.project,
            agents_filter=agents_filter,
            model=args.model,
            dry_run=args.dry_run,
            max_budget_per_agent=args.max_budget,
            timeout_per_agent=args.timeout,
            skip_qg_warnings=args.skip_qg_warnings,
            parallel=args.parallel,
            resume=args.resume,
        )
        any_failed = any(
            r.get("status") == "failed" for r in results.values()
        )
        sys.exit(1 if any_failed else 0)

    elif args.agent is not None:
        # Prompt injection check for single agent
        injection_warnings = validate_pipeline_input(args.project, args.command)
        if injection_warnings:
            for w in injection_warnings:
                log(w)

        # Single agent with optional Langfuse trace
        tracer = PipelineTracer(args.project, args.model)
        tracer.start_pipeline()
        span = tracer.start_agent(args.agent, AGENT_REGISTRY[args.agent]["name"])

        result = await run_single_agent(
            agent_id=args.agent,
            project=args.project,
            command=args.command,
            model=args.model,
            dry_run=args.dry_run,
            max_budget=args.max_budget,
            timeout=args.timeout,
        )

        tracer.end_agent(span, result)
        tracer.finish(
            result.cost_usd,
            result.duration_seconds,
            {args.agent: {"status": result.status}},
        )

        out = {
            "agent": args.agent,
            "status": result.status,
            "duration": round(result.duration_seconds, 1),
            "cost_usd": round(result.cost_usd, 2),
            "num_turns": result.num_turns,
            "session_id": result.session_id,
            "summary": str(result.summary_path) if result.summary_path else None,
        }
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(0 if result.status != "failed" else 1)

    else:
        print("ERROR: specify --agent N or --pipeline", file=sys.stderr)
        sys.exit(1)


def _load_dotenv():
    """Load secrets: Infisical (Universal Auth) -> Infisical (user) -> .env file."""
    if shutil.which("infisical"):
        # Priority 1: Infisical Universal Auth (Machine Identity)
        mi_env = ROOT_DIR / "infra" / "infisical" / ".env.machine-identity"
        if mi_env.exists():
            mi_vars = {}
            for line in mi_env.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    mi_vars[k.strip()] = v.strip()

            client_id = mi_vars.get("INFISICAL_CLIENT_ID", "")
            client_secret = mi_vars.get("INFISICAL_CLIENT_SECRET", "")
            api_url = mi_vars.get("INFISICAL_API_URL", "")
            project_id = mi_vars.get("INFISICAL_PROJECT_ID", "")

            if client_id and client_secret:
                try:
                    # Get token via Universal Auth
                    env = dict(os.environ)
                    if api_url:
                        env["INFISICAL_API_URL"] = api_url

                    # Pass credentials via environment variables instead of process args
                    env["INFISICAL_CLIENT_ID"] = client_id
                    env["INFISICAL_CLIENT_SECRET"] = client_secret

                    login_result = subprocess.run(
                        ["infisical", "login", "--method=universal-auth", "--silent"],
                        capture_output=True, text=True, timeout=15, env=env,
                    )
                    # Extract token from output
                    token_match = re.search(r'(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', login_result.stdout)
                    if token_match:
                        token = token_match.group(1)
                        env["INFISICAL_TOKEN"] = token
                        export_cmd = ["infisical", "export", "--format=dotenv-export", "--env=dev"]
                        if project_id:
                            export_cmd.append(f"--projectId={project_id}")
                        result = subprocess.run(
                            export_cmd,
                            capture_output=True, text=True, timeout=10,
                            cwd=str(ROOT_DIR), env=env,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            _parse_dotenv_export(result.stdout)
                            return
                except (subprocess.TimeoutExpired, OSError):
                    pass

        # Priority 2: Infisical user auth (if logged in previously)
        try:
            result = subprocess.run(
                ["infisical", "export", "--format=dotenv-export"],
                capture_output=True, text=True, timeout=10,
                cwd=str(ROOT_DIR),
            )
            if result.returncode == 0 and result.stdout.strip():
                _parse_dotenv_export(result.stdout)
                return
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Priority 3: .env file
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def _parse_dotenv_export(output: str):
    """Parse 'export KEY=VALUE' lines into os.environ."""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            line = line[len("export "):]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
