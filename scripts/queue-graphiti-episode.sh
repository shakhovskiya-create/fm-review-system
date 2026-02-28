#!/usr/bin/env bash
# queue-graphiti-episode.sh — Queue _summary.json for Graphiti ingestion
#
# Called by SubagentStop hook (validate-summary.sh).
# Saves summary data as a queued episode in .graphiti-queue/.
# Orchestrator (Claude) processes the queue via mcp__graphiti__add_memory.
#
# Usage:
#   queue-graphiti-episode.sh <summary_json_path>
#
# Exit codes:
#   0 - queued successfully
#   1 - error (invalid input, missing file)

set -euo pipefail

SUMMARY_PATH="${1:-}"
if [ -z "$SUMMARY_PATH" ] || [ ! -f "$SUMMARY_PATH" ]; then
    echo "ERROR: Summary file not found: $SUMMARY_PATH" >&2
    exit 1
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
QUEUE_DIR="$PROJECT_DIR/.graphiti-queue"
mkdir -p "$QUEUE_DIR"

# Extract key fields from _summary.json
AGENT=$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
agent = d.get('agent', 'unknown')
command = d.get('command', 'unknown')
project = d.get('project', 'unknown')
fm_version = d.get('fmVersion', 'unknown')
status = d.get('status', 'unknown')
timestamp = d.get('timestamp', 'unknown')

# Build episode name
print(f'{project}: {agent} {command} (FM v{fm_version})')
" "$SUMMARY_PATH" 2>/dev/null || echo "unknown")

if [ "$AGENT" = "unknown" ]; then
    echo "WARNING: Could not parse summary, skipping queue" >&2
    exit 0
fi

# Create queue entry: timestamp-based filename for ordering
QUEUE_FILE="$QUEUE_DIR/$(date +%Y%m%d-%H%M%S)-$(basename "$(dirname "$SUMMARY_PATH")").json"

python3 -c "
import json, sys, os
from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))

summary_path = sys.argv[1]
queue_path = sys.argv[2]

with open(summary_path) as f:
    summary = json.load(f)

# Build episode body from summary
parts = []
agent = summary.get('agent', 'unknown')
command = summary.get('command', 'unknown')
project = summary.get('project', 'unknown')
fm_version = summary.get('fmVersion', 'unknown')
status = summary.get('status', 'unknown')
timestamp = summary.get('timestamp', 'unknown')

parts.append(f'Agent {agent} completed {command} for {project} (FM v{fm_version})')
parts.append(f'Status: {status}, Timestamp: {timestamp}')

# Add counts if present
counts = summary.get('counts', {})
if counts:
    counts_str = ', '.join(f'{k}: {v}' for k, v in counts.items())
    parts.append(f'Findings: {counts_str}')

# Add notes if present
notes = summary.get('notes', '')
if notes:
    parts.append(f'Notes: {notes}')

# Add findings details if present
findings = summary.get('findings', [])
if findings:
    for f_item in findings[:10]:  # max 10 findings to keep episode manageable
        fid = f_item.get('id', '?')
        sev = f_item.get('severity', '?')
        desc = f_item.get('description', '')[:200]
        stat = f_item.get('status', '?')
        parts.append(f'  {fid} ({sev}): {desc} [{stat}]')

episode_body = '\\n'.join(parts)
episode_name = f'{project}: {agent} {command} (FM v{fm_version})'

queue_entry = {
    'name': episode_name,
    'episode_body': episode_body,
    'group_id': 'ekf-shared',
    'source': 'text',
    'source_description': f'Agent {agent} output summary',
    'summary_path': summary_path,
    'queued_at': datetime.now(MSK).isoformat()
}

with open(queue_path, 'w') as out:
    json.dump(queue_entry, out, ensure_ascii=False, indent=2)

print(f'Queued: {episode_name}')
" "$SUMMARY_PATH" "$QUEUE_FILE"
