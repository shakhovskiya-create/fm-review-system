#!/bin/bash

# AGENT_6 PRESENTER — Интерактивный лаунчер
# Запуск: ./agent6_present.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_6: PRESENTER — Подготовка материалов${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Аудитория
AUDIENCE=$(gum choose --header "? Для кого готовим материалы?" \
    "1. Заказчик (бизнес-пользователи) ⭐" \
    "2. Руководство (директора, CxO)" \
    "3. Разработчики (1С-команда)" \
    "4. Все аудитории сразу" \
    "5. Другое")

[[ "$AUDIENCE" == "5. Другое" ]] && AUDIENCE=$(gum input --placeholder "Укажите аудиторию...")
echo -e "${GREEN}✓${NC} Аудитория: ${AUDIENCE}"

# ШАГ 2: Формат
FORMAT=$(gum choose --header "? Какой формат нужен?" \
    "1. Краткое резюме (1 страница) ⭐" \
    "2. Полная презентация (PPTX)" \
    "3. Статус-отчет (что сделано / что осталось)" \
    "4. Дорожная карта внедрения" \
    "5. Changelog для стейкхолдеров")

echo -e "${GREEN}✓${NC} Формат: ${FORMAT}"

# ШАГ 3: Фокус
FOCUS=$(gum choose --header "? На чём сделать акцент?" \
    "1. Бизнес-ценность (проблема → решение → ROI)" \
    "2. Технические детали (архитектура, интеграции)" \
    "3. Риски и митигация" \
    "4. Прогресс проекта" \
    "5. Всё сбалансированно ⭐")

echo -e "${GREEN}✓${NC} Фокус: ${FOCUS}"

# Формируем контекст
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT=$(select_project)
FM_PATH=$(get_latest_fm "$PROJECT")

CONTEXT="ПРОЕКТ: ${PROJECT}
ФМ: $(basename "$FM_PATH")
АУДИТОРИЯ: ${AUDIENCE}
ФОРМАТ: ${FORMAT}
ФОКУС: ${FOCUS}"

save_context "AGENT_6_PRESENTER" \
    "Проект: ${PROJECT}" \
    "ФМ: $(basename "$FM_PATH")" \
    "Аудитория: ${AUDIENCE}" \
    "Формат: ${FORMAT}" \
    "Фокус: ${FOCUS}"

echo ""
echo -e "${CYAN}───────────────────────────────────────────${NC}"
echo -e "${CYAN}  Контекст собран. Запускаю Agent 6...${NC}"
echo -e "${CYAN}───────────────────────────────────────────${NC}"
echo ""

launch_claude_code \
    "${ROOT_DIR}/AGENT_6_PRESENTER.md" \
    "/present" \
    "${CONTEXT}"
