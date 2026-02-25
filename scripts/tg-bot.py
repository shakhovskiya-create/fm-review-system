#!/usr/bin/env python3
"""
Telegram-бот для отчётов по расходам.

Команды:
    /report         — за вчера
    /report 7       — за последние N дней
    /report today   — за сегодня
    /report 2026-02 — за месяц

Запуск:
    python3 scripts/tg-bot.py

Systemd:
    sudo systemctl start fm-tg-bot

Env vars (из Infisical/load-secrets.sh):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
    LANGFUSE_HOST
"""

import collections
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PYTHON = os.path.join(PROJECT_DIR, ".venv", "bin", "python3")
TG_REPORT = os.path.join(SCRIPT_DIR, "tg-report.py")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tg-bot")

HELP_TEXT = """Команды:

/report — расходы за вчера
/report 7 — за последние 7 дней
/report 30 — за последние 30 дней
/report today — за сегодня
/report 2026-02 — за февраль 2026
/help — эта справка"""


def tg_api(method: str, data: dict | None = None, timeout: int = 30) -> dict:
    """Вызов Telegram Bot API."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/{method}"

    if data:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        if "timed out" in str(e):
            return {"ok": True, "result": []}  # normal long-poll timeout
        log.error("Telegram API %s: %s", method, e)
        return {"ok": False}
    except Exception as e:
        log.error("Telegram API %s: %s", method, e)
        return {"ok": False}


def send_message(chat_id: int | str, text: str):
    """Отправить сообщение."""
    tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    })


def run_report(args: list[str]) -> str:
    """Запустить tg-report.py и вернуть вывод."""
    cmd = [PYTHON, TG_REPORT, "--dry-run"] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONPATH": os.path.join(PROJECT_DIR, "src")},
        )
        output = result.stdout.strip()
        if not output and result.returncode == 0:
            return "Нет данных за этот период"
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Нет трейсов" in stderr:
                return "Нет данных за этот период"
            return f"Ошибка: {stderr[:200]}"
        return output
    except subprocess.TimeoutExpired:
        return "Таймаут при получении данных"
    except Exception as e:
        return f"Ошибка: {e}"


# Rate limiter: max RATE_LIMIT_MAX requests per RATE_LIMIT_WINDOW seconds per chat
RATE_LIMIT_MAX = int(os.environ.get("TG_RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW = int(os.environ.get("TG_RATE_LIMIT_WINDOW", "3600"))
_rate_limits: dict[str, collections.deque] = {}


def _is_rate_limited(chat_id: str) -> bool:
    """Check if chat has exceeded rate limit. Returns True if limited."""
    now = time.time()
    if chat_id not in _rate_limits:
        _rate_limits[chat_id] = collections.deque()
    q = _rate_limits[chat_id]
    # Remove expired entries
    while q and q[0] < now - RATE_LIMIT_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT_MAX:
        log.warning("Rate limited chat_id=%s (%d/%d in %ds)", chat_id, len(q), RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)
        return True
    q.append(now)
    return False


def handle_message(msg: dict):
    """Обработать входящее сообщение."""
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    allowed_chat = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
    if str(chat_id) != allowed_chat:
        log.warning("Unauthorized chat_id: %s", chat_id)
        return

    if text == "/help" or text == "/start":
        send_message(chat_id, HELP_TEXT)
        return

    if not text.startswith("/report"):
        return

    if _is_rate_limited(str(chat_id)):
        send_message(chat_id, f"Лимит: {RATE_LIMIT_MAX} запросов в час. Попробуйте позже.")
        return

    # Парсинг аргумента после /report
    parts = text.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if not arg:
        # По умолчанию — вчера
        report = run_report(["--yesterday"])
    elif arg == "today" or arg == "сегодня":
        report = run_report(["--today"])
    elif arg == "yesterday" or arg == "вчера":
        report = run_report(["--yesterday"])
    elif "-" in arg and len(arg) == 7:
        # Формат YYYY-MM
        report = run_report(["--month", arg])
    elif arg.isdigit():
        report = run_report(["--days", arg])
    else:
        send_message(chat_id, f"Не понял: '{arg}'\n\n{HELP_TEXT}")
        return

    send_message(chat_id, report)


def poll_loop():
    """Long-polling цикл."""
    log.info("Бот запущен, жду команды...")
    offset = 0

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset

            result = tg_api("getUpdates", params, timeout=60)
            updates = result.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])

        except KeyboardInterrupt:
            log.info("Остановлен")
            break
        except Exception as e:
            log.error("Poll error: %s", e)
            time.sleep(5)


def main():
    for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
        if not os.environ.get(var):
            print(f"ERROR: {var} не задан", file=sys.stderr)
            sys.exit(1)

    poll_loop()


if __name__ == "__main__":
    main()
