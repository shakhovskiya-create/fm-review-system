#!/usr/bin/env bash
# DEPRECATED: use `python3 scripts/run_agent.py --agent 3 --project PROJECT --command /respond` instead.
# Интервью для Agent 3 (Defender)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

SOURCE=$(gum choose --header "Откуда замечания?" \
    "Заказчик/бизнес" \
    "Результаты Agent 1 (аудит)" \
    "Результаты Agent 2 (UX)" \
    "Все выше")
save_context "Agent3_Defender" "Источник замечаний: ${SOURCE}"
