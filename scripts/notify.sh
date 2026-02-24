#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# NOTIFY.SH — Alert system for critical pipeline events (MEDIUM-X3)
# ═══════════════════════════════════════════════════════════════
# Usage:
#   ./scripts/notify.sh --level ERROR --event "confluence_write_failed" --message "PUT returned 500"
#   ./scripts/notify.sh --level WARN  --event "quality_gate_override" --project PROJECT_SHPMNT_PROFIT
#   ./scripts/notify.sh --level INFO  --event "pipeline_complete" --project PROJECT_SHPMNT_PROFIT
#
# Notification channels (checked in order):
#   1. SLACK_WEBHOOK_URL env var → Slack webhook POST
#   2. NOTIFY_EMAIL env var → mail (if available)
#   3. Always: append to logs/notifications.jsonl
#
# Environment:
#   SLACK_WEBHOOK_URL  — Slack incoming webhook URL (optional)
#   NOTIFY_EMAIL       — Email address for alerts (optional)
#   NOTIFY_MIN_LEVEL   — Minimum level to notify: INFO|WARN|ERROR|CRITICAL (default: WARN)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ─── Defaults ──────────────────────────────────────────────────
LEVEL="INFO"
EVENT=""
MESSAGE=""
PROJECT=""
AGENT=""

# ─── Parse args ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --level)   LEVEL="$2"; shift 2 ;;
        --event)   EVENT="$2"; shift 2 ;;
        --message) MESSAGE="$2"; shift 2 ;;
        --project) PROJECT="$2"; shift 2 ;;
        --agent)   AGENT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 --level LEVEL --event EVENT [--message MSG] [--project NAME] [--agent NAME]"
            echo ""
            echo "Levels: INFO, WARN, ERROR, CRITICAL"
            echo "Events: confluence_write_failed, quality_gate_blocked, agent_timeout,"
            echo "        pipeline_complete, pipeline_failed, secret_missing"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

[[ -z "$EVENT" ]] && { echo "ERROR: --event is required"; exit 1; }

# ─── Level filtering ──────────────────────────────────────────
_level_num() {
    case "$1" in
        INFO)     echo 0 ;;
        WARN)     echo 1 ;;
        ERROR)    echo 2 ;;
        CRITICAL) echo 3 ;;
        *)        echo 0 ;;
    esac
}

MIN_LEVEL="${NOTIFY_MIN_LEVEL:-WARN}"
if [[ $(_level_num "$LEVEL") -lt $(_level_num "$MIN_LEVEL") ]]; then
    exit 0  # Below notification threshold
fi

# ─── Build JSON payload ───────────────────────────────────────
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)
HOSTNAME=$(hostname 2>/dev/null || echo "unknown")

# Build JSON safely with printf (no jq dependency)
JSON_PAYLOAD=$(printf '{"timestamp":"%s","level":"%s","event":"%s","message":"%s","project":"%s","agent":"%s","host":"%s"}' \
    "$TIMESTAMP" "$LEVEL" "$EVENT" \
    "$(echo "$MESSAGE" | sed 's/"/\\"/g' | head -c 500)" \
    "$PROJECT" "$AGENT" "$HOSTNAME")

# ─── 1. Always: log to file ───────────────────────────────────
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "$LOG_DIR"
echo "$JSON_PAYLOAD" >> "$LOG_DIR/notifications.jsonl"

# ─── 2. Slack webhook ─────────────────────────────────────────
SLACK_URL="${SLACK_WEBHOOK_URL:-}"
if [[ -n "$SLACK_URL" ]]; then
    # Format for Slack
    ICON=""
    case "$LEVEL" in
        INFO)     ICON=":information_source:" ;;
        WARN)     ICON=":warning:" ;;
        ERROR)    ICON=":x:" ;;
        CRITICAL) ICON=":rotating_light:" ;;
    esac

    SLACK_TEXT="${ICON} *[${LEVEL}]* \`${EVENT}\`"
    [[ -n "$PROJECT" ]] && SLACK_TEXT="${SLACK_TEXT} | project: \`${PROJECT}\`"
    [[ -n "$AGENT" ]] && SLACK_TEXT="${SLACK_TEXT} | agent: \`${AGENT}\`"
    [[ -n "$MESSAGE" ]] && SLACK_TEXT="${SLACK_TEXT}\n${MESSAGE}"

    SLACK_BODY=$(printf '{"text":"%s"}' "$(echo "$SLACK_TEXT" | sed 's/"/\\"/g')")

    # Non-blocking: don't fail pipeline if Slack is down
    curl -sf -m 5 -X POST -H 'Content-type: application/json' \
        -d "$SLACK_BODY" "$SLACK_URL" >/dev/null 2>&1 || true
fi

# ─── 3. Email (if available) ──────────────────────────────────
NOTIFY_EMAIL="${NOTIFY_EMAIL:-}"
if [[ -n "$NOTIFY_EMAIL" ]] && command -v mail &>/dev/null; then
    SUBJECT="[fm-review ${LEVEL}] ${EVENT}"
    BODY="Level: ${LEVEL}\nEvent: ${EVENT}\nProject: ${PROJECT}\nAgent: ${AGENT}\nMessage: ${MESSAGE}\nTime: ${TIMESTAMP}"
    echo -e "$BODY" | mail -s "$SUBJECT" "$NOTIFY_EMAIL" 2>/dev/null || true
fi

# ─── Output for hook callers ──────────────────────────────────
echo "${TIMESTAMP} | ${LEVEL} | ${EVENT} | ${MESSAGE:-no message}"

exit 0
