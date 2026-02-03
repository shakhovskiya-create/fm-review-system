#!/bin/bash

# AGENT_7 MIGRATOR — Интерактивный лаунчер миграции Word → Notion
# Запуск: ./agent7_migrate.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_7: MIGRATOR — Миграция Word → Notion${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Выбор проекта
echo -e "${CYAN}Доступные проекты:${NC}"
PROJECTS=$(ls -d PROJECT_*/ 2>/dev/null || echo "")
if [ -z "$PROJECTS" ]; then
    echo -e "${RED}Нет проектов. Сначала создайте проект через new_project.sh${NC}"
    exit 1
fi

PROJECT=$(gum choose --header "? Выберите проект для миграции:" $PROJECTS)
echo -e "${GREEN}✓${NC} Проект: ${PROJECT}"

# ШАГ 2: Выбор .docx файла
echo ""
DOCS=$(ls ${PROJECT}FM_DOCUMENTS/*.docx 2>/dev/null || echo "")
if [ -z "$DOCS" ]; then
    echo -e "${RED}Нет .docx файлов в ${PROJECT}FM_DOCUMENTS/${NC}"
    exit 1
fi

DOC=$(gum choose --header "? Выберите .docx файл:" $DOCS)
echo -e "${GREEN}✓${NC} Файл: ${DOC}"

# ШАГ 3: Режим миграции
echo ""
MODE=$(gum choose --header "? Режим миграции:" \
    "1. Полная миграция (все секции + требования + глоссарий + риски) ⭐" \
    "2. Только структура (секции и заголовки)" \
    "3. Только требования (извлечь и создать БД)" \
    "4. Только глоссарий и риски" \
    "5. Валидация (проверить существующую миграцию)" \
    "6. Другое")

[[ "$MODE" == "6. Другое" ]] && MODE=$(gum input --placeholder "Опишите режим...")
echo -e "${GREEN}✓${NC} Режим: ${MODE}"

# ШАГ 4: Notion workspace
echo ""
WORKSPACE=$(gum choose --header "? Целевое пространство Notion:" \
    "1. EKF — Функциональные модели ⭐" \
    "2. Создать новое пространство" \
    "3. Другое")

[[ "$WORKSPACE" == "3. Другое" ]] && WORKSPACE=$(gum input --placeholder "ID пространства...")
echo -e "${GREEN}✓${NC} Notion: ${WORKSPACE}"

# ШАГ 5: Подтверждение
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Проект:  ${GREEN}${PROJECT}${NC}"
echo -e "  Файл:    ${GREEN}${DOC}${NC}"
echo -e "  Режим:   ${GREEN}${MODE}${NC}"
echo -e "  Notion:  ${GREEN}${WORKSPACE}${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

gum confirm "Начать миграцию?" || exit 0

# ШАГ 6: Создание директории результатов
RESULT_DIR="${PROJECT}AGENT_7_MIGRATOR"
mkdir -p "$RESULT_DIR"

# ШАГ 7: Запуск Claude Code с контекстом
echo ""
echo -e "${CYAN}Запускаю Claude Code с AGENT_7_MIGRATOR...${NC}"
echo ""

PROMPT="Я Agent 7 (Migrator). Контекст:
- Проект: ${PROJECT}
- Файл: ${DOC}
- Режим: ${MODE}
- Notion workspace: ${WORKSPACE}
- Результаты в: ${RESULT_DIR}

Выполняю /migrate согласно AGENT_7_MIGRATOR.md.
Схемы БД: schemas/notion-databases.md
Шаблоны: templates/"

claude --chat "$PROMPT"
