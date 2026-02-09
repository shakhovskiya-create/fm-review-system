#!/usr/bin/env python3
"""
Автономный запуск агентов FM Review через Claude Code CLI (claude -p).

Использование:
  # Полный конвейер:
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT

  # Выборочные агенты:
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --agents 1,2,4

  # Один агент:
  python3 scripts/run_agent.py --agent 1 --project PROJECT_SHPMNT_PROFIT

  # Пробный запуск (без выполнения):
  python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run

Требования:
  - Claude Code CLI (claude) установлен и авторизован
  - Проект существует в projects/PROJECT_NAME/

Результаты сохраняются агентами в projects/PROJECT/AGENT_X_*/ автоматически.
Для полного автономного пайплайна orchestrate.sh при AUTONOMOUS=1 вызывает этот скрипт.
"""
import os
import sys
import json
import time
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# --- Реестр агентов ---

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

# Порядок конвейера: Agent 1 -> 2 -> 4 -> 5 -> QualityGate -> 7 -> 8 -> 6
PIPELINE_ORDER = [1, 2, 4, 5, "quality_gate", 7, 8, 6]


@dataclass
class AgentResult:
    agent_id: int
    status: str  # completed | partial | failed | dry_run
    summary_path: Path | None = None
    duration_seconds: float = 0.0
    exit_code: int = 0
    cost_usd: float = 0.0
    error: str = ""


# --- Утилиты ---

def find_claude_cli() -> str:
    """Находит Claude Code CLI."""
    path = shutil.which("claude")
    if path:
        return path
    # Fallback для macOS
    for candidate in ["/opt/homebrew/bin/claude", "/usr/local/bin/claude"]:
        if os.path.isfile(candidate):
            return candidate
    print("ОШИБКА: Claude Code CLI (claude) не найден.", file=sys.stderr)
    print("Установите: https://docs.anthropic.com/en/docs/claude-code", file=sys.stderr)
    sys.exit(1)


