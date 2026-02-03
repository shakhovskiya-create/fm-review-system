#!/bin/bash

# AGENT_6 PRESENTER — Интерактивный лаунчер для презентаций и отчетов
# Запуск: ./agent6_present.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_6: PRESENTER — Презентации и отчеты${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Выбор проекта
echo -e "${CYAN}Доступные проекты:${NC}"
PROJECTS=$(ls -d PROJECT_*/ 2>/dev/null || echo "")
if [ -z "$PROJECTS" ]; then
    echo -e "${RED}Нет проектов. Сначала создайте проект через new_project.sh${NC}"
    exit 1
fi

PROJECT=$(gum choose --header "? Выберите проект:" $PROJECTS)
echo -e "${GREEN}✓${NC} Проект: ${PROJECT}"


# ШАГ 2: Выбор действия
echo ""
ACTION=$(gum choose --header "? Что сделать?" \
    "present    — Презентация для стейкхолдеров" \
    "summary    — Краткое резюме (1 стр.)" \
    "status     — Статус-отчет" \
    "export-pptx — Создать PPTX" \
    "changelog  — Changelog для стейкхолдеров" \
    "roadmap    — Дорожная карта внедрения" \
    "auto       — Полный цикл (конвейер)")
ACTION=$(echo "$ACTION" | awk '{print $1}')
echo -e "${GREEN}✓${NC} Действие: ${ACTION}"

# ШАГ 3: Выбор аудитории (если present)
AUDIENCE=""
if [ "$ACTION" = "present" ]; then
    echo ""
    AUDIENCE=$(gum choose --header "? Целевая аудитория:" \
        "customer    — Заказчик (бизнес-язык)" \
        "management  — Руководство (метрики, ROI)" \
        "developers  — Разработчики (техническая)")
    AUDIENCE=$(echo "$AUDIENCE" | awk '{print $1}')
    echo -e "${GREEN}✓${NC} Аудитория: ${AUDIENCE}"
fi

# ШАГ 4: Проверка результатов предыдущих агентов
echo ""
echo -e "${CYAN}─── Доступные результаты ───${NC}"
AGENTS_DONE=""
for agent_dir in AGENT_1_ARCHITECT AGENT_2_ROLE_SIMULATOR AGENT_3_DEFENDER AGENT_4_QA_TESTER AGENT_5_TECH_ARCHITECT AGENT_7_MIGRATOR AGENT_8_EPC_DESIGNER; do
    path="${PROJECT}${agent_dir}/"
    if [ -d "$path" ] && [ "$(ls -A "$path" 2>/dev/null)" ]; then
        echo -e "  ${GREEN}✓${NC} ${agent_dir}"
        AGENTS_DONE="${AGENTS_DONE} ${agent_dir}"
    else
        echo -e "  ${RED}✗${NC} ${agent_dir} (нет данных)"
    fi
done

# ШАГ 5: Формирование промпта
echo ""
echo -e "${CYAN}─── Формирование промпта ───${NC}"

PROMPT="Прочитай и используй роль из AGENT_6_PRESENTER.md

Проект: ${PROJECT}
Действие: /${ACTION}"

if [ -n "$AUDIENCE" ]; then
    PROMPT="${PROMPT}
Аудитория: ${AUDIENCE}"
fi

PROMPT="${PROMPT}

Доступные результаты агентов:${AGENTS_DONE}

Прочитай результаты из папок проекта и выполни задачу."

echo "$PROMPT" | pbcopy
echo -e "${GREEN}✅ Промпт скопирован в буфер обмена${NC}"
echo -e "${CYAN}   Вставьте в Claude Code (Cmd+V)${NC}"
echo ""
