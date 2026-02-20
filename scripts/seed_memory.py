#!/usr/bin/env python3
"""
Seed the MCP Knowledge Graph memory with FM Review System metadata.

Populates .claude-memory/memory.jsonl with:
- Agent roles and capabilities
- Project metadata (name, PAGE_ID, FM version)
- Pipeline stages and dependencies
- Cross-agent data flow

Usage:
    python3 scripts/seed_memory.py [--reset]
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_FILE = PROJECT_ROOT / ".claude-memory" / "memory.jsonl"

# ── Agent definitions ──────────────────────────────────────────
AGENTS = [
    {
        "name": "Agent0_Creator",
        "entityType": "agent",
        "observations": [
            "Creates FM from scratch via interview",
            "Commands: /new, /apply",
            "Writes to Confluence via Agent 7",
            "File: agents/AGENT_0_CREATOR.md",
            "Tools: Read, Write, Edit, Grep, Glob, Bash, WebFetch",
        ],
    },
    {
        "name": "Agent1_Architect",
        "entityType": "agent",
        "observations": [
            "Full FM audit: business logic + 1C compatibility",
            "Commands: /audit, /apply, /auto",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_1_ARCHITECT/ (audit-report-v*.md, _summary.json)",
            "File: agents/AGENT_1_ARCHITECT.md",
            "Priority: highest in conflict resolution",
        ],
    },
    {
        "name": "Agent2_RoleSimulator",
        "entityType": "agent",
        "observations": [
            "Simulates user roles (manager, warehouse, accountant)",
            "Commands: /simulate-all, /simulate-role",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_2_ROLE_SIMULATOR/",
            "Uses Agent 1 findings for focus",
        ],
    },
    {
        "name": "Agent3_Defender",
        "entityType": "agent",
        "observations": [
            "Analyzes business stakeholder objections",
            "Commands: /respond, /classify",
            "Classification: A-I (Covered/Conscious Choice/Gap/Backlog/Impossible/Research/Incorrect/Role Conflict/Slows Down)",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_3_DEFENDER/",
        ],
    },
    {
        "name": "Agent4_QATester",
        "entityType": "agent",
        "observations": [
            "Generates test cases from FM",
            "Commands: /generate-all, /trace",
            "Creates traceability-matrix.json (FC-10A)",
            "Read-only (disallowedTools: Write, Edit)",
            "Output: AGENT_4_QA_TESTER/",
        ],
    },
    {
        "name": "Agent5_TechArchitect",
        "entityType": "agent",
        "observations": [
            "Designs 1C implementation architecture",
            "Commands: /full, /tz, /arch",
            "Creates TS-FM-* (technical specification) and ARC-FM-* (architecture)",
            "Publishes to Confluence",
            "Output: AGENT_5_TECH_ARCHITECT/",
        ],
    },
    {
        "name": "Agent6_Presenter",
        "entityType": "agent",
        "observations": [
            "Creates presentations and reports",
            "Commands: /present, /export",
            "Synthesizes all agent outputs",
            "Output: REPORTS/",
        ],
    },
    {
        "name": "Agent7_Publisher",
        "entityType": "agent",
        "observations": [
            "ONLY agent that writes to Confluence",
            "Commands: /publish, /sync, /update",
            "Uses confluence_utils.py (lock, backup, retry, audit log)",
            "Requires Quality Gate before publishing",
            "Has quality-gate skill preloaded",
            "Output: AGENT_7_PUBLISHER/",
        ],
    },
    {
        "name": "Agent8_BPMNDesigner",
        "entityType": "agent",
        "observations": [
            "Creates BPMN diagrams for Confluence",
            "Commands: /bpmn",
            "Attaches .drawio files to Confluence pages",
            "Output: AGENT_8_BPMN_DESIGNER/",
        ],
    },
    {
        "name": "Orchestrator_Helper",
        "entityType": "agent",
        "observations": [
            "Main Claude Code session role - NOT a subagent",
            "Dual role: FM agent router + project infrastructure architect",
            "Protocol: agents/ORCHESTRATOR_HELPER.md",
            "Subagent file: .claude/agents/helper-architect.md",
            "Manages: hooks, scripts, MCP servers, CI/CD, tests, agent protocols",
            "Delegates FM content work to agents 0-8",
            "Has Episodic Memory access (subagents do not)",
        ],
    },
]

# ── Pipeline stages ────────────────────────────────────────────
PIPELINE = {
    "name": "FM_Pipeline",
    "entityType": "pipeline",
    "observations": [
        "Sequential stages: [[1], [2,4], [5], [3], [quality_gate], [7], [8,6]]",
        "Agents 2 and 4 run in parallel",
        "Agents 8 and 6 run in parallel",
        "Quality Gate is mandatory before Agent 7",
        "Exit codes: 0=ready, 1=critical block, 2=warnings (skippable with --reason)",
        "Managed by scripts/run_agent.py (Claude Code SDK)",
        "Langfuse tracing: PipelineTracer in run_agent.py",
    ],
}

# ── Relations ──────────────────────────────────────────────────
RELATIONS = [
    ("Agent1_Architect", "Agent2_RoleSimulator", "provides_findings_to"),
    ("Agent1_Architect", "Agent4_QATester", "provides_findings_to"),
    ("Agent2_RoleSimulator", "Agent5_TechArchitect", "provides_ux_to"),
    ("Agent4_QATester", "Agent5_TechArchitect", "provides_tests_to"),
    ("Agent1_Architect", "Agent3_Defender", "provides_findings_to"),
    ("Agent2_RoleSimulator", "Agent3_Defender", "provides_ux_to"),
    ("Agent7_Publisher", "FM_Pipeline", "publishes_for"),
    ("Agent0_Creator", "Agent7_Publisher", "sends_content_to"),
    ("Agent5_TechArchitect", "Agent7_Publisher", "sends_docs_to"),
    ("Agent6_Presenter", "FM_Pipeline", "finalizes_for"),
    ("Orchestrator_Helper", "FM_Pipeline", "orchestrates"),
    ("Orchestrator_Helper", "Agent0_Creator", "delegates_fm_to"),
    ("Orchestrator_Helper", "Agent1_Architect", "delegates_fm_to"),
]


def discover_projects() -> list[dict]:
    """Discover active projects from projects/ directory."""
    entities = []
    projects_dir = PROJECT_ROOT / "projects"
    if not projects_dir.exists():
        return entities

    for project_dir in sorted(projects_dir.glob("PROJECT_*")):
        if not project_dir.is_dir():
            continue

        name = project_dir.name
        observations = [f"Directory: projects/{name}"]

        # PAGE_ID
        page_id_file = project_dir / "CONFLUENCE_PAGE_ID"
        if page_id_file.exists():
            page_id = page_id_file.read_text().strip()
            if page_id:
                observations.append(f"Confluence PAGE_ID: {page_id}")

        # FM version from PROJECT_CONTEXT.md
        ctx_file = project_dir / "PROJECT_CONTEXT.md"
        if ctx_file.exists():
            import re

            content = ctx_file.read_text(encoding="utf-8")
            ver_match = re.search(r"v(\d+\.\d+\.\d+)", content)
            if ver_match:
                observations.append(f"FM version: v{ver_match.group(1)}")

            # FM code
            code_match = re.search(r"FM-[\w-]+", content)
            if code_match:
                observations.append(f"FM code: {code_match.group(0)}")

        # Agent results
        agent_dirs = sorted(project_dir.glob("AGENT_*"))
        completed = [d.name for d in agent_dirs if any(d.glob("*.md"))]
        if completed:
            observations.append(f"Completed agents: {', '.join(completed)}")

        # Changes
        changes_dir = project_dir / "CHANGES"
        if changes_dir.exists():
            changes = list(changes_dir.glob("*-CHANGES.md"))
            if changes:
                observations.append(f"Change logs: {len(changes)}")

        entities.append(
            {
                "name": name,
                "entityType": "project",
                "observations": observations,
            }
        )

    return entities


def write_memory(entities: list[dict], relations: list[tuple], reset: bool = False):
    """Write entities and relations to memory.jsonl."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if reset and MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
        print("Reset: existing memory.jsonl deleted")

    # Read existing data to avoid duplicates
    # Handles both old format (no "type" field) and MCP format (with "type" field)
    existing_names = set()
    existing_rels = set()
    if MEMORY_FILE.exists():
        for line in MEMORY_FILE.read_text().splitlines():
            if line.strip():
                try:
                    obj = json.loads(line)
                    obj_type = obj.get("type", "")
                    if obj_type == "entity" or ("name" in obj and "entityType" in obj):
                        existing_names.add(obj["name"])
                    elif obj_type == "relation" or ("from" in obj and "to" in obj):
                        existing_rels.add((obj["from"], obj["to"], obj["relationType"]))
                except json.JSONDecodeError:
                    pass

    added = 0
    rels_added = 0
    with open(MEMORY_FILE, "a") as f:
        for entity in entities:
            if entity["name"] not in existing_names:
                # MCP server-memory requires "type" field to load entries
                record = {"type": "entity", **entity}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                added += 1
                existing_names.add(entity["name"])

        for from_name, to_name, rel_type in relations:
            rel_key = (from_name, to_name, rel_type)
            if rel_key not in existing_rels:
                rel = {"type": "relation", "from": from_name, "to": to_name, "relationType": rel_type}
                f.write(json.dumps(rel, ensure_ascii=False) + "\n")
                rels_added += 1
                existing_rels.add(rel_key)

    return added


def main():
    reset = "--reset" in sys.argv

    # Collect all entities
    entities = AGENTS + [PIPELINE]
    projects = discover_projects()
    entities.extend(projects)

    # Project-to-pipeline relations
    project_relations = list(RELATIONS)
    for proj in projects:
        project_relations.append((proj["name"], "FM_Pipeline", "uses_pipeline"))

    added = write_memory(entities, project_relations, reset=reset)

    print(f"Knowledge graph: {MEMORY_FILE}")
    print(f"  Entities added: {added}")
    print(f"  Relations added: {len(project_relations)}")
    print(f"  Projects found: {len(projects)}")

    # Summary
    if MEMORY_FILE.exists():
        lines = MEMORY_FILE.read_text().splitlines()
        print(f"  Total lines: {len(lines)}")


if __name__ == "__main__":
    main()
