#!/usr/bin/env bash
# MCP Confluence server launcher with Infisical support.
# Priority: Infisical (Universal Auth) -> Infisical (user) -> .env file.
# Used by .mcp.json as the command for confluence MCP server.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

MCP_CMD="$PROJECT_DIR/.venv/bin/mcp-atlassian"
MCP_ARGS=(--confluence-url https://confluence.ekf.su)

# Priority 1: Infisical Universal Auth (Machine Identity)
if _infisical_universal_auth "$PROJECT_DIR"; then
    exec infisical run --projectId="${INFISICAL_PROJECT_ID}" --env=dev -- "$MCP_CMD" "${MCP_ARGS[@]}"
fi

# Priority 2: Infisical user auth
if command -v infisical &>/dev/null && infisical export --format=dotenv-export &>/dev/null 2>&1; then
    exec infisical run -- "$MCP_CMD" "${MCP_ARGS[@]}"
fi

# Priority 3: .env file fallback (if exists)
if [[ -f "$PROJECT_DIR/.env" ]]; then
    exec "$MCP_CMD" "${MCP_ARGS[@]}" --env-file "$PROJECT_DIR/.env"
fi

echo "[mcp-confluence] ERROR: No secrets source available (Infisical down, no .env)" >&2
exit 1
