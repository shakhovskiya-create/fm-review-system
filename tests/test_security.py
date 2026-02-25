"""
Tests for security: API key handling, credential management, secret hygiene.

Validates that:
- No hardcoded secrets in source files
- Token/credential env vars are properly handled
- .env is in .gitignore
- Scripts fail gracefully without credentials
"""
import os
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class TestNoHardcodedSecrets:
    """Scan source files for hardcoded secrets."""

    # Patterns that suggest hardcoded secrets
    SECRET_PATTERNS = [
        (r'(?:token|password|secret|key)\s*=\s*["\'][A-Za-z0-9+/=]{20,}["\']', "Possible hardcoded secret"),
        (r'Bearer\s+[A-Za-z0-9+/=]{20,}', "Possible hardcoded Bearer token"),
        (r'Basic\s+[A-Za-z0-9+/=]{20,}', "Possible hardcoded Basic auth"),
    ]

    def _get_source_files(self):
        """Get all Python and shell source files."""
        py_files = list(SCRIPTS_DIR.rglob("*.py"))
        sh_files = list((PROJECT_ROOT / ".claude" / "hooks").glob("*.sh"))
        return py_files + sh_files

    @pytest.mark.parametrize("pattern,desc", SECRET_PATTERNS)
    def test_no_secrets_in_scripts(self, pattern, desc):
        for source_file in self._get_source_files():
            content = source_file.read_text()
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert not matches, (
                f"{desc} found in {source_file.relative_to(PROJECT_ROOT)}: {matches[:3]}"
            )

    def test_no_secrets_in_agent_configs(self):
        """Agent .md files should not contain secrets."""
        agents_dir = PROJECT_ROOT / ".claude" / "agents"
        for agent_file in agents_dir.glob("agent-*.md"):
            content = agent_file.read_text()
            for pattern, desc in self.SECRET_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, f"{desc} in {agent_file.name}"


class TestEnvFileHandling:
    """Validate .env file security."""

    def test_env_in_gitignore(self):
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore not found"
        content = gitignore.read_text()
        assert ".env" in content, ".env not in .gitignore"

    def test_env_example_exists(self):
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example not found"

    def test_env_example_has_no_real_values(self):
        env_example = PROJECT_ROOT / ".env.example"
        if not env_example.exists():
            pytest.skip(".env.example not found")
        content = env_example.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip("'\"")
                # Value should be empty, a placeholder, or a comment
                assert len(value) < 50 or value.startswith("your_") or value.startswith("<"), (
                    f"Suspicious value in .env.example: {key}={value[:30]}..."
                )

    def test_env_not_tracked_by_git(self):
        """.env file must not be tracked by git (contains real tokens locally)."""
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0, ".env is tracked by git - remove it with git rm --cached .env"


class TestCredentialHandling:
    """Validate proper credential handling in scripts."""

    def test_confluence_utils_requires_token(self):
        """create_client_from_env raises ValueError without token."""
        import sys
        sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
        from fm_review.confluence_utils import create_client_from_env

        with patch_env({}):
            with pytest.raises(ValueError, match="CONFLUENCE_TOKEN"):
                create_client_from_env("12345")

    def test_confluence_utils_accepts_personal_token(self):
        """create_client_from_env accepts CONFLUENCE_PERSONAL_TOKEN as fallback."""
        import sys
        sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
        from fm_review.confluence_utils import create_client_from_env

        with patch_env({"CONFLUENCE_PERSONAL_TOKEN": "test-pat-token"}):
            client = create_client_from_env("12345")
            assert client.token == "test-pat-token"

    def test_confluence_utils_requires_page_id(self):
        """create_client_from_env raises ValueError without page_id."""
        import sys
        sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
        from fm_review.confluence_utils import create_client_from_env

        with patch_env({"CONFLUENCE_TOKEN": "test-token"}):
            with pytest.raises(ValueError, match="page_id"):
                create_client_from_env()

    def test_export_script_reads_token_from_env(self):
        """export_from_confluence.py reads CONFLUENCE_TOKEN from env."""
        source = (SCRIPTS_DIR / "export_from_confluence.py").read_text()
        assert 'os.environ.get("CONFLUENCE_TOKEN"' in source

    def test_publish_script_uses_confluence_utils(self):
        """publish_to_confluence.py uses confluence_utils for API access."""
        source = (SCRIPTS_DIR / "publish_to_confluence.py").read_text()
        assert "confluence_utils" in source or "ConfluenceClient" in source

    def test_hooks_dont_read_env_files(self):
        """Hook scripts should not read .env files directly."""
        hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
        for hook_file in hooks_dir.glob("*.sh"):
            content = hook_file.read_text()
            # Hooks should use env vars, not source .env files directly.
            # Match both 'source' and '.' (dot command); exclude comment lines.
            assert not re.search(r'^\s*(?:source|\.)\s+.*\.env', content, re.MULTILINE), (
                f"Hook {hook_file.name} sources .env file directly"
            )


