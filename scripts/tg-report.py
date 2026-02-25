#!/usr/bin/env python3
"""
Telegram-отчёт по расходам — тянет данные из Langfuse, шлёт в Telegram.

Usage:
    ./scripts/tg-report.py                  # За вчера (по умолчанию)
    ./scripts/tg-report.py --today          # За сегодня (текущий день)
    ./scripts/tg-report.py --yesterday      # За вчера
    ./scripts/tg-report.py --days 7         # За последние 7 дней
    ./scripts/tg-report.py --month 2026-02  # За месяц
    ./scripts/tg-report.py --dry-run        # Только показать, не слать

Cron (MSK):
    0 9  * * * source scripts/load-secrets.sh && python3 scripts/tg-report.py --yesterday
    0 18 * * * source scripts/load-secrets.sh && python3 scripts/tg-report.py --today

Env vars:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
    LANGFUSE_HOST (default: https://cloud.langfuse.com)
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

MSK = timezone(timedelta(hours=3))

AGENT_LABELS = {
    "agent-0-Creator": "Создатель ФМ",
    "agent-1-Architect": "Аудитор",
    "agent-2-RoleSimulator": "Симулятор ролей",
    "agent-3-Defender": "Защитник ФМ",
    "agent-4-QATester": "QA тестер",
    "agent-5-TechArchitect": "Техн. архитектор",
    "agent-6-Presenter": "Презентации",
    "agent-7-Publisher": "Публикация",
    "agent-8-BPMNDesigner": "BPMN",
    "interactive": "Ручная работа",
}


def load_secrets():
    """Загрузить секреты через load-secrets.sh."""
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("TELEGRAM_BOT_TOKEN"):
        return
    try:
        subprocess.run(
            ["bash", "-c", f"source {SCRIPT_DIR}/load-secrets.sh 2>/dev/null"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def langfuse_get(path: str) -> dict:
    """GET-запрос к Langfuse API."""
    host = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
    url = f"{host}{path}"

    import base64
    auth = base64.b64encode(
        f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()

    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Langfuse API: {e}", file=sys.stderr)
        return {"data": []}


def fetch_traces(from_ts: str, to_ts: str) -> list[dict]:
    """Получить все трейсы за период (с пагинацией)."""
    traces = []
    page = 1
    while True:
        data = langfuse_get(
            f"/api/public/traces?page={page}&limit=100"
            f"&fromTimestamp={from_ts}&toTimestamp={to_ts}"
        )
        batch = data.get("data", [])
        traces.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return traces


def aggregate(traces: list[dict]) -> dict:
    """Агрегация трейсов по агентам."""
    agents = defaultdict(lambda: {"calls": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0})

    for t in traces:
        meta = t.get("metadata") or {}
        name = t.get("name", "unknown")
        tags = t.get("tags") or []

        agent = "interactive"
        for tag in tags:
            if tag.startswith("agent:"):
                agent = tag.replace("agent:", "")
                break
        if name.startswith("agent-"):
            agent = name

        cost = float(meta.get("cost_usd", 0))
        inp = int(meta.get("input_tokens", 0) or 0)
        out = int(meta.get("output_tokens", 0) or 0)

        agents[agent]["calls"] += 1
        agents[agent]["cost"] += cost
        agents[agent]["input_tokens"] += inp
        agents[agent]["output_tokens"] += out

    return dict(agents)


def format_message(agents: dict, period: str, budget: float, period_days: int) -> str:
    """Форматировать сообщение для Telegram."""
    lines = []
    lines.append("📊 FM Review System")
    lines.append(f"📅 {period}")
    lines.append("")

    total_cost = 0.0
    total_calls = 0
    total_input = 0
    total_output = 0

    sorted_agents = sorted(agents.items(), key=lambda x: x[1]["cost"], reverse=True)

    for agent, data in sorted_agents:
        cost = data["cost"]
        calls = data["calls"]
        inp = data["input_tokens"]
        out = data["output_tokens"]

        total_cost += cost
        total_calls += calls
        total_input += inp
        total_output += out

        label = AGENT_LABELS.get(agent, agent.replace("agent-", "Агент "))
        icon = "👤" if agent == "interactive" else "🤖"

        avg = f" (~${cost / calls:.1f}/вызов)" if calls > 0 and cost > 0 else ""

        lines.append(f"{icon} {label}: ${cost:.2f} ({calls} выз.){avg}")

    lines.append("")
    lines.append(f"💰 Итого: ${total_cost:.2f} за {total_calls} вызовов")

    if period_days > 0 and total_cost > 0:
        daily = total_cost / max(period_days, 1)
        lines.append(f"📈 Среднее: ${daily:.1f}/день")

    if total_input + total_output > 0:
        lines.append(f"📝 Токены: {total_input / 1_000_000:.1f}M вх. + {total_output / 1_000_000:.1f}M вых.")

    if budget > 0:
        pct = total_cost / budget * 100
        if pct >= 100:
            lines.append(f"🚨 Бюджет: ${total_cost:.0f}/${budget:.0f} ({pct:.0f}%) ПРЕВЫШЕН")
        elif pct >= 80:
            lines.append(f"⚠️ Бюджет: ${total_cost:.0f}/${budget:.0f} ({pct:.0f}%)")
        else:
            lines.append(f"✅ Бюджет: ${total_cost:.0f}/${budget:.0f} ({pct:.0f}%)")

    lines.append("")
    lines.append("ℹ️ Вызов = один запуск агента или ручной запрос Claude Code")

    return "\n".join(lines)


def send_telegram(text: str, bot_token: str, chat_id: str) -> bool:
    """Отправить сообщение через Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"Telegram: {e}", file=sys.stderr)
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Отчёт по расходам в Telegram")
    parser.add_argument("--days", type=int, help="Период в днях")
    parser.add_argument("--yesterday", action="store_true", help="За вчера (по умолчанию)")
    parser.add_argument("--today", action="store_true", help="За сегодня")
    parser.add_argument("--month", type=str, help="Месяц (YYYY-MM)")
    parser.add_argument("--dry-run", action="store_true", help="Показать, не отправлять")
    parser.add_argument("--budget", type=float, default=float(os.environ.get("FM_REVIEW_MONTHLY_BUDGET", "100")))
    args = parser.parse_args()

    load_secrets()

    for var in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
        if not os.environ.get(var):
            print(f"ERROR: {var} не задан", file=sys.stderr)
            sys.exit(1)

    if not args.dry_run:
        for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
            if not os.environ.get(var):
                print(f"ERROR: {var} не задан (--dry-run для превью)", file=sys.stderr)
                sys.exit(1)

    now = datetime.now(MSK)

    if args.month:
        year, month = map(int, args.month.split("-"))
        from_dt = datetime(year, month, 1, tzinfo=MSK)
        if month == 12:
            to_dt = datetime(year + 1, 1, 1, tzinfo=MSK) - timedelta(seconds=1)
        else:
            to_dt = datetime(year, month + 1, 1, tzinfo=MSK) - timedelta(seconds=1)
        period = f"Месяц: {args.month}"
        period_days = (to_dt - from_dt).days + 1
    elif args.today:
        from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = now
        period = f"Сегодня, {now.strftime('%d.%m.%Y')}"
        period_days = 1
    elif args.days:
        from_dt = now - timedelta(days=args.days)
        to_dt = now
        period = f"Последние {args.days} дн."
        period_days = args.days
    else:
        # По умолчанию — вчера
        yesterday = now - timedelta(days=1)
        from_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        period = f"Вчера, {yesterday.strftime('%d.%m.%Y')}"
        period_days = 1

    from_ts = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_ts = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Загрузка трейсов ({period})...", file=sys.stderr)
    traces = fetch_traces(from_ts, to_ts)
    print(f"Найдено: {len(traces)} трейсов", file=sys.stderr)

    if not traces:
        if not args.dry_run and not args.today:
            send_telegram(
                f"📊 FM Review System\n📅 {period}\n\n✨ Вызовов не было — расход $0",
                os.environ["TELEGRAM_BOT_TOKEN"],
                os.environ["TELEGRAM_CHAT_ID"],
            )
        print("Нет трейсов за этот период", file=sys.stderr)
        sys.exit(0)

    agents = aggregate(traces)
    message = format_message(agents, period, args.budget, period_days)

    if args.dry_run:
        print(message)
        return

    ok = send_telegram(message, os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"])
    if ok:
        print("Отправлено в Telegram", file=sys.stderr)
    else:
        print("Ошибка отправки в Telegram", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
