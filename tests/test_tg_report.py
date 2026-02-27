"""
Tests for scripts/tg-report.py — Telegram expense report generator.

Covers: load_secrets, langfuse_get, fetch_traces, aggregate, format_message, send_telegram.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

# tg-report.py has a hyphen — use importlib to load it
_spec = importlib.util.spec_from_file_location("tg_report", SCRIPTS_DIR / "tg-report.py")
tg_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tg_report)


# ── load_secrets ───────────────────────────────────────────


class TestLoadSecrets:
    def test_skips_when_vars_set(self):
        """load_secrets skips when env vars already set."""
        env = {"LANGFUSE_PUBLIC_KEY": "pk", "TELEGRAM_BOT_TOKEN": "tok"}
        with patch.dict(os.environ, env):
            with patch("subprocess.run") as mock_run:
                tg_report.load_secrets()
                mock_run.assert_not_called()

    def test_runs_load_secrets_sh(self):
        """load_secrets runs load-secrets.sh when vars missing."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("subprocess.run") as mock_run:
                tg_report.load_secrets()
                mock_run.assert_called_once()

    def test_handles_exception(self):
        """load_secrets handles exception gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("subprocess.run", side_effect=OSError("fail")):
                tg_report.load_secrets()  # Should not raise


# ── langfuse_get ───────────────────────────────────────────


class TestLangfuseGet:
    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
        "LANGFUSE_HOST": "https://langfuse.test.com",
    })
    def test_successful_get(self):
        """langfuse_get returns parsed JSON."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": [{"id": "1"}]}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = tg_report.langfuse_get("/api/public/traces")
            assert result["data"][0]["id"] == "1"

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_uses_default_host(self):
        """langfuse_get uses default host when not set."""
        os.environ.pop("LANGFUSE_HOST", None)
        os.environ.pop("LANGFUSE_BASE_URL", None)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tg_report.langfuse_get("/api/test")
            req = mock_open.call_args[0][0]
            assert "cloud.langfuse.com" in req.full_url

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
        "LANGFUSE_BASE_URL": "https://custom.langfuse.com",
    })
    def test_uses_base_url_fallback(self):
        """langfuse_get uses LANGFUSE_BASE_URL when HOST not set."""
        os.environ.pop("LANGFUSE_HOST", None)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tg_report.langfuse_get("/api/test")
            req = mock_open.call_args[0][0]
            assert "custom.langfuse.com" in req.full_url

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk",
        "LANGFUSE_SECRET_KEY": "sk",
        "LANGFUSE_HOST": "https://langfuse.test.com",
    })
    def test_error_returns_empty_data(self):
        """langfuse_get returns empty data on error."""
        with patch("urllib.request.urlopen", side_effect=RuntimeError("fail")):
            result = tg_report.langfuse_get("/api/fail")
            assert result == {"data": []}


# ── fetch_traces ───────────────────────────────────────────


