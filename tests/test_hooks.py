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
    "guard-agent-write-scope.sh",
    "block-secrets.sh",
    "guard-destructive-bash.sh",
    "guard-mcp-confluence-write.sh",
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


class TestSubagentContextIssueGate:
    """Tests for issue-gate blocking in subagent-context.sh (SubagentStart hook).

    Agents MUST have at least one issue with status:in-progress to start work.
    Exceptions: helper-architect (whitelist), --skip-issue-check in prompt.
    """

    def _make_gh_mock(self, tmp_path, script_body):
        """Create a mock 'gh' script that returns controlled data."""
        mock_dir = tmp_path / "mock_bin"
        mock_dir.mkdir(exist_ok=True)
        mock_gh = mock_dir / "gh"
        mock_gh.write_text(script_body)
        mock_gh.chmod(0o755)
        return str(mock_dir)

    def _setup_project_dir(self, tmp_path):
        """Create minimal project structure for the hook."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        return str(tmp_path)

    def test_blocks_when_no_in_progress_issues(self, tmp_path):
        """Agent with open issues but none in-progress should be BLOCKED (exit 2)."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[{"number":42,"title":"Test issue","labels":[{"name":"agent:1-architect"},{"name":"status:planned"}]}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 2
        assert "BLOCK" in result.stdout

    def test_passes_when_in_progress_issue_exists(self, tmp_path):
        """Agent with status:in-progress issue should pass (exit 0)."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[{"number":42,"title":"Audit FM","labels":[{"name":"agent:1-architect"},{"name":"status:in-progress"}]}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "#42" in result.stdout

    def test_blocks_when_no_issues_at_all(self, tmp_path):
        """Agent with zero issues should be BLOCKED (exit 2)."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-0-creator"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 2
        assert "BLOCK" in result.stdout
        assert "gh-tasks.sh create" in result.stdout

    def test_helper_architect_not_blocked(self, tmp_path):
        """helper-architect (orchestrator) should never be blocked, only warned."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "helper-architect"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "WARNING" in result.stdout

    def test_skip_issue_check_flag(self, tmp_path):
        """--skip-issue-check in prompt bypasses blocking for any agent."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[]'
        ;;
esac
''')
        stdin = json.dumps({
            "subagent_name": "agent-1-architect",
            "prompt": "Do something --skip-issue-check"
        })
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "WARNING" in result.stdout

    def test_graceful_degradation_gh_unavailable(self, tmp_path):
        """If gh CLI fails, hook should not block (exit 0)."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '#!/bin/bash\nexit 1\n')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "WARNING" in result.stdout

    def test_no_check_without_agent_name(self):
        """Without subagent_name, no issue check performed."""
        result = run_hook("subagent-context.sh", stdin_data="{}")
        assert result.returncode == 0

    def test_mixed_issues_only_in_progress_passes(self, tmp_path):
        """Mix of planned and in-progress: should pass because in-progress exists."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[{"number":10,"title":"Task A","labels":[{"name":"agent:5-tech-architect"},{"name":"status:planned"}]},{"number":11,"title":"Task B","labels":[{"name":"agent:5-tech-architect"},{"name":"status:in-progress"}]}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-5-tech-architect"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "#10" in result.stdout
        assert "#11" in result.stdout

    def test_block_message_instructs_start(self, tmp_path):
        """Block message should instruct to run gh-tasks.sh start."""
        project_dir = self._setup_project_dir(tmp_path)
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"issue list"*)
        echo '[{"number":55,"title":"Review code","labels":[{"name":"agent:9-se-go"},{"name":"status:planned"}]}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-9-se-go"})
        env = {
            "PATH": f"{mock_path}:{os.environ.get('PATH', '')}",
            "CLAUDE_PROJECT_DIR": project_dir,
        }
        result = run_hook("subagent-context.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 2
        assert "gh-tasks.sh start" in result.stdout


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


class TestValidateSummaryEnforcement:
    """Tests for GitHub Issues enforcement in validate-summary.sh."""

    def _make_gh_mock(self, tmp_path, script_body):
        """Create a mock 'gh' script that returns controlled data."""
        mock_dir = tmp_path / "mock_bin"
        mock_dir.mkdir(exist_ok=True)
        mock_gh = mock_dir / "gh"
        mock_gh.write_text(script_body)
        mock_gh.chmod(0o755)
        return str(mock_dir)

    def test_blocks_when_open_issues_exist(self, tmp_path):
        """Agent with open issues should be BLOCKED (exit 2)."""
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"--state all"*)
        echo '[{"number":42}]'
        ;;
    *"--state open"*)
        echo '[{"number":42,"title":"Test issue"}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {"PATH": f"{mock_path}:{os.environ.get('PATH', '')}"}
        result = run_hook("validate-summary.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 2
        assert "BLOCKED" in result.stdout
        assert "#42" in result.stdout

    def test_passes_when_no_open_issues(self, tmp_path):
        """Agent with all issues closed should pass (exit 0)."""
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"--state all"*)
        echo '[{"number":42}]'
        ;;
    *"--state open"*)
        echo '[]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {"PATH": f"{mock_path}:{os.environ.get('PATH', '')}"}
        result = run_hook("validate-summary.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0

    def test_warns_when_no_issues_at_all(self, tmp_path):
        """Agent with zero issues gets WARNING (not BLOCK)."""
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"--state all"*)
        echo '[]'
        ;;
    *"--state open"*)
        echo '[]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-2-simulator"})
        env = {"PATH": f"{mock_path}:{os.environ.get('PATH', '')}"}
        result = run_hook("validate-summary.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0  # WARNING, not BLOCK
        assert "WARNING" in result.stdout

    def test_graceful_when_gh_unavailable(self, tmp_path):
        """Without gh CLI, hook should pass gracefully."""
        # Mock gh that always fails (simulating unavailable gh)
        mock_path = self._make_gh_mock(tmp_path, '#!/bin/bash\nexit 1\n')
        stdin = json.dumps({"subagent_name": "agent-1-architect"})
        env = {"PATH": f"{mock_path}:{os.environ.get('PATH', '')}"}
        result = run_hook("validate-summary.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 0
        assert "WARNING" in result.stdout

    def test_no_enforcement_without_agent_name(self):
        """Without subagent_name in stdin, no enforcement."""
        result = run_hook("validate-summary.sh", stdin_data="{}")
        assert result.returncode == 0

    def test_blocks_multiple_open_issues(self, tmp_path):
        """Multiple open issues all listed in BLOCKED message."""
        mock_path = self._make_gh_mock(tmp_path, '''#!/bin/bash
