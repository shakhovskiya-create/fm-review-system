#!/usr/bin/env python3
"""
Generate FINDINGS_REGISTRY.json — central cross-agent findings aggregator.

Scans AGENT_1, AGENT_2, AGENT_4, AGENT_5 directories for _summary.json files
and Markdown reports. Extracts findings, deduplicates, and writes a unified registry.

Usage:
    python3 scripts/generate_findings_registry.py PROJECT_SHPMNT_PROFIT
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
AGENT_SOURCES = {
    "AGENT_1_ARCHITECT": "Agent1_Architect",
    "AGENT_2_ROLE_SIMULATOR": "Agent2_Simulator",
    "AGENT_4_QA_TESTER": "Agent4_QA",
    "AGENT_5_TECH_ARCHITECT": "Agent5_TechArchitect",
}

# Patterns for finding IDs in Markdown
FINDING_PATTERN = re.compile(
    r"\[?(CRITICAL|HIGH|MEDIUM|LOW)-(\d{3})\]?"
)
UX_FINDING_PATTERN = re.compile(
    r"\[?(UX-(?:CRITICAL|HIGH|MEDIUM|LOW)-\d{3})\]?"
)

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def extract_findings_from_summary(summary_path: Path, source: str) -> list:
    """Extract findings from _summary.json counts."""
    findings = []
    try:
        with open(summary_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return findings

    counts = data.get("counts", {})
    # Summary-level findings don't have individual IDs; they provide totals.
    # We note them but prefer Markdown extraction for details.
    return findings


def extract_findings_from_markdown(md_path: Path, source: str) -> list:
    """Extract findings from Markdown report files."""
    findings = []
    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError:
        return findings

    # Extract standard findings (CRITICAL-001, HIGH-002, etc.)
    for match in FINDING_PATTERN.finditer(content):
        severity = match.group(1)
        num = match.group(2)
        finding_id = f"{severity}-{num}"

        # Try to extract description from surrounding context
        pos = match.start()
        # Get line containing the finding
        line_start = content.rfind("\n", 0, pos) + 1
        line_end = content.find("\n", pos)
        if line_end == -1:
            line_end = len(content)
        line = content[line_start:line_end].strip()

        # Clean up the description
        desc = re.sub(r"^\[?" + re.escape(finding_id) + r"\]?\s*[:\-–]\s*", "", line)
        desc = re.sub(r"^[#*|]+\s*", "", desc).strip()
        if len(desc) < 10:
            desc = f"Finding {finding_id} from {source}"

        findings.append({
            "id": finding_id,
            "source": source,
            "severity": severity,
            "category": "LOGIC",  # Default; agents should set this
            "description": desc[:200],
            "location": "",
            "status": "Open",
        })

    # Extract UX findings (UX-CRITICAL-001, etc.)
    for match in UX_FINDING_PATTERN.finditer(content):
        ux_id = match.group(1)
        severity = ux_id.split("-")[1]

        pos = match.start()
        line_start = content.rfind("\n", 0, pos) + 1
        line_end = content.find("\n", pos)
        if line_end == -1:
            line_end = len(content)
        line = content[line_start:line_end].strip()

        desc = re.sub(r"^\[?" + re.escape(ux_id) + r"\]?\s*[:\-–]\s*", "", line)
        desc = re.sub(r"^[#*|]+\s*", "", desc).strip()
        if len(desc) < 10:
            desc = f"UX Finding {ux_id} from {source}"

        findings.append({
            "id": ux_id,
            "source": source,
            "severity": severity,
            "category": "UX",
            "description": desc[:200],
            "location": "",
            "status": "Open",
        })

    return findings


def deduplicate(findings: list) -> list:
    """Deduplicate findings by ID, keeping first occurrence."""
    seen = set()
    unique = []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            unique.append(f)
    return unique


def build_summary(findings: list) -> dict:
    """Build summary statistics."""
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_source = {}
    by_status = {}

    for f in findings:
        sev = f["severity"].lower()
        if sev in by_severity:
            by_severity[sev] += 1
        src = f["source"]
        by_source[src] = by_source.get(src, 0) + 1
        st = f["status"]
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "total": len(findings),
        "bySeverity": by_severity,
        "bySource": by_source,
        "byStatus": by_status,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_findings_registry.py PROJECT_NAME")
        sys.exit(1)

    project_name = sys.argv[1]
    project_dir = ROOT_DIR / "projects" / project_name

    if not project_dir.is_dir():
        print(f"ERROR: Project directory not found: {project_dir}")
        sys.exit(1)

    # Determine FM version from PROJECT_CONTEXT.md
    fm_version = "0.0.0"
    ctx_path = project_dir / "PROJECT_CONTEXT.md"
    if ctx_path.exists():
        ctx_content = ctx_path.read_text(encoding="utf-8")
        ver_match = re.search(r"Версия ФМ:\s*(\d+\.\d+\.\d+)", ctx_content)
        if ver_match:
            fm_version = ver_match.group(1)

    all_findings = []

    for agent_dir_name, source_name in AGENT_SOURCES.items():
        agent_dir = project_dir / agent_dir_name
        if not agent_dir.is_dir():
            continue

        # Scan Markdown reports
        for md_file in sorted(agent_dir.glob("*.md")):
            findings = extract_findings_from_markdown(md_file, source_name)
            all_findings.extend(findings)

        # Also scan subdirectories (e.g., AGENT_1_ARCHITECT/audit/)
        for md_file in sorted(agent_dir.rglob("*.md")):
            if md_file.parent == agent_dir:
                continue  # Already scanned
            findings = extract_findings_from_markdown(md_file, source_name)
            all_findings.extend(findings)

    # Deduplicate
    all_findings = deduplicate(all_findings)

    # Sort by severity
    all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))

    # Build registry
    registry = {
        "project": project_name,
        "fmVersion": fm_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": all_findings,
        "summary": build_summary(all_findings),
    }

    # Write output
    output_path = project_dir / "FINDINGS_REGISTRY.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    print(f"FINDINGS_REGISTRY.json generated: {output_path}")
    print(f"  Total findings: {registry['summary']['total']}")
    for sev, count in registry["summary"]["bySeverity"].items():
        if count > 0:
            print(f"  {sev.upper()}: {count}")
    for src, count in registry["summary"]["bySource"].items():
        print(f"  From {src}: {count}")


if __name__ == "__main__":
    main()
