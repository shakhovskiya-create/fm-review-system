#!/bin/bash
# Интервью для Agent 4 (QA Tester)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

SCOPE=$(gum choose --header "Объем тестов?" \
    "Все модули + манипуляции" \
    "Только по findings Agent 1/2" \
    "Плюс тесты на скорость" \
    "Полное покрытие")
save_context "Agent4_QA" "Объем: ${SCOPE}"
