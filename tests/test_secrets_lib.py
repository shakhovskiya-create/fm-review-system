"""
Tests for scripts/lib/secrets.sh (H-A5: DRY Infisical Universal Auth).

Validates that:
- File exists and has valid bash syntax
- _infisical_universal_auth function is defined
- No use of eval (security requirement)
- load-secrets.sh, mcp-confluence.sh, check-secrets.sh source lib/secrets.sh
"""
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"
SECRETS_LIB = LIB_DIR / "secrets.sh"


class TestSecretsLibExists:
    def test_lib_dir_exists(self):
        assert LIB_DIR.is_dir(), "scripts/lib/ directory not found"

    def test_secrets_lib_exists(self):
        assert SECRETS_LIB.exists(), "scripts/lib/secrets.sh not found"


class TestSecretsLibSyntax:
    def test_bash_syntax_valid(self):
        """bash -n: parse without executing."""
        result = subprocess.run(
            ["bash", "-n", str(SECRETS_LIB)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error in secrets.sh: {result.stderr}"

    def test_no_eval_usage(self):
        """eval is forbidden — arbitrary code execution risk."""
        content = SECRETS_LIB.read_text()
        code_lines = [
            line for line in content.splitlines()
            if "eval" in line and not line.strip().startswith("#")
        ]
        assert not code_lines, (
            f"secrets.sh uses eval (forbidden): {code_lines[0].strip()}"
        )

    def test_function_defined(self):
        """_infisical_universal_auth must be defined."""
        content = SECRETS_LIB.read_text()
        assert "_infisical_universal_auth" in content, (
            "Function _infisical_universal_auth not found in secrets.sh"
        )

    def test_function_returns_on_missing_cli(self):
        """Function returns 1 when infisical CLI is missing (graceful degradation)."""
        # Override PATH so infisical is not found
        result = subprocess.run(
            ["bash", "-c",
             f'source "{SECRETS_LIB}"; PATH=/nonexistent _infisical_universal_auth /tmp'],
            capture_output=True, text=True,
        )
        assert result.returncode == 1, (
            "Expected return 1 when infisical not in PATH, "
            f"got {result.returncode}"
        )

    def test_function_returns_on_missing_mi_file(self, tmp_path):
        """Function returns 1 when .env.machine-identity does not exist."""
        result = subprocess.run(
            ["bash", "-c",
             f'source "{SECRETS_LIB}"; _infisical_universal_auth "{tmp_path}"'],
            capture_output=True, text=True,
        )
        assert result.returncode == 1, (
            "Expected return 1 when machine identity file missing, "
            f"got {result.returncode}"
        )


class TestScriptsSourceSecretsLib:
    """All scripts that use Infisical must source lib/secrets.sh."""

    SCRIPTS_TO_CHECK = [
        "load-secrets.sh",
        "mcp-confluence.sh",
        "check-secrets.sh",
    ]

    def test_scripts_source_secrets_lib(self):
        for script_name in self.SCRIPTS_TO_CHECK:
            script_path = SCRIPTS_DIR / script_name
            if not script_path.exists():
                continue
            content = script_path.read_text()
            assert "lib/secrets.sh" in content, (
                f"{script_name} does not source lib/secrets.sh"
            )
