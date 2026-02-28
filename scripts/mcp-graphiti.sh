#!/usr/bin/env bash
# mcp-graphiti.sh — Graphiti MCP server для fm-review-system
# Общий граф с cio-assistant (group_id=ekf-shared)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GRAPHITI_DIR="/home/dev/projects/claude-agents/infra/graphiti/mcp_server"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

# Определяем NEO4J-параметры
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-graphiti-dev-2026}"

# Общий group_id — cio-assistant и fm-review-system видят одни данные
GROUP_ID="${GRAPHITI_GROUP_ID:-ekf-shared}"

# Priority 1: Infisical Universal Auth (Machine Identity)
if _infisical_universal_auth "$PROJECT_DIR"; then
    cd "$GRAPHITI_DIR"
    exec infisical run --projectId="${INFISICAL_PROJECT_ID}" --env=dev -- \
        uv run python main.py \
            --transport stdio \
            --llm-provider openai \
            --model gpt-5.2 \
            --embedder-provider openai \
            --database-provider neo4j \
            --group-id "$GROUP_ID"
fi

# Priority 2: Infisical user auth
if command -v infisical &>/dev/null && infisical export --format=dotenv-export &>/dev/null 2>&1; then
    cd "$GRAPHITI_DIR"
    exec infisical run -- \
        uv run python main.py \
            --transport stdio \
            --llm-provider openai \
            --model gpt-5.2 \
            --embedder-provider openai \
            --database-provider neo4j \
            --group-id "$GROUP_ID"
fi

# Priority 3: .env fallback
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
    if [[ -n "${OPENAI_API_KEY:-}" ]]; then
        cd "$GRAPHITI_DIR"
        exec uv run python main.py \
            --transport stdio \
            --llm-provider openai \
            --model gpt-5.2 \
            --embedder-provider openai \
            --database-provider neo4j \
            --group-id "$GROUP_ID"
    fi
fi

echo "[mcp-graphiti] ERROR: No OPENAI_API_KEY available (Infisical down, no .env)" >&2
exit 1
