#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# CONFLUENCE-RESTORE.SH — Restore Confluence page from local backup
# ═══════════════════════════════════════════════════════════════
# Usage:
#   ./scripts/confluence-restore.sh --page-id 83951683                  # restore latest backup
#   ./scripts/confluence-restore.sh --page-id 83951683 --list           # list available backups
#   ./scripts/confluence-restore.sh --page-id 83951683 --backup FILE    # restore specific backup
#   ./scripts/confluence-restore.sh --page-id 83951683 --dry-run        # show what would be restored
#
# Backups are created by confluence_utils.py before every PUT.
# Stored in: src/.confluence_backups/<page_id>/v<N>_<timestamp>.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/secrets.sh"

# Defaults
PAGE_ID=""
BACKUP_FILE=""
LIST_MODE=false
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

usage() {
    echo "Usage: $0 --page-id ID [--backup FILE] [--list] [--dry-run]"
    echo ""
    echo "Options:"
    echo "  --page-id ID    Confluence page ID (required)"
    echo "  --backup FILE   Specific backup file to restore (default: latest)"
    echo "  --list          List available backups and exit"
    echo "  --dry-run       Show what would be restored without making changes"
}

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --page-id) PAGE_ID="$2"; shift 2 ;;
        --backup) BACKUP_FILE="$2"; shift 2 ;;
        --list) LIST_MODE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

[[ -z "$PAGE_ID" ]] && { echo -e "${RED}ERROR: --page-id is required${NC}"; usage; exit 1; }

BACKUP_DIR="${PROJECT_DIR}/src/.confluence_backups/${PAGE_ID}"

if [[ ! -d "$BACKUP_DIR" ]]; then
    echo -e "${RED}No backups found for page ${PAGE_ID}${NC}"
    echo "  Expected directory: ${BACKUP_DIR}"
    exit 1
fi

# List mode
if $LIST_MODE; then
    echo -e "${BOLD}Available backups for page ${PAGE_ID}:${NC}"
    echo ""
    # shellcheck disable=SC2012
    ls -lt "$BACKUP_DIR"/*.json 2>/dev/null | while read -r line; do
        file=$(echo "$line" | awk '{print $NF}')
        basename=$(basename "$file")
        size=$(echo "$line" | awk '{print $5}')
        date=$(echo "$line" | awk '{print $6, $7, $8}')
        echo -e "  ${GREEN}${basename}${NC}  (${size} bytes, ${date})"
    done
    count=$(find "$BACKUP_DIR" -name "*.json" 2>/dev/null | wc -l)
    echo ""
    echo -e "  Total: ${BOLD}${count}${NC} backup(s)"
    exit 0
fi

# Resolve backup file
if [[ -n "$BACKUP_FILE" ]]; then
    # If relative path, look in backup dir
    if [[ ! -f "$BACKUP_FILE" && -f "$BACKUP_DIR/$BACKUP_FILE" ]]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    fi
    if [[ ! -f "$BACKUP_FILE" ]]; then
        echo -e "${RED}Backup file not found: ${BACKUP_FILE}${NC}"
        exit 1
    fi
else
    # Use latest backup
    BACKUP_FILE=$(find "$BACKUP_DIR" -name "*.json" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
    if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
        echo -e "${RED}No backup files found in ${BACKUP_DIR}${NC}"
        exit 1
    fi
fi

echo -e "${BOLD}═══════════════════════════════════════════${NC}"
echo -e "  ${BOLD}Confluence Page Restore${NC}"
echo -e "${BOLD}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  Page ID:     ${PAGE_ID}"
echo -e "  Backup file: $(basename "$BACKUP_FILE")"

# Extract backup info
BACKUP_VERSION=$(python3 -c "
import json, sys
with open('${BACKUP_FILE}') as f:
    data = json.load(f)
v = data.get('version', {}).get('number', '?')
t = data.get('title', 'unknown')
print(f'{v}|{t}')
" 2>/dev/null || echo "?|unknown")

BACKUP_VER=$(echo "$BACKUP_VERSION" | cut -d'|' -f1)
BACKUP_TITLE=$(echo "$BACKUP_VERSION" | cut -d'|' -f2-)

echo -e "  Version:     ${BACKUP_VER}"
echo -e "  Title:       ${BACKUP_TITLE}"
echo ""

if $DRY_RUN; then
    echo -e "${YELLOW}DRY RUN — no changes will be made${NC}"
    echo ""
    echo -e "Would restore page ${PAGE_ID} to version ${BACKUP_VER}"
    echo -e "Backup body size: $(python3 -c "
import json
with open('${BACKUP_FILE}') as f:
    data = json.load(f)
print(len(data.get('body', {}).get('storage', {}).get('value', '')))
" 2>/dev/null || echo '?') characters"
    exit 0
fi

# Load secrets for Confluence access
echo -e "  Loading secrets..."
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/load-secrets.sh" 2>/dev/null || true

CONFLUENCE_URL="${CONFLUENCE_URL:-https://confluence.ekf.su}"
CONFLUENCE_TOKEN="${CONFLUENCE_TOKEN:-}"

if [[ -z "$CONFLUENCE_TOKEN" ]]; then
    echo -e "${RED}ERROR: CONFLUENCE_TOKEN not available${NC}"
    echo "  Run: source scripts/load-secrets.sh"
    exit 1
fi

# Confirm
echo -e "${YELLOW}${BOLD}WARNING: This will overwrite the current page content!${NC}"
echo -ne "  Continue? [y/N] "
read -r confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "  Aborted."
    exit 0
fi

# Execute restore via Python
echo ""
echo -e "  Restoring..."
if PYTHONPATH="${PROJECT_DIR}/src" python3 -c "
import sys, json
from fm_review.confluence_utils import ConfluenceClient

client = ConfluenceClient('${CONFLUENCE_URL}', '${CONFLUENCE_TOKEN}', '${PAGE_ID}')
from pathlib import Path
result = client.rollback(backup_path=Path('${BACKUP_FILE}'))
print(f'  Restored to version: {result.get(\"version\", {}).get(\"number\", \"?\")}')
" 2>&1; then
    echo ""
    echo -e "${GREEN}${BOLD}  RESTORE COMPLETE${NC}"
else
    echo ""
    echo -e "${RED}${BOLD}  RESTORE FAILED${NC}"
    exit 1
fi