def log(msg: str):
    """Лог с таймстемпом в stderr."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr)


def find_summary_json(project: str, agent_id: int) -> Path | None:
    """Ищет самый свежий _summary.json для агента."""
    config = AGENT_REGISTRY[agent_id]
    agent_dir = ROOT_DIR / "projects" / project / config["dir"]
    if not agent_dir.is_dir():
        return None
    summaries = sorted(agent_dir.glob("*_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return summaries[0] if summaries else None


def check_agent_status(summary_path: Path) -> str:
    """Читает статус из _summary.json."""
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        return data.get("status", "completed")
    except (json.JSONDecodeError, OSError):
        return "completed"


# --- Сборка промпта ---

def build_prompt(agent_id: int, project: str, command: str) -> str:
    """Собирает промпт для claude -p."""
    config = AGENT_REGISTRY[agent_id]
    agent_file = ROOT_DIR / "agents" / config["file"]
    project_dir = ROOT_DIR / "projects" / project

    parts = []

    # 1. Инструкция прочитать роль
    parts.append(f"Прочитай и используй роль из {agent_file}")
    parts.append("")

    # 2. Контекст проекта
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

    # 4. Результаты предыдущих агентов
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

    # 5. Инструкции автономного режима
    parts.append("")
    parts.append("ВАЖНО: Это АВТОНОМНЫЙ запуск конвейера.")
    parts.append("- НЕ задавай вопросов. Используй режим /auto.")
    parts.append("- Читай все нужные файлы через инструмент Read.")
    parts.append("- Сохраняй результаты в папку проекта.")
    parts.append(f"- После завершения ОБЯЗАТЕЛЬНО создай _summary.json в {project_dir / config['dir']}/")
    parts.append("- _summary.json должен содержать: agent, command, timestamp, fmVersion, project, status")
    parts.append("")

    # 6. Команда
    parts.append(command)

    return "\n".join(parts)


# --- Запуск агента ---

def run_single_agent(
    agent_id: int,
    project: str,
    command: str = "/auto",
    model: str = "sonnet",
    dry_run: bool = False,
    max_budget: float = 5.0,
    timeout: int = 600,
) -> AgentResult:
    """Запускает одного агента через claude -p."""
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

    claude_cmd = [
        find_claude_cli(),
        "-p", prompt,
        "--output-format", "json",
        "--permission-mode", "acceptEdits",
        "--model", model,
        "--max-budget-usd", str(max_budget),
        "--append-system-prompt",
        f"Ты Agent {agent_id} ({config['name']}) в автономном конвейере. "
        f"Проект: {project}. НЕ задавай вопросов. Выполни команду полностью и создай _summary.json.",
    ]

    start_time = time.time()

    try:
        result = subprocess.run(
            claude_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT_DIR),
        )
        duration = time.time() - start_time

        # Парсим JSON-вывод
        cost = 0.0
        is_error = result.returncode != 0
        try:
            output_data = json.loads(result.stdout)
            is_error = output_data.get("is_error", is_error)
            cost = output_data.get("total_cost_usd", 0.0)
        except (json.JSONDecodeError, TypeError):
            pass

        # Проверяем _summary.json
        summary_path = find_summary_json(project, agent_id)
        if summary_path:
            status = check_agent_status(summary_path)
        elif is_error:
            status = "failed"
        else:
            status = "completed"

        log(f"Agent {agent_id} ({config['name']}): {status.upper()} ({duration:.1f}с, ${cost:.2f})")

        if is_error and result.stderr:
            error_lines = result.stderr.strip().split("\n")[-3:]
            log(f"  Ошибка: {' | '.join(error_lines)}")

        return AgentResult(
            agent_id=agent_id,
            status=status,
            summary_path=summary_path,
            duration_seconds=duration,
            exit_code=result.returncode,
            cost_usd=cost,
            error=result.stderr[:500] if is_error else "",
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        log(f"Agent {agent_id} ({config['name']}): ТАЙМАУТ ({duration:.1f}с)")
        return AgentResult(
            agent_id=agent_id, status="failed",
            duration_seconds=duration, error="Timeout",
        )
    except Exception as e:
        log(f"Agent {agent_id} ({config['name']}): ОШИБКА: {e}")
        return AgentResult(
            agent_id=agent_id, status="failed", error=str(e),
        )


# --- Quality Gate ---

def run_quality_gate(project: str) -> tuple[int, str]:
    """Запускает quality_gate.sh. Возвращает (exit_code, output)."""
    qg_script = SCRIPT_DIR / "quality_gate.sh"
    if not qg_script.exists():
        return 1, f"quality_gate.sh не найден: {qg_script}"

    try:
        result = subprocess.run(
            ["bash", str(qg_script), project],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT_DIR),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Quality Gate: таймаут"
    except Exception as e:
        return 1, f"Quality Gate: ошибка: {e}"


def run_quality_gate_with_reason(project: str, reason: str) -> int:
    """Запускает quality_gate.sh с --reason для пропуска предупреждений."""
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


# --- Конвейер ---

def run_pipeline(
    project: str,
    agents_filter: list[int] | None = None,
    model: str = "sonnet",
    dry_run: bool = False,
    max_budget_per_agent: float = 5.0,
    timeout_per_agent: int = 600,
    skip_qg_warnings: bool = False,
) -> dict:
    """Запускает полный конвейер агентов."""
    results = {}

    # Фильтруем шаги
    pipeline = list(PIPELINE_ORDER)
    if agents_filter:
        pipeline = [
            step for step in PIPELINE_ORDER
            if step == "quality_gate" or step in agents_filter
        ]
        # Quality Gate только если Agent 7 в списке
        if 7 not in agents_filter:
            pipeline = [s for s in pipeline if s != "quality_gate"]

    total_start = time.time()

    log(f"{'=' * 60}")
    log(f"  АВТОНОМНЫЙ КОНВЕЙЕР: {project}")
    log(f"  Шаги: {pipeline}")
    log(f"  Модель: {model}")
    log(f"{'=' * 60}")

    total_cost = 0.0

    for step in pipeline:

        # Quality Gate
        if step == "quality_gate":
            log("")
            log("--- QUALITY GATE ---")
            if dry_run:
                log("  [DRY RUN] quality_gate.sh")
                results["quality_gate"] = {"status": "dry_run"}
                continue

            exit_code, output = run_quality_gate(project)
            for line in output.strip().split("\n")[-10:]:
                log(f"  {line}")

            if exit_code == 1:
                log("КОНВЕЙЕР ОСТАНОВЛЕН: критические ошибки Quality Gate.")
                results["quality_gate"] = {"status": "failed", "exit_code": 1}
                break
            elif exit_code == 2:
                if skip_qg_warnings:
                    log("Quality Gate: предупреждения пропущены (--skip-qg-warnings).")
                    run_quality_gate_with_reason(project, "Автопропуск в автономном конвейере")
                    results["quality_gate"] = {"status": "warnings_skipped"}
                else:
                    log("КОНВЕЙЕР ОСТАНОВЛЕН: предупреждения Quality Gate.")
                    log("  Используйте --skip-qg-warnings для продолжения.")
                    results["quality_gate"] = {"status": "warnings", "exit_code": 2}
                    break
            else:
                log("Quality Gate: все проверки пройдены.")
                results["quality_gate"] = {"status": "passed"}
            continue

        # Обычный агент
        agent_id = step
        config = AGENT_REGISTRY[agent_id]
        log("")
        log(f"--- Agent {agent_id}: {config['name']} ---")

        agent_result = run_single_agent(
            agent_id=agent_id,
            project=project,
            command="/auto",
            model=model,
            dry_run=dry_run,
            max_budget=max_budget_per_agent,
            timeout=timeout_per_agent,
        )

        total_cost += agent_result.cost_usd
        results[agent_id] = {
            "status": agent_result.status,
            "duration": round(agent_result.duration_seconds, 1),
            "cost_usd": round(agent_result.cost_usd, 2),
            "summary": str(agent_result.summary_path) if agent_result.summary_path else None,
        }

        # Прерываем при ошибке
        if agent_result.status == "failed":
            log(f"КОНВЕЙЕР ОСТАНОВЛЕН: Agent {agent_id} ({config['name']}) завершился с ошибкой.")
            if agent_result.error:
                log(f"  {agent_result.error[:200]}")
            break

        # Предупреждение при частичном выполнении
        if agent_result.status == "partial":
            log(f"  ВНИМАНИЕ: Agent {agent_id} завершился частично. Продолжаем.")

        # Предупреждение если нет _summary.json
        if not agent_result.summary_path and agent_result.status != "dry_run":
            log(f"  ВНИМАНИЕ: _summary.json не найден для Agent {agent_id}.")

    # Итоги
    total_duration = time.time() - total_start
    log("")
    log(f"{'=' * 60}")
    log(f"  КОНВЕЙЕР ЗАВЕРШЕН ({total_duration:.0f}с, ${total_cost:.2f})")
    log(f"{'=' * 60}")

    status_icons = {
        "completed": "OK", "passed": "OK", "partial": "!!", "dry_run": "--",
        "failed": "XX", "warnings": "!!", "warnings_skipped": "!!",
    }
    for step_key, step_result in results.items():
        status = step_result.get("status", "?")
        icon = status_icons.get(status, "??")
        extra = ""
        if "duration" in step_result:
            extra = f" ({step_result['duration']}с)"
        log(f"  [{icon}] {step_key}: {status}{extra}")

    # Сохраняем состояние конвейера
    if not dry_run:
        state_file = ROOT_DIR / "projects" / project / ".pipeline_state.json"
        state = {
            "project": project,
            "started_at": datetime.now().isoformat(),
            "duration_seconds": round(total_duration, 1),
            "total_cost_usd": round(total_cost, 2),
            "model": model,
            "results": results,
        }
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"  Состояние: {state_file}")

    return results


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Автономный запуск агентов FM Review через Claude Code CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Примеры:
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --agents 1,2,4
  %(prog)s --agent 1 --project PROJECT_SHPMNT_PROFIT --command /audit
  %(prog)s --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run
""",
    )
    parser.add_argument("--project", default=os.environ.get("PROJECT"),
                        help="Имя проекта (или env PROJECT)")
    parser.add_argument("--agent", type=int, choices=range(9), metavar="0-8",
                        help="Запустить одного агента (0-8)")
    parser.add_argument("--command", default="/auto",
                        help="Команда агента (по умолчанию: /auto)")
    parser.add_argument("--pipeline", action="store_true",
                        help="Запустить полный конвейер (1->2->4->5->QG->7->8->6)")
    parser.add_argument("--agents", type=str, default=None,
                        help="Фильтр агентов через запятую (например: 1,2,4)")
    parser.add_argument("--model", default="sonnet",
                        help="Модель Claude (по умолчанию: sonnet)")
    parser.add_argument("--max-budget", type=float, default=5.0,
                        help="Макс. бюджет USD на агента (по умолчанию: 5.0)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Таймаут на агента в секундах (по умолчанию: 600)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать промпты без выполнения")
    parser.add_argument("--skip-qg-warnings", action="store_true",
                        help="Пропустить предупреждения Quality Gate (не критические)")
    args = parser.parse_args()

    if not args.project:
        print("ОШИБКА: укажите --project или env PROJECT", file=sys.stderr)
        sys.exit(1)

    # Проверяем что проект существует
    project_dir = ROOT_DIR / "projects" / args.project
    if not project_dir.is_dir():
        print(f"ОШИБКА: папка проекта не найдена: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Проверяем claude CLI
    find_claude_cli()

    if args.pipeline:
        agents_filter = None
        if args.agents:
            agents_filter = [int(x.strip()) for x in args.agents.split(",")]
        results = run_pipeline(
            project=args.project,
            agents_filter=agents_filter,
            model=args.model,
            dry_run=args.dry_run,
            max_budget_per_agent=args.max_budget,
            timeout_per_agent=args.timeout,
            skip_qg_warnings=args.skip_qg_warnings,
        )
        any_failed = any(
            r.get("status") == "failed"
            for r in results.values()
        )
        sys.exit(1 if any_failed else 0)

    elif args.agent is not None:
        result = run_single_agent(
            agent_id=args.agent,
            project=args.project,
            command=args.command,
            model=args.model,
            dry_run=args.dry_run,
            max_budget=args.max_budget,
            timeout=args.timeout,
        )
        out = {
            "agent": args.agent,
            "status": result.status,
            "duration": round(result.duration_seconds, 1),
            "cost_usd": round(result.cost_usd, 2),
            "summary": str(result.summary_path) if result.summary_path else None,
        }
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(0 if result.status != "failed" else 1)

    else:
        print("ОШИБКА: укажите --agent N или --pipeline", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
