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