class TestFetchTraces:
    def test_single_page(self):
        """fetch_traces returns traces from single page."""
        traces = [{"id": "t1"}, {"id": "t2"}]
        with patch.object(tg_report, "langfuse_get", return_value={"data": traces}):
            result = tg_report.fetch_traces("2026-02-26T00:00:00Z", "2026-02-27T00:00:00Z")
            assert len(result) == 2

    def test_pagination(self):
        """fetch_traces paginates when 100 traces per page."""
        page1 = [{"id": f"t{i}"} for i in range(100)]
        page2 = [{"id": "t100"}, {"id": "t101"}]
        call_count = 0

        def mock_get(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": page1}
            return {"data": page2}

        with patch.object(tg_report, "langfuse_get", side_effect=mock_get):
            result = tg_report.fetch_traces("2026-02-26T00:00:00Z", "2026-02-27T00:00:00Z")
            assert len(result) == 102

    def test_empty_response(self):
        """fetch_traces returns empty list when no traces."""
        with patch.object(tg_report, "langfuse_get", return_value={"data": []}):
            result = tg_report.fetch_traces("2026-02-26T00:00:00Z", "2026-02-27T00:00:00Z")
            assert result == []


# ── aggregate ──────────────────────────────────────────────


class TestAggregate:
    def test_basic_aggregation(self):
        """aggregate groups traces by agent."""
        traces = [
            {"name": "agent-1-Architect", "tags": ["agent:agent-1-Architect"],
             "metadata": {"cost_usd": 1.5, "input_tokens": 1000, "output_tokens": 500}},
            {"name": "agent-1-Architect", "tags": ["agent:agent-1-Architect"],
             "metadata": {"cost_usd": 2.0, "input_tokens": 2000, "output_tokens": 1000}},
            {"name": "interactive", "tags": [],
             "metadata": {"cost_usd": 0.5, "input_tokens": 500, "output_tokens": 200}},
        ]
        result = tg_report.aggregate(traces)
        assert result["agent-1-Architect"]["calls"] == 2
        assert result["agent-1-Architect"]["cost"] == 3.5
        assert result["interactive"]["calls"] == 1

    def test_agent_from_tag(self):
        """aggregate extracts agent from tags."""
        traces = [
            {"name": "unknown", "tags": ["agent:agent-5-TechArchitect"],
             "metadata": {"cost_usd": 1.0}},
        ]
        result = tg_report.aggregate(traces)
        assert "agent-5-TechArchitect" in result

    def test_agent_from_name_fallback(self):
        """aggregate uses name when no agent tag."""
        traces = [
            {"name": "agent-7-Publisher", "tags": [],
             "metadata": {"cost_usd": 0.5}},
        ]
        result = tg_report.aggregate(traces)
        assert "agent-7-Publisher" in result

    def test_no_metadata(self):
        """aggregate handles traces with no metadata."""
        traces = [
            {"name": "test", "tags": [], "metadata": None},
        ]
        result = tg_report.aggregate(traces)
        assert result["interactive"]["calls"] == 1
        assert result["interactive"]["cost"] == 0.0

    def test_empty_traces(self):
        """aggregate returns empty dict for empty input."""
        result = tg_report.aggregate([])
        assert result == {}


# ── format_message ─────────────────────────────────────────


class TestFormatMessage:
    def test_basic_format(self):
        """format_message produces readable output."""
        agents = {
            "agent-1-Architect": {"calls": 2, "cost": 3.5, "input_tokens": 3000, "output_tokens": 1500},
        }
        msg = tg_report.format_message(agents, "Вчера, 26.02.2026", budget=100, period_days=1)
        assert "FM Review System" in msg
        assert "$3.50" in msg
        assert "2 выз." in msg

    def test_budget_exceeded(self):
        """format_message shows ПРЕВЫШЕН when over budget."""
        agents = {
            "interactive": {"calls": 1, "cost": 150.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Месяц", budget=100, period_days=30)
        assert "ПРЕВЫШЕН" in msg

    def test_budget_warning(self):
        """format_message shows warning when 80-99% budget."""
        agents = {
            "interactive": {"calls": 1, "cost": 85.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Месяц", budget=100, period_days=30)
        assert "⚠️" in msg

    def test_budget_ok(self):
        """format_message shows OK when under 80% budget."""
        agents = {
            "interactive": {"calls": 1, "cost": 50.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Месяц", budget=100, period_days=30)
        assert "✅" in msg

    def test_no_budget(self):
        """format_message works without budget."""
        agents = {
            "interactive": {"calls": 1, "cost": 5.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Сегодня", budget=0, period_days=1)
        assert "FM Review System" in msg

    def test_daily_average(self):
        """format_message shows daily average for multi-day periods."""
        agents = {
            "interactive": {"calls": 7, "cost": 35.0, "input_tokens": 10000, "output_tokens": 5000},
        }
        msg = tg_report.format_message(agents, "7 дней", budget=100, period_days=7)
        assert "$5.0/день" in msg

    def test_tokens_display(self):
        """format_message shows token counts."""
        agents = {
            "interactive": {"calls": 1, "cost": 5.0, "input_tokens": 1_500_000, "output_tokens": 500_000},
        }
        msg = tg_report.format_message(agents, "Сегодня", budget=0, period_days=0)
        assert "1.5M вх." in msg
        assert "0.5M вых." in msg

    def test_known_agent_label(self):
        """format_message uses AGENT_LABELS for known agents."""
        agents = {
            "agent-0-Creator": {"calls": 1, "cost": 1.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Test", budget=0, period_days=0)
        assert "Создатель ФМ" in msg

    def test_unknown_agent_fallback(self):
        """format_message falls back for unknown agents."""
        agents = {
            "agent-99-Custom": {"calls": 1, "cost": 1.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Test", budget=0, period_days=0)
        assert "99-Custom" in msg

    def test_per_call_average(self):
        """format_message shows per-call average."""
        agents = {
            "agent-1-Architect": {"calls": 4, "cost": 8.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Test", budget=0, period_days=0)
        assert "~$2.0/вызов" in msg

    def test_zero_cost_no_average(self):
        """format_message omits per-call average when cost is zero."""
        agents = {
            "interactive": {"calls": 1, "cost": 0.0, "input_tokens": 0, "output_tokens": 0},
        }
        msg = tg_report.format_message(agents, "Test", budget=0, period_days=0)
        assert "/вызов" not in msg


# ── send_telegram ──────────────────────────────────────────


class TestSendTelegram:
    def test_successful_send(self):
        """send_telegram returns True on success."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert tg_report.send_telegram("Test", "token", "123") is True

    def test_failed_send(self):
        """send_telegram returns False on error."""
        with patch("urllib.request.urlopen", side_effect=RuntimeError("fail")):
            assert tg_report.send_telegram("Test", "token", "123") is False

    def test_api_returns_not_ok(self):
        """send_telegram returns False when API returns ok=False."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": False}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert tg_report.send_telegram("Test", "token", "123") is False


# ── main ───────────────────────────────────────────────────


class TestMain:
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_langfuse_key_exits(self):
        """main exits when LANGFUSE_PUBLIC_KEY not set."""
        with patch("sys.argv", ["tg-report.py", "--dry-run"]):
            with patch.object(tg_report, "load_secrets"):
                with pytest.raises(SystemExit):
                    tg_report.main()

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_missing_telegram_vars_exits_non_dryrun(self):
        """main exits when TG vars missing and not dry-run."""
        with patch("sys.argv", ["tg-report.py"]):
            with patch.object(tg_report, "load_secrets"):
                with pytest.raises(SystemExit):
                    tg_report.main()

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_dry_run_yesterday_default(self, capsys):
        """main runs dry-run with yesterday default."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 1.0, "input_tokens": 100, "output_tokens": 50}},
        ]
        with patch("sys.argv", ["tg-report.py", "--dry-run"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    tg_report.main()
        captured = capsys.readouterr()
        assert "FM Review System" in captured.out

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_dry_run_today(self, capsys):
        """main runs dry-run with --today."""
        traces = [
            {"name": "interactive", "tags": [], "metadata": {"cost_usd": 0.5}},
        ]
        with patch("sys.argv", ["tg-report.py", "--dry-run", "--today"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    tg_report.main()
        captured = capsys.readouterr()
        assert "Сегодня" in captured.out

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_dry_run_days(self, capsys):
        """main runs dry-run with --days 7."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 5.0}},
        ]
        with patch("sys.argv", ["tg-report.py", "--dry-run", "--days", "7"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    tg_report.main()
        captured = capsys.readouterr()
        assert "Последние 7 дн." in captured.out

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_dry_run_month(self, capsys):
        """main runs dry-run with --month."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 10.0}},
        ]
        with patch("sys.argv", ["tg-report.py", "--dry-run", "--month", "2026-02"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    tg_report.main()
        captured = capsys.readouterr()
        assert "Месяц: 2026-02" in captured.out

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_dry_run_month_december(self, capsys):
        """main handles December correctly (month 12)."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 1.0}},
        ]
        with patch("sys.argv", ["tg-report.py", "--dry-run", "--month", "2026-12"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    tg_report.main()
        captured = capsys.readouterr()
        assert "Месяц: 2026-12" in captured.out

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
    })
    def test_no_traces_dry_run_exits(self):
        """main exits 0 with no traces in dry-run mode."""
        with patch("sys.argv", ["tg-report.py", "--dry-run"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=[]):
                    with pytest.raises(SystemExit) as exc:
                        tg_report.main()
                    assert exc.value.code == 0

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
        "TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123",
    })
    def test_no_traces_sends_empty_message(self):
        """main sends empty report message when not dry-run and not today."""
        with patch("sys.argv", ["tg-report.py"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=[]):
                    with patch.object(tg_report, "send_telegram") as mock_send:
                        with pytest.raises(SystemExit) as exc:
                            tg_report.main()
                        assert exc.value.code == 0
                        mock_send.assert_called_once()
                        assert "расход $0" in mock_send.call_args[0][0]

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
        "TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123",
    })
    def test_send_success(self):
        """main sends report and exits cleanly on success."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 1.0}},
        ]
        with patch("sys.argv", ["tg-report.py"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    with patch.object(tg_report, "send_telegram", return_value=True):
                        tg_report.main()

    @patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk",
        "TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123",
    })
    def test_send_failure_exits_1(self):
        """main exits 1 when send fails."""
        traces = [
            {"name": "agent-1", "tags": [], "metadata": {"cost_usd": 1.0}},
        ]
        with patch("sys.argv", ["tg-report.py"]):
            with patch.object(tg_report, "load_secrets"):
                with patch.object(tg_report, "fetch_traces", return_value=traces):
                    with patch.object(tg_report, "send_telegram", return_value=False):
                        with pytest.raises(SystemExit) as exc:
                            tg_report.main()
                        assert exc.value.code == 1
