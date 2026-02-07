#!/bin/bash
# Интервью для Agent 1 (Architect) — аудит ФМ
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

SCOPE=$(gum choose --header "Объем аудита?" \
    "Полный (бизнес + 1С)" \
    "Только бизнес-логика" \
    "Только 1С-специфика" \
    "Экспресс (только Critical)")
save_context "Agent1_Architect" "Объем: ${SCOPE}"