case "$*" in
    *"repo view"*)
        echo '{"nameWithOwner":"test/repo"}'
        ;;
    *"--state all"*)
        echo '[{"number":10},{"number":20},{"number":30}]'
        ;;
    *"--state open"*)
        echo '[{"number":10,"title":"First task"},{"number":20,"title":"Second task"}]'
        ;;
esac
''')
        stdin = json.dumps({"subagent_name": "agent-4-qa-tester"})
        env = {"PATH": f"{mock_path}:{os.environ.get('PATH', '')}"}
        result = run_hook("validate-summary.sh", stdin_data=stdin, env_extra=env)
        assert result.returncode == 2
        assert "#10" in result.stdout
        assert "#20" in result.stdout
        assert "2 незакрытых" in result.stdout


class TestGuardAgentWriteScope:
    """Tests for guard-agent-write-scope.sh hook."""

    def test_allows_write_without_marker(self, tmp_path):
        """No marker file = orchestrator session, allow all."""
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "projects/PROJECT_X/AGENT_1_ARCHITECT/file.md")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0

    def test_allows_agent_writing_own_dir(self, tmp_path):
        """Agent 1 writing to AGENT_1_* should be allowed."""
        marker = tmp_path / ".claude" / ".current-subagent"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("agent-1-architect")
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "projects/PROJECT_X/AGENT_1_ARCHITECT/report.md")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0

    def test_blocks_agent_writing_other_dir(self, tmp_path):
        """Agent 2 writing to AGENT_1_* should be blocked."""
        marker = tmp_path / ".claude" / ".current-subagent"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("agent-2-simulator")
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "projects/PROJECT_X/AGENT_1_ARCHITECT/report.md")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr

    def test_allows_orchestrator_anywhere(self, tmp_path):
        """helper-architect can write to any agent directory."""
        marker = tmp_path / ".claude" / ".current-subagent"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("helper-architect")
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "projects/PROJECT_X/AGENT_1_ARCHITECT/report.md")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0

    def test_allows_non_project_writes(self, tmp_path):
        """Agent can write to non-project paths (scripts, etc.)."""
        marker = tmp_path / ".claude" / ".current-subagent"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("agent-1-architect")
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "scripts/some_script.py")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0

    def test_allows_project_context_writes(self, tmp_path):
        """Agent can write PROJECT_CONTEXT.md (not in AGENT_* subdir)."""
        marker = tmp_path / ".claude" / ".current-subagent"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("agent-1-architect")
        stdin = json.dumps({"tool_input": {"file_path": str(tmp_path / "projects/PROJECT_X/PROJECT_CONTEXT.md")}})
        result = run_hook("guard-agent-write-scope.sh", stdin_data=stdin, env_extra={
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        })
        assert result.returncode == 0
