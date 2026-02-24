#!/usr/bin/env bash
# MCP Langfuse server launcher with Infisical support.
# Priority: Infisical (Universal Auth) -> env vars -> .env file.
# Used by .mcp.json as the command for Langfuse MCP server.
#
# Requires: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
# Activate in .claude/settings.json enabledMcpjsonServers when Langfuse is running.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

MCP_CMD="npx"
MCP_ARGS=(-y langfuse-observability-mcp-server)

# Priority 1: Infisical Universal Auth (Machine Identity)
if _infisical_universal_auth "$PROJECT_DIR"; then
    _dotenv=$(infisical export --projectId="${INFISICAL_PROJECT_ID}" --env=dev --format=dotenv 2>/dev/null) || true
    LANGFUSE_PUBLIC_KEY=$(echo "$_dotenv" | grep '^LANGFUSE_PUBLIC_KEY=' | cut -d= -f2-) || true
    LANGFUSE_SECRET_KEY=$(echo "$_dotenv" | grep '^LANGFUSE_SECRET_KEY=' | cut -d= -f2-) || true
    LANGFUSE_BASE_URL=$(echo "$_dotenv" | grep '^LANGFUSE_BASE_URL=' | cut -d= -f2-) || true
    unset _dotenv
fi

# Priority 2: env vars already set — nothing to do

# Priority 3: .env file fallback
if [[ -z "${LANGFUSE_PUBLIC_KEY:-}" && -f "$PROJECT_DIR/.env" ]]; then
    LANGFUSE_PUBLIC_KEY=$(grep '^LANGFUSE_PUBLIC_KEY=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2-) || true
    LANGFUSE_SECRET_KEY=$(grep '^LANGFUSE_SECRET_KEY=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2-) || true
    LANGFUSE_BASE_URL=$(grep '^LANGFUSE_BASE_URL=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2-) || true
fi

export LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
export LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"
export LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-http://localhost:3000}"

exec "$MCP_CMD" "${MCP_ARGS[@]}"
