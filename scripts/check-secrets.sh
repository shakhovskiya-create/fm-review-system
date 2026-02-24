#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# CHECK-SECRETS.SH — Verify all required secrets are available
# ═══════════════════════════════════════════════════════════════
# Usage: ./scripts/check-secrets.sh [--verbose]
#
# Checks secrets availability in priority order:
#   1. Infisical (Universal Auth or user session)
#   2. System keyring (secret-tool / security)
#   3. .env file
#
# Exit codes: 0=all found, 1=missing required, 2=missing optional

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

# Required secrets (pipeline won't work without these)
REQUIRED_KEYS=(ANTHROPIC_API_KEY)

# Important secrets (specific features need these)
IMPORTANT_KEYS=(CONFLUENCE_TOKEN)

# Optional secrets (nice to have)
OPTIONAL_KEYS=(LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY GITHUB_TOKEN MIRO_ACCESS_TOKEN)

VERBOSE=false
[[ "${1:-}" == "--verbose" || "${1:-}" == "-v" ]] && VERBOSE=true

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

found=0
missing_required=0
missing_important=0
missing_optional=0
source_info=""

# --- Detect secret source ---
detect_source() {
    local key="$1"

    # Check environment (already loaded)
    if [[ -n "${!key:-}" ]]; then
        echo "env"
        return 0
    fi

    # Check Infisical
    if command -v infisical &>/dev/null; then
        local val
        val=$(infisical secrets get "$key" --plain 2>/dev/null) || true
        if [[ -n "$val" ]]; then
            echo "infisical"
            return 0
        fi
    fi

    # Check keyring
    if command -v secret-tool &>/dev/null; then
        local val
        val=$(secret-tool lookup service fm-review key "$key" 2>/dev/null) || true
        if [[ -n "$val" ]]; then
            echo "keyring"
            return 0
        fi
    elif command -v security &>/dev/null; then
        local val
        val=$(security find-generic-password -s fm-review -a "$key" -w 2>/dev/null) || true
        if [[ -n "$val" ]]; then
            echo "keychain"
            return 0
        fi
    fi

    # Check .env file
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        if grep -qE "^${key}=" "$PROJECT_DIR/.env" 2>/dev/null; then
            echo "dotenv"
            return 0
        fi
    fi

    echo "missing"
    return 1
}

# --- Load secrets first (so env check works) ---
# shellcheck disable=SC1091
source "$SCRIPT_DIR/load-secrets.sh" 2>/dev/null || true

echo -e "${BOLD}═══════════════════════════════════════════${NC}"
echo -e "  ${BOLD}Secret Verification${NC}"
echo -e "${BOLD}═══════════════════════════════════════════${NC}"

# --- Check required ---
echo -e "\n${BOLD}Required:${NC}"
for key in "${REQUIRED_KEYS[@]}"; do
    src=$(detect_source "$key") || true
    if [[ "$src" != "missing" ]]; then
        echo -e "  ${GREEN}OK${NC}  $key ($src)"
        ((found++)) || true
    else
        echo -e "  ${RED}XX${NC}  $key — ${RED}MISSING (pipeline will fail)${NC}"
        ((missing_required++)) || true
    fi
done

# --- Check important ---
echo -e "\n${BOLD}Important:${NC}"
for key in "${IMPORTANT_KEYS[@]}"; do
    src=$(detect_source "$key") || true
    if [[ "$src" != "missing" ]]; then
        echo -e "  ${GREEN}OK${NC}  $key ($src)"
        ((found++)) || true
    else
        echo -e "  ${YELLOW}!!${NC}  $key — ${YELLOW}missing (Confluence features disabled)${NC}"
        ((missing_important++)) || true
    fi
done

# --- Check optional ---
echo -e "\n${BOLD}Optional:${NC}"
for key in "${OPTIONAL_KEYS[@]}"; do
    src=$(detect_source "$key") || true
    if [[ "$src" != "missing" ]]; then
        echo -e "  ${GREEN}OK${NC}  $key ($src)"
        ((found++)) || true
    else
        echo -e "  ${CYAN}--${NC}  $key — not configured"
        ((missing_optional++)) || true
    fi
done

# --- Infrastructure check ---
echo -e "\n${BOLD}Infrastructure:${NC}"

# Infisical CLI
if command -v infisical &>/dev/null; then
    ver=$(infisical --version 2>/dev/null | head -1) || ver="unknown"
    echo -e "  ${GREEN}OK${NC}  Infisical CLI ($ver)"
else
    echo -e "  ${CYAN}--${NC}  Infisical CLI not installed"
fi

# Infisical self-hosted
if [[ -f "$PROJECT_DIR/infra/infisical/docker-compose.yml" ]]; then
    echo -e "  ${GREEN}OK${NC}  Infisical self-hosted config present"
else
    echo -e "  ${CYAN}--${NC}  Infisical self-hosted not configured"
fi

# Machine Identity
if [[ -f "$PROJECT_DIR/infra/infisical/.env.machine-identity" ]]; then
    echo -e "  ${GREEN}OK${NC}  Machine Identity configured"
else
    echo -e "  ${CYAN}--${NC}  Machine Identity not configured (CI/CD)"
fi

# .env file permissions
if [[ -f "$PROJECT_DIR/.env" ]]; then
    perms=$(stat -c '%a' "$PROJECT_DIR/.env" 2>/dev/null || stat -f '%Lp' "$PROJECT_DIR/.env" 2>/dev/null || echo "unknown")
    if [[ "$perms" == "600" ]]; then
        echo -e "  ${GREEN}OK${NC}  .env permissions: $perms"
    else
        echo -e "  ${YELLOW}!!${NC}  .env permissions: $perms (should be 600)"
    fi
fi

# --- Summary ---
total=$((found + missing_required + missing_important + missing_optional))
echo -e "\n${BOLD}═══════════════════════════════════════════${NC}"
echo -e "  Found: ${GREEN}${found}${NC}/${total}  Missing required: ${RED}${missing_required}${NC}  Missing important: ${YELLOW}${missing_important}${NC}"

if [[ $missing_required -gt 0 ]]; then
    echo -e "  ${RED}${BOLD}FAIL: Missing required secrets${NC}"
    exit 1
elif [[ $missing_important -gt 0 ]]; then
    echo -e "  ${YELLOW}${BOLD}WARN: Some features will be limited${NC}"
    exit 2
else
    echo -e "  ${GREEN}${BOLD}ALL SECRETS VERIFIED${NC}"
    exit 0
fi
