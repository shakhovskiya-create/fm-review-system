#!/usr/bin/env bash
# Auto-update memory layers after agent/sprint completion.
# Called by SubagentStop hook and sprint-close command.
#
# Usage:
#   update-memory.sh --agent <name> --summary <path>   # After agent completion
#   update-memory.sh --sprint <N> --status <status>     # After sprint close
#
# Layers updated:
#   Layer 2: MCP Memory (.claude-memory/memory.jsonl) — append observations
#   Layer 3: Graphiti (via queue-graphiti-episode.sh) — temporal episode
#   Layer 4: Local RAG (knowledge-base/) — re-index if new files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MEMORY_FILE="$PROJECT_DIR/.claude-memory/memory.jsonl"
KB_DIR="$PROJECT_DIR/knowledge-base"

# --- Layer 2: MCP Memory (append to memory.jsonl) ---
_update_mcp_memory() {
    local entity_name="$1"
    shift
    local observations=("$@")

    # Build JSON observation array
    local obs_json=""
    for obs in "${observations[@]}"; do
        [[ -n "$obs_json" ]] && obs_json+=","
        obs_json+="$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$obs")"
    done

    # Check if entity exists → add observations; else create entity
    if grep -qE "\"name\"[[:space:]]*:[[:space:]]*\"${entity_name}\"" "$MEMORY_FILE" 2>/dev/null; then
        # Entity exists — append observations using python to modify JSONL
        python3 -c "
import json, sys

entity_name = sys.argv[1]
new_obs = json.loads(sys.argv[2])

lines = []
updated = False
with open('$MEMORY_FILE', 'r') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue
        if obj.get('name') == entity_name and obj.get('type') == 'entity':
            existing = set(obj.get('observations', []))
            for o in new_obs:
                existing.add(o)
            obj['observations'] = sorted(existing)
            updated = True
        lines.append(json.dumps(obj, ensure_ascii=False))

with open('$MEMORY_FILE', 'w') as f:
    for line in lines:
        f.write(line + '\n')

if updated:
    print(f'  MCP Memory: updated {entity_name} (+{len(new_obs)} observations)')
else:
    print(f'  MCP Memory: entity {entity_name} not found, skipping update')
" "$entity_name" "[$obs_json]"
    else
        # Create new entity
        local entity_json
        entity_json=$(python3 -c "
import json, sys
print(json.dumps({
    'type': 'entity',
    'name': sys.argv[1],
    'entityType': 'sprint_record',
    'observations': json.loads(sys.argv[2])
}, ensure_ascii=False))
" "$entity_name" "[$obs_json]")
        echo "$entity_json" >> "$MEMORY_FILE"
        echo "  MCP Memory: created entity ${entity_name}"
    fi
}

# --- Layer 3: Graphiti (queue episode) ---
_update_graphiti() {
    local episode_name="$1"
    local episode_body="$2"
    local queue_dir="$PROJECT_DIR/.graphiti-queue"
    mkdir -p "$queue_dir"

    local filename
    filename=$(date +%s)_$(echo "$episode_name" | tr ' ' '_' | tr -cd '[:alnum:]_').json
    cat > "$queue_dir/$filename" <<EPISODE
{
  "name": "$episode_name",
  "body": $episode_body,
  "group_id": "ekf-shared",
  "source": "json"
}
EPISODE
    echo "  Graphiti: queued episode '$episode_name'"
}

# --- Layer 4: Local RAG (re-index if needed) ---
_update_rag() {
    if [[ -d "$KB_DIR" ]]; then
        local last_index="$PROJECT_DIR/.rag-db/last-index"
        if [[ ! -f "$last_index" ]]; then
            echo "  Local RAG: no index yet, skipping (run scripts/index-rag.sh manually)"
            return 0
        fi
        local new_files
        new_files=$(find "$KB_DIR" -name "*.md" -newer "$last_index" 2>/dev/null | wc -l || echo "0")
        if [[ "$new_files" -gt 0 ]]; then
            if [[ -x "$SCRIPT_DIR/index-rag.sh" ]]; then
                "$SCRIPT_DIR/index-rag.sh" 2>/dev/null || true
                echo "  Local RAG: re-indexed ($new_files new files)"
            fi
        fi
    fi
}

# --- Parse arguments ---
MODE=""
AGENT_NAME=""
SUMMARY_PATH=""
SPRINT_NUM=""
SPRINT_STATUS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent) AGENT_NAME="$2"; MODE="agent"; shift 2 ;;
        --summary) SUMMARY_PATH="$2"; shift 2 ;;
        --sprint) SPRINT_NUM="$2"; MODE="sprint"; shift 2 ;;
        --status) SPRINT_STATUS="$2"; shift 2 ;;
        *) shift ;;
    esac
done

# --- Agent completion ---
if [[ "$MODE" == "agent" && -n "$AGENT_NAME" ]]; then
    echo "=== Updating memory: agent ${AGENT_NAME} ==="

    if [[ -n "$SUMMARY_PATH" && -f "$SUMMARY_PATH" ]]; then
        # Extract key info from _summary.json (no 'local' — we're not inside a function)
        agent_id=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('agent','?'))" "$SUMMARY_PATH" 2>/dev/null || echo "?")
        status=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('status','?'))" "$SUMMARY_PATH" 2>/dev/null || echo "?")
        command=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('command','?'))" "$SUMMARY_PATH" 2>/dev/null || echo "?")
        timestamp=$(date +%Y-%m-%dT%H:%M:%S)

        _update_mcp_memory "PROJECT_SHPMNT_PROFIT" \
            "Agent ${AGENT_NAME} completed ${command}: status=${status} at ${timestamp}"

        _update_graphiti "Agent ${AGENT_NAME} completion" \
            "$(python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))" "$SUMMARY_PATH" 2>/dev/null || echo '{}')"
    else
        echo "  No _summary.json found, skipping detailed memory update"
    fi

    _update_rag
    echo "=== Memory update complete ==="
fi

# --- Sprint completion ---
if [[ "$MODE" == "sprint" && -n "$SPRINT_NUM" ]]; then
    echo "=== Updating memory: Sprint ${SPRINT_NUM} ==="

    _update_mcp_memory "PROJECT_SHPMNT_PROFIT" \
        "Sprint ${SPRINT_NUM} ${SPRINT_STATUS:-completed} on $(date +%Y-%m-%d)"

    _update_graphiti "Sprint ${SPRINT_NUM} ${SPRINT_STATUS:-completed}" \
        "{\"event\":\"Sprint ${SPRINT_NUM} ${SPRINT_STATUS:-completed}\",\"date\":\"$(date +%Y-%m-%d)\"}"

    _update_rag
    echo "=== Memory update complete ==="
fi
