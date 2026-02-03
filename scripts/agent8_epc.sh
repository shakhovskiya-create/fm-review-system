#!/bin/bash

# AGENT_8 EPC DESIGNER — Интерактивный лаунчер создания ePC в Miro
# Запуск: ./agent8_epc.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_8: EPC DESIGNER — ePC-диаграммы в Miro${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Выбор проекта
PROJECTS=$(ls -d PROJECT_*/ 2>/dev/null || echo "")
if [ -z "$PROJECTS" ]; then
    echo -e "${RED}Нет проектов.${NC}"
    exit 1
fi

PROJECT=$(gum choose --header "? Выберите проект:" $PROJECTS)
echo -e "${GREEN}✓${NC} Проект: ${PROJECT}"

# ШАГ 2: Тип диаграммы
echo ""
TYPE=$(gum choose --header "? Тип ePC-диаграммы:" \
    "1. Полная ePC (события + функции + роли + системы) ⭐" \
    "2. Упрощенная (только события и функции)" \
    "3. С swimlanes (по ролям)" \
    "4. Фрагмент процесса (конкретный раздел ФМ)" \
    "5. Другое")

[[ "$TYPE" == "5. Другое" ]] && TYPE=$(gum input --placeholder "Опишите тип...")
echo -e "${GREEN}✓${NC} Тип: ${TYPE}"

# ШАГ 3: Miro доска
echo ""
BOARD=$(gum choose --header "? Целевая доска Miro:" \
    "1. Создать новую доску для проекта ⭐" \
    "2. Добавить на существующую доску" \
    "3. Другое")

if [ "$BOARD" == "2. Добавить на существующую доску" ]; then
    BOARD_URL=$(gum input --placeholder "URL доски Miro...")
    echo -e "${GREEN}✓${NC} Доска: ${BOARD_URL}"
else
    echo -e "${GREEN}✓${NC} Доска: ${BOARD}"
fi

# ШАГ 4: Источник данных
echo ""
SOURCE=$(gum choose --header "? Источник описания процесса:" \
    "1. .docx файл из FM_DOCUMENTS/ ⭐" \
    "2. Notion-страница (результат Agent 7)" \
    "3. Ручное описание процесса" \
    "4. Другое")

echo -e "${GREEN}✓${NC} Источник: ${SOURCE}"

# ШАГ 5: Подтверждение
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Проект:    ${GREEN}${PROJECT}${NC}"
echo -e "  Тип:       ${GREEN}${TYPE}${NC}"
echo -e "  Доска:     ${GREEN}${BOARD}${NC}"
echo -e "  Источник:  ${GREEN}${SOURCE}${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

gum confirm "Создать ePC-диаграмму?" || exit 0

# ШАГ 6: Создание директории результатов
RESULT_DIR="${PROJECT}AGENT_8_EPC_DESIGNER"
mkdir -p "$RESULT_DIR"

# ШАГ 7: Запуск Claude Code
echo ""
echo -e "${CYAN}Запускаю Claude Code с AGENT_8_EPC_DESIGNER...${NC}"
echo ""

PROMPT="Я Agent 8 (EPC Designer). Контекст:
- Проект: ${PROJECT}
- Тип диаграммы: ${TYPE}
- Доска Miro: ${BOARD}
- Источник: ${SOURCE}
- Результаты в: ${RESULT_DIR}

Выполняю /design согласно AGENT_8_EPC_DESIGNER.md.
Стандарты ePC, цвета, нотация - все в агенте."

claude --chat "$PROMPT"