class TestBlockSecretsHook:
    """Tests for .claude/hooks/block-secrets.sh patterns."""

    HOOK_PATH = PROJECT_ROOT / ".claude" / "hooks" / "block-secrets.sh"

    def test_hook_exists_and_executable(self):
        assert self.HOOK_PATH.exists()

    def test_hook_has_langfuse_patterns(self):
        content = self.HOOK_PATH.read_text()
        assert "sk-lf-" in content, "Missing Langfuse secret key pattern"
        assert "pk-lf-" in content, "Missing Langfuse public key pattern"

    def test_hook_has_telegram_pattern(self):
        content = self.HOOK_PATH.read_text()
        assert ":AA" in content, "Missing Telegram bot token pattern"

    def test_hook_has_private_key_pattern(self):
        content = self.HOOK_PATH.read_text()
        assert "PRIVATE KEY" in content

    def test_hook_blocks_on_secret(self):
        """Run the hook with a fake Anthropic key and verify it blocks."""
        import subprocess
        # Build a test key dynamically to avoid hook catching this test file
        test_key = "sk-" + "ant-" + "A" * 30
        payload = '{"tool_input":{"content":"' + test_key + '","file_path":"test.txt"}}'
        result = subprocess.run(
            ["bash", str(self.HOOK_PATH)],
            input=payload, capture_output=True, text=True
        )
        assert result.returncode == 2, "Hook should block (exit 2) on secret"

    def test_hook_allows_safe_text(self):
        """Run the hook with safe text and verify it passes."""
        import subprocess
        payload = '{"tool_input":{"content":"normal code here","file_path":"test.txt"}}'
        result = subprocess.run(
            ["bash", str(self.HOOK_PATH)],
            input=payload, capture_output=True, text=True
        )
        assert result.returncode == 0, "Hook should pass (exit 0) on safe text"


class TestGuardDestructiveBashHook:
    """Tests for .claude/hooks/guard-destructive-bash.sh — blocks dangerous commands."""

    HOOK_PATH = PROJECT_ROOT / ".claude" / "hooks" / "guard-destructive-bash.sh"

    def test_hook_exists_and_executable(self):
        assert self.HOOK_PATH.exists()
        assert os.access(self.HOOK_PATH, os.X_OK)

    def _run_hook(self, command: str) -> int:
        import subprocess
        payload = '{"tool_input":{"command":"' + command + '"}}'
        result = subprocess.run(
            ["bash", str(self.HOOK_PATH)],
            input=payload, capture_output=True, text=True
        )
        return result.returncode

    def test_blocks_rm_rf_root(self):
        assert self._run_hook("rm -rf /") == 2

    def test_blocks_rm_rf_home(self):
        assert self._run_hook("rm -rf /home") == 2

    def test_blocks_git_push_force_main(self):
        assert self._run_hook("git push --force origin main") == 2

    def test_blocks_git_push_f_master(self):
        assert self._run_hook("git push -f origin master") == 2

    def test_blocks_git_reset_hard(self):
        assert self._run_hook("git reset --hard HEAD~3") == 2

    def test_blocks_git_clean_f(self):
        assert self._run_hook("git clean -fd") == 2

    def test_allows_git_clean_dry_run(self):
        assert self._run_hook("git clean -n") == 0

    def test_blocks_git_checkout_dot(self):
        assert self._run_hook("git checkout .") == 2

    def test_blocks_git_restore_dot(self):
        assert self._run_hook("git restore .") == 2

    def test_blocks_git_branch_D_main(self):
        assert self._run_hook("git branch -D main") == 2

    def test_allows_safe_commands(self):
        assert self._run_hook("git status") == 0
        assert self._run_hook("git push origin feature-branch") == 0
        assert self._run_hook("rm -rf ./build") == 0
        assert self._run_hook("git diff HEAD") == 0

    def test_allows_git_push_force_feature(self):
        """Force push to non-main/master branch is allowed."""
        assert self._run_hook("git push --force origin feature/my-branch") == 0

    def test_allows_text_mentioning_destructive_commands(self):
        """Text in arguments that mentions destructive commands should not trigger."""
        # Simulates heredoc content with rm -rf / mentioned as documentation text
        cmd = 'echo "защита от rm -rf /, git push --force main, git reset --hard"'
        assert self._run_hook(cmd) == 0

    def test_allows_rm_rf_build_dir(self):
        """rm -rf on project subdirectories is allowed."""
        assert self._run_hook("rm -rf ./build") == 0
        assert self._run_hook("rm -rf dist/") == 0


