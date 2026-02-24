#!/usr/bin/env bash
# cost-report.sh — Monthly cost breakdown by agent from Langfuse API.
#
# Usage:
#   ./scripts/cost-report.sh                    # Current month
#   ./scripts/cost-report.sh --month 2026-01    # Specific month
#   ./scripts/cost-report.sh --days 7           # Last N days
#
# Requires: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL in env.
# Falls back to Infisical → .env via load-secrets.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load secrets if not in env
if [ -z "${LANGFUSE_PUBLIC_KEY:-}" ] || [ -z "${LANGFUSE_SECRET_KEY:-}" ]; then
    if [ -f "$SCRIPT_DIR/load-secrets.sh" ]; then
        # shellcheck source=scripts/load-secrets.sh
        source "$SCRIPT_DIR/load-secrets.sh" 2>/dev/null || true
    fi
fi

# Validate
if [ -z "${LANGFUSE_PUBLIC_KEY:-}" ] || [ -z "${LANGFUSE_SECRET_KEY:-}" ]; then
    echo "ERROR: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required" >&2
    exit 1
fi

LANGFUSE_HOST="${LANGFUSE_BASE_URL:-${LANGFUSE_HOST:-https://cloud.langfuse.com}}"

# Parse args
PERIOD_MODE="month"
MONTH=""
DAYS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --month)
            PERIOD_MODE="month"
            MONTH="$2"
            shift 2
            ;;
        --days)
            PERIOD_MODE="days"
            DAYS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--month YYYY-MM | --days N]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Calculate date range
if [ "$PERIOD_MODE" = "month" ]; then
    if [ -z "$MONTH" ]; then
        FROM_DATE="$(date -u +%Y-%m-01T00:00:00Z)"
        TO_DATE="$(date -u +%Y-%m-%dT23:59:59Z)"
        PERIOD_LABEL="$(date +%Y-%m) (MTD)"
    else
        FROM_DATE="${MONTH}-01T00:00:00Z"
        # Last day of month
        TO_DATE="$(date -u -d "${MONTH}-01 + 1 month - 1 day" +%Y-%m-%dT23:59:59Z 2>/dev/null || \
                   date -u -v1m -v-1d -j -f '%Y-%m-%d' "${MONTH}-01" +%Y-%m-%dT23:59:59Z 2>/dev/null)"
        PERIOD_LABEL="$MONTH"
    fi
else
    FROM_DATE="$(date -u -d "${DAYS} days ago" +%Y-%m-%dT00:00:00Z 2>/dev/null || \
                 date -u -v-${DAYS}d +%Y-%m-%dT00:00:00Z 2>/dev/null)"
    TO_DATE="$(date -u +%Y-%m-%dT23:59:59Z)"
    PERIOD_LABEL="last ${DAYS} days"
fi

echo "=== FM Review System — Cost Report ==="
echo "Period: $PERIOD_LABEL"
echo "Source: $LANGFUSE_HOST"
echo ""

# Fetch traces via Langfuse API (paginated)
PAGE=1
TOTAL_COST=0
declare -A AGENT_COST AGENT_SESSIONS AGENT_TOKENS

fetch_page() {
    curl -sf -u "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
        "${LANGFUSE_HOST}/api/public/traces?page=${1}&limit=100&fromTimestamp=${FROM_DATE}&toTimestamp=${TO_DATE}" \
        2>/dev/null || echo '{"data":[]}'
}

while true; do
    RESPONSE=$(fetch_page "$PAGE")
    COUNT=$(echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
traces = data.get('data', [])
print(len(traces))
for t in traces:
    meta = t.get('metadata', {}) or {}
    cost = float(meta.get('cost_usd', 0))
    name = t.get('name', 'unknown')
    tags = t.get('tags', []) or []
    # Extract agent from name or tags
    agent = 'interactive'
    for tag in tags:
        if tag.startswith('agent:'):
            agent = tag
            break
    if name.startswith('agent-'):
        agent = name
    input_t = int(meta.get('input_tokens', 0) if meta.get('input_tokens') else 0)
    output_t = int(meta.get('output_tokens', 0) if meta.get('output_tokens') else 0)
    print(f'{agent}\t{cost}\t{input_t + output_t}')
" 2>/dev/null)

    LINE_COUNT=$(echo "$COUNT" | head -1)

    if [ "$LINE_COUNT" = "0" ] && [ "$PAGE" -gt 1 ]; then
        break
    fi

    # Parse results
    while IFS=$'\t' read -r agent cost tokens; do
        [ "$agent" = "$LINE_COUNT" ] && continue  # skip first line (count)
        AGENT_COST["$agent"]=$(python3 -c "print(round(${AGENT_COST[$agent]:-0} + ${cost:-0}, 6))")
        AGENT_SESSIONS["$agent"]=$(( ${AGENT_SESSIONS[$agent]:-0} + 1 ))
        AGENT_TOKENS["$agent"]=$(( ${AGENT_TOKENS[$agent]:-0} + ${tokens:-0} ))
        TOTAL_COST=$(python3 -c "print(round(${TOTAL_COST} + ${cost:-0}, 6))")
    done <<< "$COUNT"

    if [ "$LINE_COUNT" -lt 100 ]; then
        break
    fi
    PAGE=$((PAGE + 1))
done

# Print report
echo "┌────────────────────────┬──────────┬──────────┬─────────────┐"
echo "│ Agent                  │ Sessions │ Cost USD │ Tokens      │"
echo "├────────────────────────┼──────────┼──────────┼─────────────┤"

for agent in $(echo "${!AGENT_COST[@]}" | tr ' ' '\n' | sort); do
    printf "│ %-22s │ %8d │ %8s │ %11s │\n" \
        "$agent" \
        "${AGENT_SESSIONS[$agent]}" \
        "\$${AGENT_COST[$agent]}" \
        "${AGENT_TOKENS[$agent]}"
done

echo "├────────────────────────┼──────────┼──────────┼─────────────┤"

TOTAL_SESSIONS=0
TOTAL_TOKENS=0
for agent in "${!AGENT_SESSIONS[@]}"; do
    TOTAL_SESSIONS=$(( TOTAL_SESSIONS + ${AGENT_SESSIONS[$agent]} ))
    TOTAL_TOKENS=$(( TOTAL_TOKENS + ${AGENT_TOKENS[$agent]} ))
done

printf "│ %-22s │ %8d │ %8s │ %11s │\n" \
    "TOTAL" "$TOTAL_SESSIONS" "\$${TOTAL_COST}" "$TOTAL_TOKENS"
echo "└────────────────────────┴──────────┴──────────┴─────────────┘"
echo ""

# Budget alert
MONTHLY_BUDGET="${FM_REVIEW_MONTHLY_BUDGET:-100}"
if python3 -c "exit(0 if $TOTAL_COST > $MONTHLY_BUDGET * 0.8 else 1)" 2>/dev/null; then
    echo "⚠️  WARNING: Cost \$${TOTAL_COST} is ≥80% of monthly budget \$${MONTHLY_BUDGET}"
    if [ -f "$SCRIPT_DIR/notify.sh" ]; then
        "$SCRIPT_DIR/notify.sh" --level WARN --event "cost_budget_warning" \
            --message "Monthly cost \$${TOTAL_COST} is ≥80% of budget \$${MONTHLY_BUDGET}" 2>/dev/null || true
    fi
fi
