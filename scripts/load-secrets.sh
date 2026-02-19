#!/usr/bin/env bash
# Load secrets from system keyring into environment variables.
# Usage: source scripts/load-secrets.sh
#
# Setup (one-time):
#   # Linux (secret-tool / GNOME Keyring):
#   secret-tool store --label="fm-review CONFLUENCE_TOKEN" service fm-review key CONFLUENCE_TOKEN <<< "your_token"
#   secret-tool store --label="fm-review LANGFUSE_SECRET_KEY" service fm-review key LANGFUSE_SECRET_KEY <<< "your_key"
#
#   # macOS Keychain:
#   security add-generic-password -s "fm-review" -a "CONFLUENCE_TOKEN" -w "your_token"

SERVICE="fm-review"
KEYS=(CONFLUENCE_TOKEN CONFLUENCE_PERSONAL_TOKEN LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY GITHUB_TOKEN MIRO_ACCESS_TOKEN)

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
        ((loaded++))
    fi
done

if [[ $loaded -gt 0 ]]; then
    echo "[load-secrets] Loaded $loaded secrets from keyring"
else
    echo "[load-secrets] No secrets found in keyring; falling back to .env file"
    if [[ -f "${BASH_SOURCE[0]%/*}/../.env" ]]; then
        set -a
        # shellcheck disable=SC1091
        source "${BASH_SOURCE[0]%/*}/../.env"
        set +a
    fi
fi
