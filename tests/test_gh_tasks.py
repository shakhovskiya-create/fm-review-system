"""
Tests for gh-tasks.sh — GitHub Issues management script.

Validates enforcement rules:
- create: --body is required (DoD rule 28)
- done: --comment is required (DoD rule 27)
- Correct error messages and exit codes
"""
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "gh-tasks.sh"


def run_gh_tasks(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run gh-tasks.sh with given arguments, WITHOUT hitting GitHub API.

    We test argument validation only — no network calls.
    The script will fail on gh commands, but enforcement checks happen before that.
    """
    env = os.environ.copy()
    env["PATH"] = str(PROJECT_ROOT / "tests" / "stubs") + ":" + env.get("PATH", "")
    return subprocess.run(
        ["bash", str(SCRIPT)] + list(args),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


class TestGhTasksCreateEnforcement:
    """Tests for mandatory --body on create command."""

    def test_create_without_body_fails(self):
        """create without --body should fail with exit 1."""
        result = run_gh_tasks(
            "create",
            "--title", "Test issue",
            "--agent", "orchestrator",
            "--sprint", "99",
        )
        assert result.returncode == 1
        assert "--body required" in result.stdout

    def test_create_with_empty_body_fails(self):
        """create with --body '' should fail with exit 1."""
        result = run_gh_tasks(
            "create",
            "--title", "Test issue",
            "--agent", "orchestrator",
            "--sprint", "99",
            "--body", "",
        )
        assert result.returncode == 1
        assert "--body required" in result.stdout

    def test_create_error_mentions_template(self):
        """Error message should mention the expected template."""
        result = run_gh_tasks(
            "create",
            "--title", "Test issue",
            "--agent", "orchestrator",
            "--sprint", "99",
        )
        assert "Acceptance Criteria" in result.stdout

    def test_create_without_title_fails(self):
        """create without --title should still fail."""
        result = run_gh_tasks(
            "create",
            "--agent", "orchestrator",
            "--sprint", "99",
            "--body", "some body",
        )
        assert result.returncode == 1
        assert "--title required" in result.stdout

    def test_create_without_agent_fails(self):
        """create without --agent should still fail."""
        result = run_gh_tasks(
            "create",
            "--title", "Test",
            "--sprint", "99",
            "--body", "some body",
        )
        assert result.returncode == 1
        assert "--agent required" in result.stdout

    def test_create_without_sprint_fails(self):
        """create without --sprint should still fail."""
        result = run_gh_tasks(
            "create",
            "--title", "Test",
            "--agent", "orchestrator",
            "--body", "some body",
        )
        assert result.returncode == 1
        assert "--sprint required" in result.stdout


class TestGhTasksDoneEnforcement:
    """Tests for mandatory --comment on done command."""

    def test_done_without_comment_fails(self):
        """done without --comment should fail with exit 1."""
        result = run_gh_tasks("done", "999")
        assert result.returncode == 1
        assert "--comment required" in result.stdout

    def test_done_with_empty_comment_fails(self):
        """done with --comment '' should fail with exit 1."""
        result = run_gh_tasks("done", "999", "--comment", "")
        assert result.returncode == 1
        assert "--comment required" in result.stdout

    def test_done_error_mentions_dod(self):
        """Error message should mention DoD template."""
        result = run_gh_tasks("done", "999")
        assert "DoD" in result.stdout or "Tests pass" in result.stdout


class TestGhTasksUsage:
    """Tests for usage and help."""

    def test_no_args_shows_usage(self):
        """Running without args should show usage."""
        result = run_gh_tasks()
        assert result.returncode == 1
        assert "Usage:" in result.stdout

    def test_usage_shows_body_required(self):
        """Usage should indicate --body is required for create."""
        result = run_gh_tasks()
        assert "--body" in result.stdout

    def test_usage_shows_comment_required(self):
        """Usage should indicate --comment is required for done."""
        result = run_gh_tasks()
        assert "--comment" in result.stdout
        assert "REQUIRED" in result.stdout or "DoD" in result.stdout
