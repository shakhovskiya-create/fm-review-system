#!/usr/bin/env python3
"""
Автономный запуск агента FM Review через Claude API.

Использование:
  export ANTHROPIC_API_KEY=sk-...
  export PROJECT=PROJECT_SHPMNT_PROFIT
  python3 scripts/run_agent.py --agent 1 --command /audit
  python3 scripts/run_agent.py --agent 7 --command /publish --project PROJECT_SHPMNT_PROFIT

Результат сохраняется в projects/PROJECT/AGENT_X_*/ с именем по дате и команде.
Для полного автономного пайплайна orchestrate.sh при AUTONOMOUS=1 вызывает этот скрипт вместо копирования промпта в буфер.
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


def get_agent_file(agent_id: int) -> Path:
    """Путь к .md файлу агента по номеру 0-8."""
    names = [
        "AGENT_0_CREATOR",
        "AGENT_1_ARCHITECT",
        "AGENT_2_ROLE_SIMULATOR",
        "AGENT_3_DEFENDER",
        "AGENT_4_QA_TESTER",
        "AGENT_5_TECH_ARCHITECT",
        "AGENT_6_PRESENTER",
        "AGENT_7_PUBLISHER",
        "AGENT_8_BPMN_DESIGNER",
    ]
    if not (0 <= agent_id <= 8):
        raise ValueError("agent must be 0-8")
    return ROOT_DIR / "agents" / f"{names[agent_id]}.md"


def get_agent_output_dir(project: str, agent_id: int) -> Path:
    """Папка для сохранения результата агента."""
    names = [
        "AGENT_0_CREATOR",
        "AGENT_1_ARCHITECT",
        "AGENT_2_ROLE_SIMULATOR",
        "AGENT_3_DEFENDER",
        "AGENT_4_QA_TESTER",
        "AGENT_5_TECH_ARCHITECT",
        "AGENT_6_PRESENTER",
        "AGENT_7_PUBLISHER",
        "AGENT_8_BPMN_DESIGNER",
    ]
    d = ROOT_DIR / "projects" / project / names[agent_id]
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_context(project: str, fm_path: str) -> str:
    """Собирает контекст: PROJECT_CONTEXT + список файлов предыдущих агентов."""
    lines = [f"Проект: {project}", f"ФМ: {fm_path or 'Confluence (PAGE_ID из проекта)'}"]
    project_dir = ROOT_DIR / "projects" / project
    context_md = project_dir / "PROJECT_CONTEXT.md"
    if context_md.exists():
        lines.append("")
        lines.append("PROJECT_CONTEXT.md:")
        lines.append(context_md.read_text(encoding="utf-8")[:8000])
    for agent_dir in sorted(project_dir.glob("AGENT_*")):
        if not agent_dir.is_dir():
            continue
        for f in agent_dir.glob("*.md"):
            lines.append("")
            lines.append(f"Файл предыдущего анализа: {f}")
    return "\n".join(lines)


def run_with_anthropic(agent_content: str, user_message: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Вызов Claude API. Требует pip install anthropic и ANTHROPIC_API_KEY."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: pip install anthropic", file=sys.stderr)
        sys.exit(1)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=agent_content,
        messages=[{"role": "user", "content": user_message}],
    )
    return msg.content[0].text if msg.content else ""


def main():
    parser = argparse.ArgumentParser(description="Автономный запуск агента (Claude API)")
    parser.add_argument("--project", default=os.environ.get("PROJECT"), help="Имя проекта (или env PROJECT)")
    parser.add_argument("--agent", type=int, required=True, choices=range(9), metavar="0-8", help="Номер агента 0-8")
    parser.add_argument("--command", default="/audit", help="Команда агента: /audit, /publish, /bpmn, ...")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Модель Claude")
    parser.add_argument("--dry-run", action="store_true", help="Только вывести промпт, не вызывать API")
    args = parser.parse_args()

    if not args.project:
        print("ERROR: --project или env PROJECT обязателен", file=sys.stderr)
        sys.exit(1)

    agent_file = get_agent_file(args.agent)
    if not agent_file.exists():
        print(f"ERROR: {agent_file} не найден", file=sys.stderr)
        sys.exit(1)

    agent_content = agent_file.read_text(encoding="utf-8")
    fm_path = os.environ.get("FM_PATH", "Confluence (PAGE_ID из проекта)")
    context = build_context(args.project, fm_path)
    user_message = f"{context}\n\n{args.command}"

    if args.dry_run:
        print("=== SYSTEM (agent) ===")
        print(agent_content[:2000], "...")
        print("\n=== USER (context + command) ===")
        print(user_message[:3000], "...")
        return

    print(f"Запуск агента {args.agent}: {agent_file.name}, команда: {args.command}", file=sys.stderr)
    response = run_with_anthropic(agent_content, user_message, model=args.model)

    out_dir = get_agent_output_dir(args.project, args.agent)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    cmd_short = args.command.replace("/", "").replace(" ", "-")[:20]
    out_file = out_dir / f"run_{cmd_short}_{stamp}.md"
    out_file.write_text(response, encoding="utf-8")
    print(f"Результат сохранен: {out_file}", file=sys.stderr)
    print(out_file)


if __name__ == "__main__":
    main()
