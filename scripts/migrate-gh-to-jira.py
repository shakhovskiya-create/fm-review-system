#!/usr/bin/env python3
"""
Migrate GitHub Issues to Jira EKFLAB project.

Reads /tmp/gh_issues_full.json (exported by `gh issue list --json`),
creates Epics first, then tasks linked to epics and sprints.

Usage:
    python3 scripts/migrate-gh-to-jira.py [--dry-run] [--sprint N]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

# --- Config ---
JIRA_BASE = "https://jira.ekf.su"
PROJECT_KEY = "EKFLAB"

# Sprint IDs (created earlier)
SPRINT_IDS = {
    "27": 109,
    "28": 110,
    "29": 111,
    "30": 112,
    "31": 113,
}

# Issue type IDs from EKFLAB project
ISSUE_TYPES = {
    "Epic": "10000",
    "История": "10001",
    "Задача": "10002",
    "Подзадача": "10003",
    "Ошибка": "10004",
}

# Custom field IDs
SPRINT_FIELD = "customfield_10104"
EPIC_NAME_FIELD = "customfield_10102"  # Имя эпика (Jira Server)
EPIC_LINK_FIELD = "customfield_10100"  # Ссылка на эпик (Jira Server)

# Agent → Label mapping
AGENT_LABELS = {
    "0-creator": "agent:0-creator",
    "1-architect": "agent:1-architect",
    "2-simulator": "agent:2-simulator",
    "5-tech-architect": "agent:5-tech-architect",
    "7-publisher": "agent:7-publisher",
    "8-bpmn-designer": "agent:8-bpmn-designer",
    "9-se-go": "agent:9-se-go",
    "10-se-1c": "agent:10-se-1c",
    "11-dev-1c": "agent:11-dev-1c",
    "12-dev-go": "agent:12-dev-go",
    "13-qa-1c": "agent:13-qa-1c",
    "14-qa-go": "agent:14-qa-go",
    "15-trainer": "agent:15-trainer",
    "16-release-engineer": "agent:16-release-engineer",
    "orchestrator": "agent:orchestrator",
}

# Priority mapping
PRIORITY_MAP = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def get_jira_pat():
    """Get JIRA PAT from Infisical."""
    try:
        result = subprocess.run(
            [
                "bash", "-c",
                'source scripts/lib/secrets.sh && '
                '_infisical_universal_auth "$(pwd)" && '
                'infisical secrets get JIRA_PAT '
                '--projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain'
            ],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        pat = result.stdout.strip()
        if pat:
            return pat
    except Exception:
        pass

    # Fallback: env var
    return os.environ.get("JIRA_PAT", "")


def parse_gh_issue(issue: dict) -> dict:
    """Extract structured data from a GitHub issue."""
    labels = {l["name"] for l in issue.get("labels", [])}

    sprint = "none"
    itype = "task"
    agent = "none"
    priority = "medium"

    for label in labels:
        if label.startswith("sprint:"):
            sprint = label.split(":")[1]
        elif label.startswith("type:"):
            itype = label.split(":")[1]
        elif label.startswith("agent:"):
            agent = label.split(":")[1]
        elif label.startswith("priority:"):
            priority = label.split(":")[1]

    # Find parent epic from body (multiple patterns)
    parent = None
    body = issue.get("body", "") or ""
    m = re.search(r"Part of #(\d+)", body)
    if not m:
        m = re.search(r"Parent.*?#(\d+)", body)
    if not m:
        m = re.search(r"Epic.*?#(\d+)", body)
    if m:
        parent = int(m.group(1))

    return {
        "gh_number": issue["number"],
        "title": issue["title"],
        "body": body,
        "sprint": sprint,
        "type": itype,
        "agent": agent,
        "priority": priority,
        "parent_gh": parent,
        "labels": labels,
    }


def create_jira_issue(session, issue_data, epic_key=None, dry_run=False):
    """Create a single Jira issue."""
    is_epic = issue_data["type"] == "epic"

    # Determine Jira issue type
    if is_epic:
        jira_type = "Epic"
    else:
        jira_type = "Задача"

    # Build labels
    jira_labels = [f"gh:{issue_data['gh_number']}"]
    if issue_data["agent"] != "none":
        jira_labels.append(AGENT_LABELS.get(issue_data["agent"], f"agent:{issue_data['agent']}"))

    # Build description
    desc = f"*Migrated from GitHub Issue #{issue_data['gh_number']}*\n\n"
    if issue_data["body"]:
        # Convert markdown to Jira wiki markup (basic)
        body = issue_data["body"]
        body = re.sub(r"^## (.+)$", r"h2. \1", body, flags=re.MULTILINE)
        body = re.sub(r"^### (.+)$", r"h3. \1", body, flags=re.MULTILINE)
        body = re.sub(r"^- \[x\] (.+)$", r"* (/) \1", body, flags=re.MULTILINE)
        body = re.sub(r"^- \[ \] (.+)$", r"* (x) \1", body, flags=re.MULTILINE)
        body = re.sub(r"^- (.+)$", r"* \1", body, flags=re.MULTILINE)
        body = re.sub(r"`([^`]+)`", r"{{\1}}", body)
        desc += body

    # Build fields
    fields = {
        "project": {"key": PROJECT_KEY},
        "summary": issue_data["title"],
        "issuetype": {"name": jira_type},
        "description": desc,
        "labels": jira_labels,
    }

    # Priority
    jira_priority = PRIORITY_MAP.get(issue_data["priority"], "Medium")
    fields["priority"] = {"name": jira_priority}

    # Epic Name (required for Epic type)
    if is_epic:
        fields[EPIC_NAME_FIELD] = issue_data["title"]

    # Epic Link (for non-epic tasks)
    if not is_epic and epic_key:
        fields[EPIC_LINK_FIELD] = epic_key

    # Sprint
    sprint_id = SPRINT_IDS.get(issue_data["sprint"])
    if sprint_id:
        fields[SPRINT_FIELD] = sprint_id

    if dry_run:
        print(f"  [DRY] Would create {jira_type}: {issue_data['title']} "
              f"(GH#{issue_data['gh_number']}, sprint={issue_data['sprint']}, "
              f"epic={epic_key or 'none'})")
        return f"EKFLAB-DRY-{issue_data['gh_number']}"

    # Create issue
    resp = session.post(
        f"{JIRA_BASE}/rest/api/2/issue",
        json={"fields": fields}
    )

    if resp.status_code == 201:
        key = resp.json()["key"]
        print(f"  [OK] {key}: {issue_data['title']} (GH#{issue_data['gh_number']})")
        return key
    else:
        print(f"  [ERR] {resp.status_code}: {issue_data['title']} (GH#{issue_data['gh_number']})")
        try:
            errors = resp.json()
            print(f"        {json.dumps(errors, ensure_ascii=False)[:200]}")
        except Exception:
            print(f"        {resp.text[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Migrate GitHub Issues to Jira")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually create issues")
    parser.add_argument("--sprint", type=str, help="Only migrate specific sprint (e.g., 27)")
    parser.add_argument("--input", default="/tmp/gh_issues_full.json", help="Input JSON file")
    args = parser.parse_args()

    # Load issues
    with open(args.input) as f:
        raw_issues = json.load(f)

    print(f"Loaded {len(raw_issues)} GitHub issues")

    # Parse all issues
    issues = [parse_gh_issue(i) for i in raw_issues]

    # Filter by sprint if specified
    if args.sprint:
        issues = [i for i in issues if i["sprint"] == args.sprint]
        print(f"Filtered to sprint {args.sprint}: {len(issues)} issues")

    # Separate epics and tasks
    epics = [i for i in issues if i["type"] == "epic"]
    tasks = [i for i in issues if i["type"] != "epic"]

    print(f"Epics: {len(epics)}, Tasks: {len(tasks)}")

    # Get PAT
    pat = get_jira_pat()
    if not pat and not args.dry_run:
        print("ERROR: No JIRA_PAT found")
        sys.exit(1)

    # Create session
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    })

    # Map: GH issue number → Jira key
    gh_to_jira = {}

    # Step 1: Create Epics first
    print(f"\n=== Creating {len(epics)} Epics ===")
    for epic in sorted(epics, key=lambda x: x["gh_number"]):
        key = create_jira_issue(session, epic, dry_run=args.dry_run)
        if key:
            gh_to_jira[epic["gh_number"]] = key
        time.sleep(0.3)  # Rate limiting

    # Step 2: Create Tasks linked to Epics
    print(f"\n=== Creating {len(tasks)} Tasks ===")
    for task in sorted(tasks, key=lambda x: x["gh_number"]):
        epic_key = None
        if task["parent_gh"]:
            epic_key = gh_to_jira.get(task["parent_gh"])

        key = create_jira_issue(session, task, epic_key=epic_key, dry_run=args.dry_run)
        if key:
            gh_to_jira[task["gh_number"]] = key
        time.sleep(0.3)  # Rate limiting

    # Save mapping
    mapping_file = "/tmp/gh_to_jira_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(gh_to_jira, f, indent=2)

    print("\n=== Summary ===")
    print(f"Created: {len(gh_to_jira)} issues in Jira")
    print(f"Mapping saved to: {mapping_file}")

    # Print mapping table
    print(f"\n{'GH#':>6} | {'Jira Key':>12} | Title")
    print("-" * 70)
    for gh_num, jira_key in sorted(gh_to_jira.items()):
        title = next((i["title"] for i in issues if i["gh_number"] == gh_num), "?")
        print(f"  #{gh_num:<4} | {jira_key:>12} | {title[:45]}")


if __name__ == "__main__":
    main()
