#!/usr/bin/env bash
# MCP Jira server launcher with Infisical support.
# Priority: Infisical (Universal Auth) -> env var -> .env file.
# Used by .mcp.json as the command for Jira MCP server.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

JIRA_BASE_URL="https://jira.ekf.su"

# Priority 1: Infisical Universal Auth (Machine Identity)
if _infisical_universal_auth "$PROJECT_DIR"; then
    JIRA_PAT=$(infisical secrets get JIRA_PAT --projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain 2>/dev/null || true)
    if [[ -n "$JIRA_PAT" ]]; then
        export JIRA_BASE_URL JIRA_PAT
        exec npx -y mcp-jira-server
    fi
fi

# Priority 2: env var already set
if [[ -n "${JIRA_PAT:-}" ]]; then
    export JIRA_BASE_URL JIRA_PAT
    exec npx -y mcp-jira-server
fi

# Priority 3: .env file
if [[ -f "$PROJECT_DIR/.env" ]]; then
    while IFS='=' read -r key val; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        [[ "$key" == "JIRA_PAT" ]] && export JIRA_PAT="$val"
    done < "$PROJECT_DIR/.env"
    if [[ -n "${JIRA_PAT:-}" ]]; then
        export JIRA_BASE_URL JIRA_PAT
        exec npx -y mcp-jira-server
    fi
fi

echo "FATAL: JIRA_PAT not found in Infisical, env, or .env" >&2
exit 1
