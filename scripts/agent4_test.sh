#!/usr/bin/env bash
# DEPRECATED: use `python3 scripts/run_agent.py --agent 4 --project PROJECT --command /generate-all` instead.
# Интервью для Agent 4 (QA Tester)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

SCOPE=$(gum choose --header "Объем тестов?" \
    "Все модули + манипуляции" \
    "Только по findings Agent 1/2" \
    "Плюс тесты на скорость" \
    "Полное покрытие")
save_context "Agent4_QA" "Объем: ${SCOPE}"
