"""
Tests for scripts/generate_findings_registry.py — findings aggregator.

Covers: extract_findings_from_markdown, deduplicate, build_summary, main.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts.generate_findings_registry import (
    FINDING_PATTERN,
    SEVERITY_ORDER,
    UX_FINDING_PATTERN,
    build_summary,
    deduplicate,
    extract_findings_from_markdown,
)  # noqa: I001

# ── extract_findings_from_markdown ─────────────────────────


class TestExtractFindings:
    def test_extracts_critical_finding(self, tmp_path):
        """Extracts CRITICAL-001 with description."""
        md = tmp_path / "report.md"
        md.write_text("## Findings\n\nCRITICAL-001: Missing validation on price field\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        assert len(findings) == 1
        assert findings[0]["id"] == "CRITICAL-001"
        assert findings[0]["severity"] == "CRITICAL"
        assert findings[0]["source"] == "Agent1"
        assert "validation" in findings[0]["description"].lower()

    def test_extracts_multiple_severities(self, tmp_path):
        """Extracts findings with different severities."""
        md = tmp_path / "report.md"
        md.write_text(
            "HIGH-001: First issue\n"
            "MEDIUM-002: Second issue\n"
            "LOW-003: Minor concern\n"
        )
        findings = extract_findings_from_markdown(md, "Agent2")
        assert len(findings) == 3
        severities = [f["severity"] for f in findings]
        assert "HIGH" in severities
        assert "MEDIUM" in severities
        assert "LOW" in severities

    def test_extracts_bracketed_findings(self, tmp_path):
        """Extracts findings in [SEVERITY-NNN] format."""
        md = tmp_path / "report.md"
        md.write_text("[HIGH-005]: Bracket style finding\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        assert len(findings) == 1
        assert findings[0]["id"] == "HIGH-005"

    def test_extracts_ux_findings(self, tmp_path):
        """Extracts UX-CRITICAL-001 style findings."""
        md = tmp_path / "report.md"
        md.write_text("UX-CRITICAL-001: Button too small for mobile\n")
        findings = extract_findings_from_markdown(md, "Agent2")
        ux = [f for f in findings if f["category"] == "UX"]
        assert len(ux) == 1
        assert ux[0]["id"] == "UX-CRITICAL-001"
        assert ux[0]["severity"] == "CRITICAL"

    def test_short_description_fallback(self, tmp_path):
        """Uses fallback description when context too short."""
        md = tmp_path / "report.md"
        md.write_text("HIGH-010: ab\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        assert len(findings) >= 1
        assert "Finding" in findings[0]["description"] or len(findings[0]["description"]) >= 10

    def test_missing_file(self, tmp_path):
        """Returns empty list for missing file."""
        md = tmp_path / "nonexistent.md"
        findings = extract_findings_from_markdown(md, "Agent1")
        assert findings == []

    def test_description_max_length(self, tmp_path):
        """Description is truncated to 200 chars."""
        long_desc = "X" * 300
        md = tmp_path / "report.md"
        md.write_text(f"CRITICAL-099: {long_desc}\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        assert len(findings[0]["description"]) <= 200

    def test_default_category_logic(self, tmp_path):
        """Non-UX findings default to LOGIC category."""
        md = tmp_path / "report.md"
        md.write_text("HIGH-001: Some business logic error\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        assert findings[0]["category"] == "LOGIC"

    def test_finding_status_open(self, tmp_path):
        """All extracted findings have Open status."""
        md = tmp_path / "report.md"
        md.write_text("CRITICAL-001: Test\nHIGH-002: Test2\n")
        findings = extract_findings_from_markdown(md, "Agent1")
        for f in findings:
            assert f["status"] == "Open"


# ── deduplicate ────────────────────────────────────────────


class TestDeduplicate:
    def test_removes_duplicates(self):
        """Keeps only first occurrence of each ID."""
        findings = [
            {"id": "HIGH-001", "source": "Agent1", "severity": "HIGH"},
            {"id": "HIGH-001", "source": "Agent2", "severity": "HIGH"},
            {"id": "HIGH-002", "source": "Agent1", "severity": "HIGH"},
        ]
        result = deduplicate(findings)
        assert len(result) == 2
        assert result[0]["source"] == "Agent1"

    def test_empty_list(self):
        """Returns empty list for empty input."""
        assert deduplicate([]) == []

    def test_no_duplicates(self):
        """Returns all findings when no duplicates."""
        findings = [
            {"id": "HIGH-001"},
            {"id": "HIGH-002"},
            {"id": "HIGH-003"},
        ]
        assert len(deduplicate(findings)) == 3


# ── build_summary ──────────────────────────────────────────


class TestBuildSummary:
    def test_severity_counts(self):
        """Counts findings by severity."""
        findings = [
            {"severity": "CRITICAL", "source": "A", "status": "Open"},
            {"severity": "CRITICAL", "source": "A", "status": "Open"},
            {"severity": "HIGH", "source": "B", "status": "Open"},
            {"severity": "LOW", "source": "A", "status": "Closed"},
        ]
        summary = build_summary(findings)
        assert summary["total"] == 4
        assert summary["bySeverity"]["critical"] == 2
        assert summary["bySeverity"]["high"] == 1
        assert summary["bySeverity"]["low"] == 1
        assert summary["bySeverity"]["medium"] == 0

    def test_source_counts(self):
        """Counts findings by source."""
        findings = [
            {"severity": "HIGH", "source": "Agent1", "status": "Open"},
            {"severity": "HIGH", "source": "Agent1", "status": "Open"},
            {"severity": "HIGH", "source": "Agent2", "status": "Open"},
        ]
        summary = build_summary(findings)
        assert summary["bySource"]["Agent1"] == 2
        assert summary["bySource"]["Agent2"] == 1

    def test_status_counts(self):
        """Counts findings by status."""
        findings = [
            {"severity": "HIGH", "source": "A", "status": "Open"},
            {"severity": "HIGH", "source": "A", "status": "Closed"},
            {"severity": "HIGH", "source": "A", "status": "Open"},
        ]
        summary = build_summary(findings)
        assert summary["byStatus"]["Open"] == 2
        assert summary["byStatus"]["Closed"] == 1

    def test_empty_findings(self):
        """Empty findings produce zero counts."""
        summary = build_summary([])
        assert summary["total"] == 0


# ── main ───────────────────────────────────────────────────


class TestMain:
    def test_no_args_exits(self):
        """main exits with error when no project given."""
        with patch("sys.argv", ["script"]):
            with pytest.raises(SystemExit):
                from scripts.generate_findings_registry import main
                main()

    def test_missing_project_exits(self, tmp_path):
        """main exits when project directory doesn't exist."""
        with patch("sys.argv", ["script", "NONEXISTENT"]):
            with patch("scripts.generate_findings_registry.ROOT_DIR", tmp_path):
                with pytest.raises(SystemExit):
                    from scripts.generate_findings_registry import main
                    main()

    def test_successful_generation(self, tmp_path):
        """main generates FINDINGS_REGISTRY.json."""
        project_dir = tmp_path / "projects" / "TEST_PROJECT"
        agent_dir = project_dir / "AGENT_1_ARCHITECT"
        agent_dir.mkdir(parents=True)

        (agent_dir / "audit_report.md").write_text(
            "# Audit\n\nCRITICAL-001: Major issue found\nHIGH-002: Minor issue\n"
        )

        ctx = project_dir / "PROJECT_CONTEXT.md"
        ctx.write_text("Версия ФМ: 1.0.5\n")

        with patch("sys.argv", ["script", "TEST_PROJECT"]):
            with patch("scripts.generate_findings_registry.ROOT_DIR", tmp_path):
                from scripts.generate_findings_registry import main
                main()

        output = project_dir / "FINDINGS_REGISTRY.json"
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["project"] == "TEST_PROJECT"
        assert data["fmVersion"] == "1.0.5"
        assert data["summary"]["total"] >= 2

    def test_no_context_default_version(self, tmp_path):
        """main uses 0.0.0 when no PROJECT_CONTEXT.md."""
        project_dir = tmp_path / "projects" / "TEST_PROJECT"
        project_dir.mkdir(parents=True)

        with patch("sys.argv", ["script", "TEST_PROJECT"]):
            with patch("scripts.generate_findings_registry.ROOT_DIR", tmp_path):
                from scripts.generate_findings_registry import main
                main()

        output = project_dir / "FINDINGS_REGISTRY.json"
        data = json.loads(output.read_text())
        assert data["fmVersion"] == "0.0.0"

    def test_scans_subdirectories(self, tmp_path):
        """main scans subdirectories of agent dirs."""
        project_dir = tmp_path / "projects" / "TEST_PROJECT"
        sub_dir = project_dir / "AGENT_2_ROLE_SIMULATOR" / "subdir"
        sub_dir.mkdir(parents=True)

        (sub_dir / "deep_report.md").write_text("LOW-001: Deep finding\n")

        with patch("sys.argv", ["script", "TEST_PROJECT"]):
            with patch("scripts.generate_findings_registry.ROOT_DIR", tmp_path):
                from scripts.generate_findings_registry import main
                main()

        output = project_dir / "FINDINGS_REGISTRY.json"
        data = json.loads(output.read_text())
        assert data["summary"]["total"] >= 1


# ── Pattern Tests ──────────────────────────────────────────


class TestPatterns:
    def test_finding_pattern_matches(self):
        """FINDING_PATTERN matches standard severity-number format."""
        matches = list(FINDING_PATTERN.finditer("Found CRITICAL-001 and HIGH-042"))
        assert len(matches) == 2

    def test_ux_pattern_matches(self):
        """UX_FINDING_PATTERN matches UX-severity-number format."""
        matches = list(UX_FINDING_PATTERN.finditer("UX-CRITICAL-001 and UX-LOW-005"))
        assert len(matches) == 2

    def test_severity_order(self):
        """SEVERITY_ORDER has all four levels."""
        assert SEVERITY_ORDER["CRITICAL"] < SEVERITY_ORDER["HIGH"]
        assert SEVERITY_ORDER["HIGH"] < SEVERITY_ORDER["MEDIUM"]
        assert SEVERITY_ORDER["MEDIUM"] < SEVERITY_ORDER["LOW"]