class TestSSLSafety:
    """Ensure no global SSL context override in production code."""

    def test_no_global_ssl_override(self):
        """Production scripts must not set ssl._create_default_https_context globally."""
        for py_file in SCRIPTS_DIR.rglob("*.py"):
            content = py_file.read_text()
            code_lines = [
                line for line in content.split("\n")
                if "ssl._create_default_https_context" in line
                and not line.strip().startswith("#")
                and "=" in line
            ]
            assert not code_lines, (
                f"{py_file.name} has global SSL override: {code_lines[0].strip()}"
            )


class TestAuthHeaders:
    """Validate correct authentication header usage."""

    def test_scripts_use_bearer_not_basic(self):
        """All scripts should use Bearer token, not Basic auth.

        Exception: Langfuse API requires Basic auth (public_key:secret_key).
        """
        # Scripts that legitimately use Basic auth for specific APIs
        basic_auth_allowed = {"tg-report.py", "cost-report.py"}

        for py_file in SCRIPTS_DIR.rglob("*.py"):
            if py_file.name in basic_auth_allowed:
                continue
            content = py_file.read_text()
            if "Authorization" in content:
                assert "Bearer" in content, (
                    f"{py_file.name} uses Authorization but not Bearer"
                )
                # Basic auth should not be used (except in comments)
                code_lines = [
                    l for l in content.split("\n")
                    if "Basic" in l and not l.strip().startswith("#")
                ]
                assert not code_lines, (
                    f"{py_file.name} uses Basic auth: {code_lines[0].strip()}"
                )


class TestSSLHandling:
    """Validate SSL context usage."""

    def test_scripts_handle_ssl(self):
        """Scripts that make HTTPS calls should handle SSL.

        Exception: scripts using only default urllib SSL (public APIs)
        don't need explicit ssl import — default verification is correct.
        """
        # Scripts using default SSL (public HTTPS APIs, no custom context)
        default_ssl_ok = {"tg-report.py", "tg-bot.py"}

        for py_file in SCRIPTS_DIR.rglob("*.py"):
            if py_file.name in default_ssl_ok:
                continue
            content = py_file.read_text()
            if "urlopen" in content or "urllib.request" in content:
                assert "ssl" in content, (
                    f"{py_file.name} makes HTTP calls but doesn't import ssl"
                )


# Helper context manager for env patching
import contextlib


@contextlib.contextmanager
def patch_env(env_vars):
    """Temporarily replace all CONFLUENCE_* env vars."""
    old_env = {}
    keys_to_clear = [k for k in os.environ if k.startswith("CONFLUENCE_")]
    for k in keys_to_clear:
        old_env[k] = os.environ.pop(k)
    os.environ.update(env_vars)
    try:
        yield
    finally:
        for k in env_vars:
            os.environ.pop(k, None)
        os.environ.update(old_env)


class TestHardcodedUserIds:
    """Ensure no hardcoded user_id values in source (M-A8)."""

    FORBIDDEN_USER_IDS = ["shahovsky", "шаховский", "shakhovskiy"]

    def test_no_hardcoded_user_id_in_scripts(self):
        """run_agent.py and langfuse_tracer.py must not hardcode user_id."""
        files_to_check = [
            SCRIPTS_DIR / "run_agent.py",
            PROJECT_ROOT / "src" / "fm_review" / "langfuse_tracer.py",
        ]
        for filepath in files_to_check:
            if not filepath.exists():
                continue
            content = filepath.read_text()
            for forbidden in self.FORBIDDEN_USER_IDS:
                # Allow in comments, disallow in code
                code_lines = [
                    line for line in content.splitlines()
                    if forbidden.lower() in line.lower()
                    and not line.strip().startswith("#")
                    and "user_id" in line
                ]
                assert not code_lines, (
                    f"{filepath.name} has hardcoded user_id '{forbidden}': "
                    f"{code_lines[0].strip()}"
                )
