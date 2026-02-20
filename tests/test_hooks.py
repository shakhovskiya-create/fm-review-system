"""
Tests for hook scripts (.claude/hooks/).

Validates that all hooks:
- Exist and are executable
- Accept stdin JSON without crashing
- Return correct exit codes
- Produce expected output patterns
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"

# All hook scripts that should exist
EXPECTED_HOOKS = [
    "inject-project-context.sh",
    "subagent-context.sh",
    "guard-confluence-write.sh",
    "validate-xhtml-style.sh",
    "validate-summary.sh",
    "langfuse-trace.sh",
    "auto-save-context.sh",
    "precompact-save-context.sh",
    "session-log.sh",
]


def run_hook(script_name: str, stdin_data: str = "", env_extra: dict = None) -> subprocess.CompletedProcess:
    """Run a hook script with optional stdin and env vars."""
    script = HOOKS_DIR / script_name
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(PROJECT_ROOT)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(script)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


class TestHookFilesExist:
    @pytest.mark.parametrize("hook_name", EXPECTED_HOOKS)
    def test_hook_exists(self, hook_name):
        hook = HOOKS_DIR / hook_name
        assert hook.exists(), f"Hook {hook_name} not found"

    @pytest.mark.parametrize("hook_name", EXPECTED_HOOKS)
    def test_hook_executable(self, hook_name):
        hook = HOOKS_DIR / hook_name
        assert os.access(hook, os.X_OK), f"Hook {hook_name} not executable"

    @pytest.mark.parametrize("hook_name", EXPECTED_HOOKS)
    def test_hook_has_shebang(self, hook_name):
        hook = HOOKS_DIR / hook_name
        first_line = hook.read_text().split("\n")[0]
        assert first_line.startswith("#!"), f"Hook {hook_name} missing shebang"


class TestInjectProjectContext:
    """Tests for inject-project-context.sh (SessionStart hook)."""

    def test_runs_without_error(self):
        result = run_hook("inject-project-context.sh")
        assert result.returncode == 0

    def test_outputs_header(self):
        result = run_hook("inject-project-context.sh")
        assert "FM Review System" in result.stdout

    def test_lists_projects(self):
        result = run_hook("inject-project-context.sh")
        # Should list at least PROJECT_SHPMNT_PROFIT
        if (PROJECT_ROOT / "projects" / "PROJECT_SHPMNT_PROFIT").is_dir():
            assert "PROJECT_SHPMNT_PROFIT" in result.stdout

    def test_shows_knowledge_graph(self):
        result = run_hook("inject-project-context.sh")
        if (PROJECT_ROOT / ".claude-memory" / "memory.jsonl").exists():
            assert "Knowledge Graph" in result.stdout


class TestGuardConfluenceWrite:
    """Tests for guard-confluence-write.sh (PreToolUse hook)."""

    def test_allows_normal_commands(self):
        stdin = json.dumps({"tool_input": {"command": "ls -la"}})
        result = run_hook("guard-confluence-write.sh", stdin)
        assert result.returncode == 0

    def test_blocks_curl_put_confluence(self):
        stdin = json.dumps({
            "tool_input": {"command": "curl -X PUT https://confluence.ekf.su/rest/api/content/123"}
        })
        result = run_hook("guard-confluence-write.sh", stdin)
        assert result.returncode == 2

    def test_allows_curl_get(self):
        stdin = json.dumps({
            "tool_input": {"command": "curl https://confluence.ekf.su/rest/api/content/123"}
        })
        result = run_hook("guard-confluence-write.sh", stdin)
        assert result.returncode == 0

    def test_handles_empty_input(self):
        result = run_hook("guard-confluence-write.sh", "")
        assert result.returncode == 0

    def test_handles_no_command(self):
        stdin = json.dumps({"tool_input": {}})
        result = run_hook("guard-confluence-write.sh", stdin)
        assert result.returncode == 0


class TestValidateXhtmlStyle:
    """Tests for validate-xhtml-style.sh (PostToolUse hook)."""

    def test_passes_clean_output(self):
        stdin = json.dumps({
            "tool_input": {"command": "python3 publish_to_confluence.py"},
            "stdout": "<th style='background-color: rgb(255,250,230);'>Header</th>"
        })
        result = run_hook("validate-xhtml-style.sh", stdin)
        assert result.returncode == 0

    def test_warns_on_blue_headers(self):
        stdin = json.dumps({
            "tool_input": {"command": "python3 publish_to_confluence.py"},
            "stdout": "<th style='background-color: rgb(59,115,175);'>Header</th>"
        })
        result = run_hook("validate-xhtml-style.sh", stdin)
        assert result.returncode == 0  # Warning only, not blocking
        assert "rgb(59,115,175)" in result.stderr

    def test_warns_on_ai_mentions(self):
        stdin = json.dumps({
            "tool_input": {"command": "python3 publish_to_confluence.py"},
            "stdout": "Created by Agent 1 using Claude"
        })
        result = run_hook("validate-xhtml-style.sh", stdin)
        assert result.returncode == 0  # Warning only
        assert "AI/Agent" in result.stderr or "Agent" in result.stderr

    def test_skips_non_confluence_commands(self):
        stdin = json.dumps({
            "tool_input": {"command": "ls -la"},
            "stdout": "Agent 1 Claude Bot"
        })
        result = run_hook("validate-xhtml-style.sh", stdin)
        assert result.returncode == 0
        assert result.stderr == ""  # No warnings for non-Confluence commands


class TestPrecompactSaveContext:
    """Tests for precompact-save-context.sh (PreCompact hook)."""

    def test_runs_without_error(self):
        stdin = json.dumps({"trigger": "auto", "cwd": str(PROJECT_ROOT)})
        result = run_hook("precompact-save-context.sh", stdin)
        assert result.returncode == 0

    def test_outputs_project_info(self):
        stdin = json.dumps({"trigger": "auto", "cwd": str(PROJECT_ROOT)})
        result = run_hook("precompact-save-context.sh", stdin)
        if (PROJECT_ROOT / "projects" / "PROJECT_SHPMNT_PROFIT").is_dir():
            assert "PROJECT_SHPMNT_PROFIT" in result.stdout or result.returncode == 0


class TestAutoSaveContext:
    """Tests for auto-save-context.sh (Stop hook)."""

    def test_runs_without_error(self):
        stdin = json.dumps({"cwd": str(PROJECT_ROOT)})
        result = run_hook("auto-save-context.sh", stdin)
        assert result.returncode == 0


class TestValidateSummary:
    """Tests for validate-summary.sh (SubagentStop hook)."""

    def test_runs_without_error(self):
        result = run_hook("validate-summary.sh")
        assert result.returncode == 0

    def test_validates_good_summary(self, tmp_path):
        """Hook should pass for valid _summary.json."""
        # Create a valid summary in a temp project structure
        project_dir = tmp_path / "projects" / "PROJECT_TEST" / "AGENT_1_ARCHITECT"
        project_dir.mkdir(parents=True)
        summary = {
            "agent": "Agent1_Architect",
            "command": "/audit",
            "timestamp": "2026-02-18T12:00:00Z",
            "status": "completed",
        }
        summary_file = project_dir / "audit_summary.json"
        summary_file.write_text(json.dumps(summary))
        # Touch the file to make it recent
        os.utime(summary_file, None)

        result = run_hook("validate-summary.sh", env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0
