#!/usr/bin/env bash
# Hook: SubagentStop - validate _summary.json creation after agent completion
# Fires after custom agents (agent-0..8) complete their work.
# Checks that the agent created a _summary.json file per FC-07A protocol.
#
# Environment:
#   CLAUDE_PROJECT_DIR - project root directory
#
# Exit codes:
#   0 - always (warning only, does not block)

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Find active project directories
found_warning=false

for project_dir in "$PROJECT_DIR"/projects/PROJECT_*/; do
    [ -d "$project_dir" ] || continue

    # Check each AGENT_* directory for recent _summary.json
    for agent_dir in "$project_dir"AGENT_*/; do
        [ -d "$agent_dir" ] || continue

        # Look for _summary.json files modified in the last 10 minutes
        recent=$(find "$agent_dir" -maxdepth 1 -name "*_summary.json" -mmin -10 2>/dev/null | head -1)

        if [ -n "$recent" ]; then
            # Validate JSON structure (minimal check)
            if command -v python3 &>/dev/null; then
                valid=$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    required = ['agent', 'command', 'timestamp', 'status']
    missing = [k for k in required if k not in data]
    if missing:
        print(f'WARN: Missing fields in _summary.json: {missing}')
        sys.exit(1)
    print('OK')
except Exception as e:
    print(f'WARN: Invalid _summary.json: {e}')
    sys.exit(1)
" "$recent" 2>&1)
                if [ $? -ne 0 ]; then
                    echo "$valid"
                    found_warning=true
                fi
            fi
        fi
    done
done

# No recent summaries found is not an error - the agent may not have
# produced output that requires a summary (e.g., simple queries).

exit 0
