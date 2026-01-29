#!/bin/bash

# AGENT_3 DEFENDER — Интерактивный лаунчер
# Запуск: ./agent3_defend.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_3: DEFENDER — Защита ФМ от замечаний${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Источник замечаний
SOURCE=$(gum choose --header "? От кого замечания?" \
    "1. Заказчик (бизнес) ⭐" \
    "2. Аудитор/ревьюер" \
    "3. Техспециалист/разработчик" \
    "4. Руководство" \
    "5. Другое")

[[ "$SOURCE" == "5. Другое" ]] && SOURCE=$(gum input --placeholder "Укажите источник...")
echo -e "${GREEN}✓${NC} Источник: ${SOURCE}"

# ШАГ 2: Главный аргумент
ARGUMENT=$(gum choose --header "? Какой главный аргумент использовать?" \
    "1. Скорость — это ускоряет продажи ⭐" \
    "2. Контроль — защищает от потерь" \
    "3. Простота — понятно пользователям" \
    "4. Соответствие требованиям — так в ТЗ" \
    "5. Другое")

[[ "$ARGUMENT" == "5. Другое" ]] && ARGUMENT=$(gum input --placeholder "Укажите аргумент...")
echo -e "${GREEN}✓${NC} Аргумент: ${ARGUMENT}"

# ШАГ 3: Слабые места
WEAKNESS=$(gum choose --header "? Где в ФМ есть слабые места?" \
    "1. Есть пробелы — укажу какие" \
    "2. Есть спорные решения — готов обсудить ⭐" \
    "3. Всё продумано — готов защищать" \
    "4. Не уверен — помоги оценить" \
    "5. Другое")

[[ "$WEAKNESS" == "5. Другое" ]] && WEAKNESS=$(gum input --placeholder "Опишите...")
echo -e "${GREEN}✓${NC} Слабости: ${WEAKNESS}"

# Сохраняем
CONTEXT="КОНТЕКСТ ИНТЕРВЬЮ (AGENT_3 DEFENDER):
- Источник замечаний: ${SOURCE}
- Главный аргумент защиты: ${ARGUMENT}
- Слабые места: ${WEAKNESS}"

echo "$CONTEXT" > "/Users/antonsahovskii/Documents/claude-agents/fm-review-system/.interview_context.txt"

echo ""
echo -e "${GREEN}✅ Интервью завершено!${NC}"
echo ""
echo "Теперь в Claude Code напиши:"
echo -e "${CYAN}  /defend${NC}"
