#!/usr/bin/env bash
# Hook: PostToolUse -> Bash
# After `git push`: finds EKFLAB-N in recent commit messages and adds
# comments to Jira issues with commit details.
#
# Requires: JIRA_PAT (Infisical → env → .env)
# Non-blocking: exits 0 always (link failure should not block push)

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
JIRA_BASE_URL="https://jira.ekf.su"

# Only process git push commands
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
[ -z "$COMMAND" ] && exit 0

if ! echo "$COMMAND" | grep -qE '(^|&&|\|\||;)\s*git\s+push'; then
    exit 0
fi

# Check if push succeeded (PostToolUse = after execution)
STDOUT=$(echo "$INPUT" | jq -r '.stdout // empty' 2>/dev/null || echo "")
STDERR=$(echo "$INPUT" | jq -r '.stderr // empty' 2>/dev/null || echo "")
# Git push output goes to stderr; check for success indicators
if ! echo "$STDERR$STDOUT" | grep -qE '(->|Everything up-to-date)'; then
    exit 0
fi

# Load JIRA_PAT
if [ -z "${JIRA_PAT:-}" ]; then
    if [ -f "$PROJECT_DIR/scripts/lib/secrets.sh" ]; then
        # shellcheck disable=SC1091
        source "$PROJECT_DIR/scripts/lib/secrets.sh"
        if _infisical_universal_auth "$PROJECT_DIR" 2>/dev/null; then
            JIRA_PAT=$(infisical secrets get JIRA_PAT --projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain 2>/dev/null || true)
        fi
    fi
    if [ -z "${JIRA_PAT:-}" ] && [ -f "$PROJECT_DIR/.env" ]; then
        JIRA_PAT=$(grep -E '^JIRA_PAT=' "$PROJECT_DIR/.env" | cut -d= -f2- | tr -d '"' || true)
    fi
fi

if [ -z "${JIRA_PAT:-}" ]; then
    exit 0  # No PAT = skip silently
fi

# Get commits since last push (last 5 commits on current branch)
REPO_URL=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null | sed 's/\.git$//' || echo "")
# Convert SSH URL to HTTPS if needed
REPO_URL=$(echo "$REPO_URL" | sed 's|git@github.com:|https://github.com/|')

commits=$(git -C "$PROJECT_DIR" log --oneline -5 --format="%H|%an|%s" 2>/dev/null || echo "")
[ -z "$commits" ] && exit 0

linked=0
while IFS='|' read -r sha author message; do
    [ -z "$sha" ] && continue

    # Extract EKFLAB-N keys from commit message
    keys=$(echo "$message" | grep -oE 'EKFLAB-[0-9]+' | sort -u || true)
    [ -z "$keys" ] && continue

    short_sha="${sha:0:7}"
    commit_url="${REPO_URL}/commit/${sha}"
    first_line=$(echo "$message" | head -c 120)

    comment="*Коммит:* [${short_sha}|${commit_url}]
*Автор:* ${author}
*Сообщение:* ${first_line}
*Ветка:* $(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo 'main')"

    for key in $keys; do
        # Check if we already commented (avoid duplicates on repeated pushes)
        existing=$(timeout 3 curl -s \
            -H "Authorization: Bearer $JIRA_PAT" \
            "${JIRA_BASE_URL}/rest/api/2/issue/${key}/comment" 2>/dev/null | \
            jq -r ".comments[].body" 2>/dev/null | grep -c "$short_sha" || echo "0")

        if [ "$existing" -gt 0 ]; then
            continue
        fi

        # Add comment
        result=$(timeout 5 curl -s -o /dev/null -w "%{http_code}" \
            -X POST \
            -H "Authorization: Bearer $JIRA_PAT" \
            -H "Content-Type: application/json" \
            "${JIRA_BASE_URL}/rest/api/2/issue/${key}/comment" \
            -d "{\"body\": $(echo "$comment" | jq -Rs .)}" 2>/dev/null || echo "000")

        if [ "$result" = "201" ]; then
            linked=$((linked + 1))
        fi
    done
done <<< "$commits"

if [ "$linked" -gt 0 ]; then
    echo "Jira: привязано $linked коммитов к задачам."
fi

exit 0
