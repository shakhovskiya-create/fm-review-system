#!/usr/bin/env bash
# Cron wrapper for Telegram cost report.
# Loads secrets from Infisical, runs tg-report.py.
# Usage: cron-tg-report.sh [--yesterday|--today|--days N|--month YYYY-MM]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/load-secrets.sh"

exec "${PROJECT_DIR}/.venv/bin/python3" "${SCRIPT_DIR}/tg-report.py" "$@"
