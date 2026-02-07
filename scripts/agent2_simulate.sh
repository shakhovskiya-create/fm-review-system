#!/bin/bash
# Интервью для Agent 2 (Role Simulator)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

FOCUS=$(gum choose --header "Главная роль для симуляции?" \
    "Менеджер по продажам" \
    "Согласующий" \
    "Все роли по очереди" \
    "Другая")
save_context "Agent2_Simulator" "Фокус: ${FOCUS}"
