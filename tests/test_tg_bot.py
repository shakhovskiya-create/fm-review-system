"""
Tests for scripts/tg-bot.py — Telegram bot for expense reports.

Covers: tg_api, send_message, run_report, _is_rate_limited, handle_message, main.
"""
import collections
import importlib.util
import json
import os
import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

# tg-bot.py has a hyphen — use importlib to load it
_spec = importlib.util.spec_from_file_location("tg_bot", SCRIPTS_DIR / "tg-bot.py")
tg_bot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tg_bot)


# ── tg_api ─────────────────────────────────────────────────


class TestTgApi:
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_get_request(self):
        """tg_api sends GET when no data."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "result": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = tg_bot.tg_api("getUpdates")
            assert result["ok"] is True
            req = mock_open.call_args[0][0]
            assert "bot" + "test-token" in req.full_url
            assert req.data is None

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_post_request_with_data(self):
        """tg_api sends POST with JSON when data provided."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = tg_bot.tg_api("sendMessage", {"chat_id": 123, "text": "hi"})
            assert result["ok"] is True
            req = mock_open.call_args[0][0]
            body = json.loads(req.data)
            assert body["chat_id"] == 123

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_timeout_returns_empty_result(self):
        """tg_api returns empty result on timeout."""
        err = urllib.error.URLError("timed out")
        with patch("urllib.request.urlopen", side_effect=err):
            result = tg_bot.tg_api("getUpdates")
            assert result["ok"] is True
            assert result["result"] == []

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_url_error_returns_not_ok(self):
        """tg_api returns ok=False on non-timeout URLError."""
        err = urllib.error.URLError("connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            result = tg_bot.tg_api("getUpdates")
            assert result["ok"] is False

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_generic_exception_returns_not_ok(self):
        """tg_api returns ok=False on unexpected exception."""
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            result = tg_bot.tg_api("sendMessage")
            assert result["ok"] is False


# ── send_message ───────────────────────────────────────────


class TestSendMessage:
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token"})
    def test_calls_tg_api(self):
        """send_message calls tg_api with sendMessage."""
        with patch.object(tg_bot, "tg_api") as mock_api:
            tg_bot.send_message(123, "Hello")
            mock_api.assert_called_once_with("sendMessage", {
                "chat_id": 123,
                "text": "Hello",
                "disable_web_page_preview": True,
            })


# ── run_report ─────────────────────────────────────────────


class TestRunReport:
    def test_successful_report(self):
        """run_report returns stdout on success."""
        mock_result = MagicMock()
        mock_result.stdout = "Report data\n"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            output = tg_bot.run_report(["--yesterday"])
            assert output == "Report data"

    def test_empty_output(self):
        """run_report returns default message on empty output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            output = tg_bot.run_report(["--yesterday"])
            assert "Нет данных" in output

    def test_error_with_no_traces(self):
        """run_report returns no-data message when stderr contains Нет трейсов."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 1
        mock_result.stderr = "Нет трейсов за этот период"

        with patch("subprocess.run", return_value=mock_result):
            output = tg_bot.run_report(["--yesterday"])
            assert "Нет данных" in output

    def test_error_returns_stderr(self):
        """run_report returns truncated stderr on error."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 1
        mock_result.stderr = "Some error happened"

        with patch("subprocess.run", return_value=mock_result):
            output = tg_bot.run_report(["--yesterday"])
            assert "Ошибка" in output
            assert "Some error" in output

    def test_timeout(self):
        """run_report returns timeout message."""
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=60)):
            output = tg_bot.run_report(["--yesterday"])
            assert "Таймаут" in output

    def test_exception(self):
        """run_report returns error message on exception."""
        with patch("subprocess.run", side_effect=OSError("fail")):
            output = tg_bot.run_report(["--yesterday"])
            assert "Ошибка" in output


# ── _is_rate_limited ───────────────────────────────────────


class TestRateLimit:
    def setup_method(self):
        """Clear rate limits between tests."""
        tg_bot._rate_limits.clear()

    def test_first_request_not_limited(self):
        """First request is not rate limited."""
        assert tg_bot._is_rate_limited("chat1") is False

    def test_under_limit_not_limited(self):
        """Requests under limit are not rate limited."""
        with patch.object(tg_bot, "RATE_LIMIT_MAX", 5):
            for _ in range(4):
                tg_bot._is_rate_limited("chat1")
            assert tg_bot._is_rate_limited("chat1") is False

    def test_at_limit_is_limited(self):
        """Request at limit is rate limited."""
        with patch.object(tg_bot, "RATE_LIMIT_MAX", 3):
            for _ in range(3):
                tg_bot._is_rate_limited("chat2")
            assert tg_bot._is_rate_limited("chat2") is True

    def test_expired_entries_removed(self):
        """Expired entries are cleaned up."""
        with patch.object(tg_bot, "RATE_LIMIT_MAX", 2), \
             patch.object(tg_bot, "RATE_LIMIT_WINDOW", 0):
            tg_bot._is_rate_limited("chat3")
            tg_bot._is_rate_limited("chat3")
            time.sleep(0.01)
            # After window expires, should not be limited
            assert tg_bot._is_rate_limited("chat3") is False


# ── handle_message ─────────────────────────────────────────


class TestHandleMessage:
    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_unauthorized_chat_ignored(self):
        """Messages from unauthorized chats are ignored."""
        msg = {"chat": {"id": 99999}, "text": "/report"}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            mock_send.assert_not_called()

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_help_command(self):
        """Help command sends help text."""
        msg = {"chat": {"id": 12345}, "text": "/help"}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            mock_send.assert_called_once()
            assert "Команды" in mock_send.call_args[0][1]

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_start_command(self):
        """Start command sends help text."""
        msg = {"chat": {"id": 12345}, "text": "/start"}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            mock_send.assert_called_once()

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_non_report_command_ignored(self):
        """Non-report commands are ignored."""
        msg = {"chat": {"id": 12345}, "text": "/unknown"}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            mock_send.assert_not_called()

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_default_yesterday(self):
        """Bare /report runs report for yesterday."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--yesterday"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_today(self):
        """/report today runs today report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report today"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--today"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_russian_today(self):
        """/report сегодня runs today report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report сегодня"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--today"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_yesterday(self):
        """/report yesterday runs yesterday report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report yesterday"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--yesterday"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_russian_yesterday(self):
        """/report вчера runs yesterday report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report вчера"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--yesterday"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_month(self):
        """/report 2026-02 runs month report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report 2026-02"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--month", "2026-02"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_days(self):
        """/report 7 runs N-day report."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report 7"}
        with patch.object(tg_bot, "run_report", return_value="Report") as mock_run, \
             patch.object(tg_bot, "send_message"):
            tg_bot.handle_message(msg)
            mock_run.assert_called_once_with(["--days", "7"])

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_report_bad_arg(self):
        """/report with bad arg sends help."""
        tg_bot._rate_limits.clear()
        msg = {"chat": {"id": 12345}, "text": "/report foobar"}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            text = mock_send.call_args[0][1]
            assert "Не понял" in text

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_rate_limited_response(self):
        """/report sends limit message when rate limited."""
        tg_bot._rate_limits.clear()
        with patch.object(tg_bot, "_is_rate_limited", return_value=True), \
             patch.object(tg_bot, "send_message") as mock_send:
            msg = {"chat": {"id": 12345}, "text": "/report"}
            tg_bot.handle_message(msg)
            text = mock_send.call_args[0][1]
            assert "Лимит" in text

    @patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "12345"})
    def test_message_without_text(self):
        """Message without text is handled."""
        msg = {"chat": {"id": 12345}}
        with patch.object(tg_bot, "send_message") as mock_send:
            tg_bot.handle_message(msg)
            mock_send.assert_not_called()


# ── main ───────────────────────────────────────────────────


class TestMain:
    def test_missing_env_var_exits(self):
        """main exits with error if required env vars missing."""
        env = {k: "" for k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                                 "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                tg_bot.main()

    def test_all_env_vars_starts_loop(self):
        """main starts poll loop when all vars set."""
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "TELEGRAM_CHAT_ID": "123",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
        }
        with patch.dict(os.environ, env):
            with patch.object(tg_bot, "poll_loop") as mock_loop:
                tg_bot.main()
                mock_loop.assert_called_once()
