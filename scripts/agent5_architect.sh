#!/bin/bash
# Интервью для Agent 5 (Tech Architect)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

OUTPUT=$(gum choose --header "Что генерировать?" \
    "Архитектура + ТЗ + оценка (/full)" \
    "Только архитектура" \
    "Только оценка трудоемкости" \
    "ТЗ на разработку")
save_context "Agent5_TechArch" "Выход: ${OUTPUT}"
