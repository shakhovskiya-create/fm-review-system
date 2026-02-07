#!/bin/bash
# Интервью для Agent 0 (Creator) — создание новой ФМ
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

PRIORITY=$(gum choose --header "Что в приоритете для новой ФМ?" \
    "Скорость операций" \
    "Баланс скорости и контроля" \
    "Максимальный контроль" \
    "Другое")
SOURCE=$(gum choose --header "Откуда берем требования?" \
    "Интервью с заказчиком" \
    "Готовое ТЗ/описание" \
    "Аналогичная ФМ" \
    "С нуля по шаблону")
save_context "Agent0_Creator" "Приоритет: ${PRIORITY}" "Источник: ${SOURCE}"
