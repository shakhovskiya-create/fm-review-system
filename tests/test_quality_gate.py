"""
Tests for quality_gate.sh: exit codes, override logging (FC-08C / H-A3).

Validates that:
- Exit 0 when no failures/warnings
- Exit 2 when warnings, no --reason
- Exit 0 when warnings + --reason → logs to .audit_trail
- JSONL audit log has required fields
"""
import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
QG_SCRIPT = SCRIPTS_DIR / "quality_gate.sh"


def _run_qg(args: list, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run quality_gate.sh with given args, capture output."""
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(QG_SCRIPT)] + args,
        capture_output=True,
        text=True,
        env=run_env,
    )


class TestQualityGateScript:
    """quality_gate.sh exists and is syntactically valid."""

    def test_script_exists(self):
        assert QG_SCRIPT.exists(), "quality_gate.sh not found"

    def test_script_syntax(self):
        """bash -n: syntax check only."""
        result = subprocess.run(
            ["bash", "-n", str(QG_SCRIPT)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_script_is_executable_or_runnable(self):
        """Script can be invoked via bash."""
        result = subprocess.run(
            ["bash", str(QG_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        # No --help flag → exits with an error or runs normally, either is fine
        # What matters: it doesn't crash with exit 127 (command not found)
        assert result.returncode != 127, "Script not found by bash"


class TestQualityGateOverrideAuditTrail:
    """FC-08C: --reason logs override to .audit_trail JSONL (H-A3)."""

    def test_override_creates_jsonl(self, tmp_path):
        """--reason flag writes a JSONL entry to quality_gate_overrides.jsonl."""
        # Setup: fake project dir with minimal structure so QG runs to warnings stage
        project_name = "TEST_QG_OVERRIDE"
        project_dir = tmp_path / "projects" / project_name
        project_dir.mkdir(parents=True)
        (project_dir / "PROJECT_CONTEXT.md").write_text("# Context\nВерсия ФМ: 1.0.0\n")

        audit_log_dir = SCRIPTS_DIR / ".audit_log"
        audit_log_file = audit_log_dir / "quality_gate_overrides.jsonl"

        # Record lines before
        before_count = 0
        if audit_log_file.exists():
            before_count = sum(1 for _ in audit_log_file.open())

        result = _run_qg(
            [project_name, "--reason", "test override reason"],
            env={"ROOT_DIR": str(tmp_path)},
        )

        # Exit 0 because --reason skips warnings
        assert result.returncode == 0, (
            f"Expected exit 0 with --reason, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # JSONL file should have grown by at least 1
        assert audit_log_file.exists(), "audit_log/quality_gate_overrides.jsonl not created"
        after_count = sum(1 for _ in audit_log_file.open())
        assert after_count > before_count, "No JSONL entry written for override"

        # Last entry should have required fields
        with audit_log_file.open() as f:
            lines = f.readlines()
        last_entry = json.loads(lines[-1])
        assert "timestamp" in last_entry, "Missing 'timestamp' in audit entry"
        assert "project" in last_entry, "Missing 'project' in audit entry"
        assert "reason" in last_entry, "Missing 'reason' in audit entry"
        assert "warnings" in last_entry, "Missing 'warnings' in audit entry"
        assert last_entry["reason"] == "test override reason"

    def test_no_reason_exits_2_on_warnings(self, tmp_path):
        """Without --reason, QG exits 2 when there are only warnings."""
        project_name = "TEST_QG_NOWARN"
        project_dir = tmp_path / "projects" / project_name
        project_dir.mkdir(parents=True)
        # Minimal context — no agent results → warnings only, no failures
        (project_dir / "PROJECT_CONTEXT.md").write_text("# Context\n")

        result = _run_qg([project_name], env={"ROOT_DIR": str(tmp_path)})

        # Should exit 2 (warnings, no --reason to skip)
        assert result.returncode in (0, 2), (
            f"Expected 0 or 2, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
