#!/usr/bin/env bash
# DEPRECATED: use `python3 scripts/run_agent.py --agent 1 --project PROJECT --command /audit` instead.
# Интервью для Agent 1 (Architect) — аудит ФМ
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

SCOPE=$(gum choose --header "Объем аудита?" \
    "Полный (бизнес + 1С)" \
    "Только бизнес-логика" \
    "Только 1С-специфика" \
    "Экспресс (только Critical)")
save_context "Agent1_Architect" "Объем: ${SCOPE}"
