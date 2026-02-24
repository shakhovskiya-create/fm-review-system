#!/usr/bin/env bash
# MCP GitHub server launcher with Infisical support.
# Priority: Infisical (Universal Auth) -> Infisical (user) -> .env file.
# Used by .mcp.json as the command for GitHub MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

MCP_CMD="npx"
MCP_ARGS=(-y @modelcontextprotocol/server-github)

# Priority 1: Infisical Universal Auth (Machine Identity)
if _infisical_universal_auth "$PROJECT_DIR"; then
    GITHUB_PERSONAL_ACCESS_TOKEN=$(
        infisical export --projectId="${INFISICAL_PROJECT_ID}" --env=dev --format=dotenv 2>/dev/null \
        | grep '^GITHUB_TOKEN=' | cut -d= -f2-
    ) || true
fi

# Priority 2: env var
if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
    GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN:-}"
fi

# Priority 3: .env file fallback
if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" && -f "$PROJECT_DIR/.env" ]]; then
    GITHUB_PERSONAL_ACCESS_TOKEN=$(grep '^GITHUB_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2-) || true
fi

export GITHUB_PERSONAL_ACCESS_TOKEN
exec "$MCP_CMD" "${MCP_ARGS[@]}"
