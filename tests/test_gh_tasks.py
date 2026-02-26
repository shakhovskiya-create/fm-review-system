"""
Tests for gh-tasks.sh — GitHub Issues management script.

Validates enforcement rules:
- create: --body is required (DoD rule 28)
- done: --comment is required (DoD rule 27)
- done: cross-check changed files vs --comment (artifact validation)
- Correct error messages and exit codes
"""
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "gh-tasks.sh"


def run_gh_tasks(*args: str, check: bool = False, cwd: str = None) -> subprocess.CompletedProcess:
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
        cwd=cwd,
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


class TestArtifactCrossCheck:
    """Tests for _validate_artifacts: cross-check git diff vs --comment."""

    def _create_git_repo_with_diff(self, tmpdir: Path) -> Path:
        """Create a temp git repo with a known diff for testing."""
        repo = tmpdir / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
        # Initial commit
        (repo / "README.md").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        # Second commit with known files
        (repo / "scripts" / "gh-tasks.sh").parent.mkdir(parents=True, exist_ok=True)
        (repo / "scripts" / "gh-tasks.sh").write_text("changed")
        (repo / "agents" / "COMMON_RULES.md").parent.mkdir(parents=True, exist_ok=True)
        (repo / "agents" / "COMMON_RULES.md").write_text("changed")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "changes"], cwd=str(repo), capture_output=True)
        return repo

    def test_warns_on_missing_files(self, tmp_path):
        """Should warn when changed files are not mentioned in comment."""
        repo = self._create_git_repo_with_diff(tmp_path)
        # Comment mentions gh-tasks.sh but NOT COMMON_RULES.md
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nUpdated gh-tasks.sh\n## DoD\n- [x] Artifacts: gh-tasks.sh",
            cwd=str(repo),
        )
        # Should contain warning about COMMON_RULES.md (not mentioned)
        output = result.stdout + result.stderr
        assert "COMMON_RULES.md" in output or "WARNING" in output

    def test_no_warning_when_all_mentioned(self, tmp_path):
        """No warning when all changed files are mentioned in comment."""
        repo = self._create_git_repo_with_diff(tmp_path)
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] Artifacts: gh-tasks.sh, COMMON_RULES.md",
            cwd=str(repo),
        )
        output = result.stdout + result.stderr
        assert "WARNING" not in output or "НЕ упомянуты" not in output

    def test_works_with_full_paths_in_comment(self, tmp_path):
        """Full paths like agents/COMMON_RULES.md should also match."""
        repo = self._create_git_repo_with_diff(tmp_path)
        result = run_gh_tasks(
            "done", "999",
            "--comment", "Artifacts: scripts/gh-tasks.sh, agents/COMMON_RULES.md",
            cwd=str(repo),
        )
        output = result.stdout + result.stderr
        assert "НЕ упомянуты" not in output


class TestGhTasksDoneGitCheck:
    """Tests for pre-close git state checks (uncommitted changes, unpushed commits)."""

    @staticmethod
    def _create_clean_repo(tmpdir: Path) -> Path:
        """Create a temp git repo with initial commit and a fake remote (for @{u})."""
        repo = tmpdir / "repo"
        repo.mkdir()
        bare = tmpdir / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True)
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
        (repo / "README.md").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(repo), capture_output=True)
        # Fallback: if default branch is master
        subprocess.run(["git", "push", "-u", "origin", "master"], cwd=str(repo), capture_output=True)
        return repo

    def test_blocks_on_uncommitted_changes(self, tmp_path):
        """done should exit 1 when there are uncommitted tracked changes."""
        repo = self._create_clean_repo(tmp_path)
        # Modify a tracked file without committing
        (repo / "README.md").write_text("modified")
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] All good",
            cwd=str(repo),
        )
        assert result.returncode == 1
        assert "незакоммиченные" in result.stdout.lower() or "uncommitted" in result.stdout.lower()

    def test_blocks_on_unpushed_commits(self, tmp_path):
        """done should exit 1 when there are unpushed commits."""
        repo = self._create_clean_repo(tmp_path)
        # Make a new commit but don't push
        (repo / "README.md").write_text("new change")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "unpushed"], cwd=str(repo), capture_output=True)
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] All good\n- [x] Artifacts: README.md",
            cwd=str(repo),
        )
        assert result.returncode == 1
        assert "незапушенные" in result.stdout.lower() or "unpushed" in result.stdout.lower()

    def test_force_bypasses_uncommitted_check(self, tmp_path):
        """--force should bypass the uncommitted changes check."""
        repo = self._create_clean_repo(tmp_path)
        (repo / "README.md").write_text("modified")
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] All good",
            "--force",
            cwd=str(repo),
        )
        # Should NOT contain the git-check error (may fail later on gh calls, that's fine)
        assert "незакоммиченные" not in result.stdout.lower()

    def test_force_bypasses_unpushed_check(self, tmp_path):
        """--force should bypass the unpushed commits check."""
        repo = self._create_clean_repo(tmp_path)
        (repo / "README.md").write_text("new change")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "unpushed"], cwd=str(repo), capture_output=True)
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] All good\n- [x] Artifacts: README.md",
            "--force",
            cwd=str(repo),
        )
        assert "незапушенные" not in result.stdout.lower()

    def test_clean_repo_passes_git_check(self, tmp_path):
        """done on a clean repo (everything committed and pushed) should pass git checks."""
        repo = self._create_clean_repo(tmp_path)
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone\n## DoD\n- [x] All good\n- [x] Artifacts: README.md",
            cwd=str(repo),
        )
        # Should not contain git-check errors (may fail later on gh, but not on git checks)
        assert "незакоммиченные" not in result.stdout.lower()
        assert "незапушенные" not in result.stdout.lower()

    def test_error_suggests_force_flag(self, tmp_path):
        """Error message should suggest --force as a workaround."""
        repo = self._create_clean_repo(tmp_path)
        (repo / "README.md").write_text("modified")
        result = run_gh_tasks(
            "done", "999",
            "--comment", "## Результат\nDone",
            cwd=str(repo),
        )
        assert "--force" in result.stdout
