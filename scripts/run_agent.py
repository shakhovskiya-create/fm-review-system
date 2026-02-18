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
import asyncio
import json
import os
import subprocess
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field

from claude_code_sdk import (
    query,
    ClaudeCodeOptions,
    ResultMessage,
    AssistantMessage,
    TextBlock,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# --- Agent registry ---

AGENT_REGISTRY = {
    0: {"name": "Creator",       "file": "AGENT_0_CREATOR.md",        "dir": "AGENT_0_CREATOR"},
    1: {"name": "Architect",     "file": "AGENT_1_ARCHITECT.md",      "dir": "AGENT_1_ARCHITECT"},
    2: {"name": "RoleSimulator", "file": "AGENT_2_ROLE_SIMULATOR.md", "dir": "AGENT_2_ROLE_SIMULATOR"},
    3: {"name": "Defender",      "file": "AGENT_3_DEFENDER.md",       "dir": "AGENT_3_DEFENDER"},
    4: {"name": "QATester",      "file": "AGENT_4_QA_TESTER.md",     "dir": "AGENT_4_QA_TESTER"},
    5: {"name": "TechArchitect", "file": "AGENT_5_TECH_ARCHITECT.md", "dir": "AGENT_5_TECH_ARCHITECT"},
    6: {"name": "Presenter",     "file": "AGENT_6_PRESENTER.md",     "dir": "AGENT_6_PRESENTER"},
    7: {"name": "Publisher",     "file": "AGENT_7_PUBLISHER.md",     "dir": "AGENT_7_PUBLISHER"},
    8: {"name": "BPMNDesigner",  "file": "AGENT_8_BPMN_DESIGNER.md", "dir": "AGENT_8_BPMN_DESIGNER"},
}

# Pipeline order: Agent 1 -> 2 -> 4 -> 5 -> 3 -> QualityGate -> 7 -> 8 -> 6
PIPELINE_ORDER = [1, 2, 4, 5, 3, "quality_gate", 7, 8, 6]

# Parallel stages (for --parallel)
PARALLEL_STAGES = [
    [1],                    # Stage 1: Architect (base for all)
    [2, 4],                 # Stage 2: Simulator + QA (parallel)
    [5],                    # Stage 3: TechArchitect (reads 1+2+4)
    [3],                    # Stage 4: Defender (analyzes findings 1+2+4+5)
    ["quality_gate"],       # Stage 5: Quality Gate
    [7],                    # Stage 6: Publisher
    [8, 6],                 # Stage 7: BPMN + Presenter (parallel)
]


@dataclass
class AgentResult:
    agent_id: int
    status: str  # completed | partial | failed | dry_run
    summary_path: Path | None = None
    duration_seconds: float = 0.0
    exit_code: int = 0
    cost_usd: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    error: str = ""


# --- Langfuse Pipeline Tracer ---

class PipelineTracer:
    """Optional Langfuse tracing for pipeline runs.

    Creates a root trace for the pipeline with child spans for each agent.
    Disabled silently if LANGFUSE_PUBLIC_KEY is not set.
    """

    def __init__(self, project: str, model: str, parallel: bool = False):
        self.project = project
        self.model = model
        self.parallel = parallel
        self.enabled = False
        self.langfuse = None
        self.root = None
        self._init()

    def _init(self):
        if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
            return
        # Ensure LANGFUSE_HOST is set (SDK v3 uses HOST, not BASE_URL)
        if not os.environ.get("LANGFUSE_HOST") and os.environ.get("LANGFUSE_BASE_URL"):
            os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]
        try:
            from langfuse import get_client
            self.langfuse = get_client()
            self.enabled = True
        except Exception:
            pass

    def start_pipeline(self) -> None:
        """Create root trace for the pipeline run."""
        if not self.enabled:
            return
        mode = "parallel" if self.parallel else "sequential"
        self.root = self.langfuse.start_span(name=f"pipeline-{self.project}")
        self.root.update_trace(
            name=f"pipeline-{self.project}",
            user_id="shahovsky",
            metadata={
                "project": self.project,
                "model": self.model,
                "mode": mode,
            },
            tags=[f"project:{self.project}", f"model:{self.model}", "pipeline", mode],
        )

    def start_agent(self, agent_id: int, agent_name: str):
        """Create a child span for an agent run. Returns span or None."""
        if not self.enabled or not self.root:
            return None
        span = self.root.start_span(
            name=f"agent-{agent_id}-{agent_name}",
            metadata={"agent_id": agent_id, "agent_name": agent_name},
        )
        return span

    def end_agent(self, span, result: AgentResult) -> None:
        """End an agent span with result metadata."""
        if not span:
            return
        status_level = "ERROR" if result.status == "failed" else "DEFAULT"
        span.update(
            metadata={
                "status": result.status,
                "cost_usd": result.cost_usd,
                "duration_seconds": result.duration_seconds,
                "num_turns": result.num_turns,
                "session_id": result.session_id,
                "error": result.error or None,
            },
            level=status_level,
        )
        # Add generation for cost tracking
        if result.cost_usd > 0:
            gen = span.start_generation(
                name=f"agent-{result.agent_id}-llm",
                model=self.model,
                metadata={"total_cost_usd": result.cost_usd},
            )
            gen.end()
        span.end()

    def start_quality_gate(self):
        """Create a child span for Quality Gate."""
        if not self.enabled or not self.root:
            return None
        return self.root.start_span(
            name="quality-gate",
            metadata={"type": "quality_gate"},
        )

    def end_quality_gate(self, span, exit_code: int, status: str) -> None:
        """End Quality Gate span."""
        if not span:
            return
        level = "ERROR" if exit_code == 1 else "WARNING" if exit_code == 2 else "DEFAULT"
        span.update(
            metadata={"exit_code": exit_code, "status": status},
            level=level,
        )
        span.end()

    def finish(self, total_cost: float, total_duration: float, results: dict) -> None:
        """End root trace and flush."""
        if not self.enabled or not self.root:
            return
        completed = sum(1 for r in results.values() if r.get("status") == "completed")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")
        self.root.update(
            metadata={
                "total_cost_usd": total_cost,
                "total_duration_seconds": total_duration,
                "agents_completed": completed,
                "agents_failed": failed,
            },
        )
        self.root.end()
        try:
            self.langfuse.flush()
        except Exception:
            pass


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

    options = ClaudeCodeOptions(
        model=model,
        permission_mode="acceptEdits",
        max_turns=25,
        cwd=str(ROOT_DIR),
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
            status="failed",
            duration_seconds=duration,
            error="Timeout",
        )
    except Exception as e:
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
        error=result_msg.result[:500] if result_msg and is_error else "",
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
    except Exception as e:
        return 1, f"Quality Gate: error: {e}"


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
    except Exception:
        return 1


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
) -> dict:
    """Run the full agent pipeline with optional Langfuse tracing.

    When parallel=True, independent agents run concurrently
    (e.g., Agent 2 + Agent 4 in one stage).
    """
    results = {}
    total_start = time.time()
    total_cost = 0.0
    pipeline_stopped = False

    # Initialize Langfuse tracer (no-op if LANGFUSE_PUBLIC_KEY not set)
    tracer = PipelineTracer(project, model, parallel)
    if not dry_run:
        tracer.start_pipeline()
        if tracer.enabled:
            log("Langfuse: трейсинг активен")

    # Build stages
    if parallel:
        stages = _build_parallel_stages(agents_filter)
        mode_label = "ПАРАЛЛЕЛЬНЫЙ"
    else:
        stages = _build_sequential_stages(agents_filter)
        mode_label = "ПОСЛЕДОВАТЕЛЬНЫЙ"

    log(f"{'=' * 60}")
    log(f"  КОНВЕЙЕР ({mode_label}): {project}")
    log(f"  Стадии: {stages}")
    log(f"  Модель: {model}")
    log(f"{'=' * 60}")

    for stage_idx, stage in enumerate(stages, 1):
        if pipeline_stopped:
            break

        # Quality Gate
        if stage == ["quality_gate"]:
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

            if exit_code == 1:
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
            continue

        # Agent stage
        agent_ids = [s for s in stage if isinstance(s, int)]
        if not agent_ids:
            continue

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

        # Execute agents
        if len(agent_ids) == 1:
            agent_result = await run_single_agent(
                agent_id=agent_ids[0],
                project=project,
                command="/auto",
                model=model,
                dry_run=dry_run,
                max_budget=max_budget_per_agent,
                timeout=timeout_per_agent,
            )
            stage_results = {agent_ids[0]: agent_result}
        else:
            # Parallel execution with asyncio.gather
            tasks = [
                run_single_agent(
                    agent_id=aid,
                    project=project,
                    command="/auto",
                    model=model,
                    dry_run=dry_run,
                    max_budget=max_budget_per_agent,
                    timeout=timeout_per_agent,
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

            if agent_result.status == "failed":
                log(
                    f"КОНВЕЙЕР ОСТАНОВЛЕН: Agent {aid} "
                    f"({AGENT_REGISTRY[aid]['name']}) завершился с ошибкой."
                )
                if agent_result.error:
                    log(f"  {agent_result.error[:200]}")
                pipeline_stopped = True
            elif agent_result.status == "partial":
                log(f"  ВНИМАНИЕ: Agent {aid} завершился частично. Продолжаем.")
            if not agent_result.summary_path and agent_result.status != "dry_run":
                log(f"  ВНИМАНИЕ: _summary.json не найден для Agent {aid}.")

    # Summary
    total_duration = time.time() - total_start
    log("")
    log(f"{'=' * 60}")
    log(f"  КОНВЕЙЕР ЗАВЕРШЕН ({total_duration:.0f}с, ${total_cost:.2f})")
    log(f"{'=' * 60}")

    status_icons = {
        "completed": "OK", "passed": "OK", "partial": "!!",
        "dry_run": "--", "failed": "XX", "warnings": "!!",
        "warnings_skipped": "!!",
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

    # Save pipeline state
    if not dry_run:
        state_file = ROOT_DIR / "projects" / project / ".pipeline_state.json"
        state = {
            "project": project,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(total_duration, 1),
            "total_cost_usd": round(total_cost, 2),
            "model": model,
            "mode": "parallel" if parallel else "sequential",
            "langfuse_enabled": tracer.enabled,
            "results": results,
        }
        state_file.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log(f"  Состояние: {state_file}")

    return results


def _build_parallel_stages(agents_filter: list[int] | None) -> list[list]:
    """Build parallel stage list, applying agent filter."""
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
    return stages


def _build_sequential_stages(agents_filter: list[int] | None) -> list[list]:
    """Build sequential stage list (each step in its own stage)."""
    pipeline = list(PIPELINE_ORDER)
    if agents_filter:
        pipeline = [
            step for step in PIPELINE_ORDER
            if step == "quality_gate" or step in agents_filter
        ]
        if 7 not in agents_filter:
            pipeline = [s for s in pipeline if s != "quality_gate"]
    return [[step] for step in pipeline]


# --- CLI ---

async def async_main():
    parser = argparse.ArgumentParser(
        description="Pipeline runner for FM Review agents (Claude Code SDK + Langfuse)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --parallel
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --agents 1,2,4
  %(prog)s --agent 1 --project PROJECT_SHPMNT_PROFIT --command /audit
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run
""",
    )
    parser.add_argument(
        "--project", default=os.environ.get("PROJECT"),
        help="Project name (or env PROJECT)",
    )
    parser.add_argument(
        "--agent", type=int, choices=range(9), metavar="0-8",
        help="Run a single agent (0-8)",
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
        )
        any_failed = any(
            r.get("status") == "failed" for r in results.values()
        )
        sys.exit(1 if any_failed else 0)

    elif args.agent is not None:
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
    """Load .env file if it exists (simple parser, no dependency)."""
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


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
