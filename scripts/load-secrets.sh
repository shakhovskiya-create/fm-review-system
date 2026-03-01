#!/usr/bin/env bash
# Load secrets into environment variables.
# Priority: Infisical (Universal Auth) -> system keyring -> .env file
# Usage: source scripts/load-secrets.sh [--project PROJECT_NAME]
#
# Projects:
#   (default)              — fm-review-system secrets (root path /)
#   --project profitability-service — profitability-service secrets (/profitability-service)
#
# Setup:
#   1. Infisical (recommended): Machine Identity credentials in infra/infisical/.env.machine-identity
#   2. Keyring (Linux): secret-tool store --label="fm-review CONFLUENCE_TOKEN" service fm-review key CONFLUENCE_TOKEN <<< "your_token"
#   3. Keyring (macOS): security add-generic-password -s "fm-review" -a "CONFLUENCE_TOKEN" -w "your_token"
#   4. .env fallback: copy .env.example to .env and fill values

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"
SERVICE="fm-review"

# --- Parse --project argument ---
_INFISICAL_PATH="/"
_PROJECT_NAME="fm-review-system"
_prev_arg=""
for _arg in "$@"; do
    if [[ "$_prev_arg" == "--project" ]]; then
        _PROJECT_NAME="$_arg"
        _INFISICAL_PATH="/${_arg}"
    fi
    _prev_arg="$_arg"
done
unset _arg _prev_arg

KEYS=(CONFLUENCE_TOKEN LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY GITHUB_TOKEN MIRO_ACCESS_TOKEN ANTHROPIC_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID)

# --- Priority 1: Infisical (Universal Auth) ---
if _infisical_universal_auth "$PROJECT_DIR"; then
    _loaded=0
    while IFS= read -r _line; do
        [[ "$_line" =~ ^export\ ([A-Za-z_][A-Za-z0-9_]*)=(.*) ]] && {
            _val="${BASH_REMATCH[2]}"
            # Strip wrapping quotes ('value' or "value" → value)
            _val="${_val#\'}" ; _val="${_val%\'}"
            _val="${_val#\"}" ; _val="${_val%\"}"
            export "${BASH_REMATCH[1]}=${_val}"
            ((_loaded++)) || true
        }
    done < <(INFISICAL_TOKEN="$INFISICAL_TOKEN" \
        infisical export --format=dotenv-export \
        --projectId="${INFISICAL_PROJECT_ID}" --env=dev \
        --path="${_INFISICAL_PATH}" \
        --domain="${INFISICAL_API_URL:-https://app.infisical.com/api}" 2>/dev/null)
    if [[ $_loaded -gt 0 ]]; then
        echo "[load-secrets] Loaded $_loaded secrets from Infisical (${_PROJECT_NAME}, path=${_INFISICAL_PATH})"
        return 0 2>/dev/null || exit 0
    fi
fi

if command -v infisical &>/dev/null; then
    # Fallback: try user-based Infisical login (if logged in previously)
    _loaded=0
    while IFS= read -r _line; do
        [[ "$_line" =~ ^export\ ([A-Za-z_][A-Za-z0-9_]*)=(.*) ]] && {
            export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
            ((_loaded++)) || true
        }
    done < <(infisical export --format=dotenv-export 2>/dev/null)
    if [[ $_loaded -gt 0 ]]; then
        echo "[load-secrets] Loaded $_loaded secrets from Infisical (user auth)"
        return 0 2>/dev/null || exit 0
    fi
fi

# --- Priority 2: System keyring ---
_lookup() {
    if command -v secret-tool &>/dev/null; then
        secret-tool lookup service "$SERVICE" key "$1" 2>/dev/null
    elif command -v security &>/dev/null; then
        security find-generic-password -s "$SERVICE" -a "$1" -w 2>/dev/null
    else
        return 1
    fi
}

loaded=0
for key in "${KEYS[@]}"; do
    val=$(_lookup "$key")
    if [[ -n "$val" ]]; then
        export "$key=$val"
        ((loaded++)) || true
    fi
done

if [[ $loaded -gt 0 ]]; then
    echo "[load-secrets] Loaded $loaded secrets from keyring"
    return 0 2>/dev/null || exit 0
fi

# --- Priority 3: .env file ---
echo "[load-secrets] No secrets found in Infisical/keyring; falling back to .env file"
if [[ -f "${BASH_SOURCE[0]%/*}/../.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${BASH_SOURCE[0]%/*}/../.env"
    set +a
fi
