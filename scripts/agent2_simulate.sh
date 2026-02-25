#!/usr/bin/env bash
# DEPRECATED: use `python3 scripts/run_agent.py --agent 2 --project PROJECT --command /simulate-all` instead.
# Интервью для Agent 2 (Role Simulator)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

FOCUS=$(gum choose --header "Главная роль для симуляции?" \
    "Менеджер по продажам" \
    "Согласующий" \
    "Все роли по очереди" \
    "Другая")
save_context "Agent2_Simulator" "Фокус: ${FOCUS}"
