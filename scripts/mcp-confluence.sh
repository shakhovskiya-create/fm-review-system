#!/usr/bin/env bash
# MCP Confluence server launcher with Infisical support.
# Priority: Infisical (Universal Auth) -> Infisical (user) -> .env file.
# Used by .mcp.json as the command for confluence MCP server.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MI_ENV="$PROJECT_DIR/infra/infisical/.env.machine-identity"

MCP_CMD="$PROJECT_DIR/.venv/bin/mcp-atlassian"
MCP_ARGS=(--confluence-url https://confluence.ekf.su --no-confluence-ssl-verify)

# Priority 1: Infisical Universal Auth (Machine Identity)
if command -v infisical &>/dev/null && [[ -f "$MI_ENV" ]]; then
    # Load Machine Identity credentials
    while IFS='=' read -r key val; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        export "$key=$val"
    done < "$MI_ENV"

    if [[ -n "$INFISICAL_CLIENT_ID" && -n "$INFISICAL_CLIENT_SECRET" ]]; then
        _token=$(INFISICAL_API_URL="${INFISICAL_API_URL}" infisical login \
            --method=universal-auth \
            --client-id="$INFISICAL_CLIENT_ID" \
            --client-secret="$INFISICAL_CLIENT_SECRET" \
            --silent 2>/dev/null | grep -oP 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
        if [[ -n "$_token" ]]; then
            export INFISICAL_TOKEN="$_token"
            exec infisical run --projectId="${INFISICAL_PROJECT_ID}" --env=dev -- "$MCP_CMD" "${MCP_ARGS[@]}"
        fi
    fi
fi

# Priority 2: Infisical user auth
if command -v infisical &>/dev/null && infisical export --format=dotenv-export &>/dev/null 2>&1; then
    exec infisical run -- "$MCP_CMD" "${MCP_ARGS[@]}"
fi

# Priority 3: .env file fallback
exec "$MCP_CMD" "${MCP_ARGS[@]}" --env-file "$PROJECT_DIR/.env"
