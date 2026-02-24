#!/usr/bin/env bash
# scripts/lib/secrets.sh
# Shared Infisical authentication utilities (H-A5: DRY).
# Source this file before using Infisical Universal Auth in scripts.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/secrets.sh"
#   _infisical_universal_auth "$PROJECT_DIR" && echo "Authenticated"

# _infisical_universal_auth [project_dir]
#
# Authenticates with Infisical using Machine Identity (Universal Auth).
# Reads credentials from infra/infisical/.env.machine-identity.
# Never uses eval — reads line by line.
#
# On success: exports INFISICAL_TOKEN
# Returns: 0 on success, 1 on failure (no CLI / no creds file / bad token)
_infisical_universal_auth() {
    local project_dir="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
    local mi_env="${project_dir}/infra/infisical/.env.machine-identity"

    command -v infisical &>/dev/null || return 1
    [[ -f "$mi_env" ]] || return 1

    # Load Machine Identity credentials (never eval — key=value line by line)
    while IFS='=' read -r key val; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        export "$key=$val"
    done < "$mi_env"

    [[ -n "${INFISICAL_CLIENT_ID:-}" && -n "${INFISICAL_CLIENT_SECRET:-}" ]] || return 1

    local _token
    _token=$(INFISICAL_API_URL="${INFISICAL_API_URL:-}" \
        INFISICAL_CLIENT_ID="${INFISICAL_CLIENT_ID}" \
        INFISICAL_CLIENT_SECRET="${INFISICAL_CLIENT_SECRET}" \
        infisical login \
            --method=universal-auth \
            --silent 2>/dev/null \
        | grep -oP 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')

    [[ -n "$_token" ]] || return 1
    export INFISICAL_TOKEN="$_token"
    return 0
}
