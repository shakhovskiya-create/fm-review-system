#!/bin/bash

# AGENT_5 TECH ARCHITECT — Интерактивный лаунчер
# Запуск: ./agent5_architect.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_5: TECH ARCHITECT — Проектирование 1С${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Пользователи
USERS=$(gum choose --header "? Сколько пользователей одновременно?" \
    "1. До 10 пользователей" \
    "2. 10-50 пользователей ⭐" \
    "3. 50-200 пользователей" \
    "4. Больше 200" \
    "5. Другое")

[[ "$USERS" == "5. Другое" ]] && USERS=$(gum input --placeholder "Укажите количество...")
echo -e "${GREEN}✓${NC} Пользователей: ${USERS}"

# ШАГ 2: Скорость
SPEED=$(gum choose --header "? Требования к скорости проведения документа?" \
    "1. До 1 секунды (высокая нагрузка)" \
    "2. До 3 секунд ⭐" \
    "3. До 10 секунд (приемлемо)" \
    "4. Не критично" \
    "5. Другое")

[[ "$SPEED" == "5. Другое" ]] && SPEED=$(gum input --placeholder "Укажите требование...")
echo -e "${GREEN}✓${NC} Скорость: ${SPEED}"

# ШАГ 3: Интеграции
INTEGRATIONS=$(gum choose --header "? Какие интеграции нужны?" \
    "1. Только внутри 1С (обмен между базами)" \
    "2. WMS/склад ⭐" \
    "3. Банк-клиент / эквайринг" \
    "4. Маркетплейсы / EDI" \
    "5. Другое")

[[ "$INTEGRATIONS" == "5. Другое" ]] && INTEGRATIONS=$(gum input --placeholder "Укажите интеграции...")
echo -e "${GREEN}✓${NC} Интеграции: ${INTEGRATIONS}"

# ШАГ 4: Конфигурация
CONFIG=$(gum choose --header "? Какая конфигурация 1С?" \
    "1. 1С:ERP" \
    "2. 1С:УТ (Управление торговлей) ⭐" \
    "3. 1С:КА (Комплексная автоматизация)" \
    "4. 1С:УХ + УТ" \
    "5. Самописная/другая")

[[ "$CONFIG" == "5. Самописная/другая" ]] && CONFIG=$(gum input --placeholder "Укажите...")
echo -e "${GREEN}✓${NC} Конфигурация: ${CONFIG}"

# ШАГ 5: Выход
OUTPUT=$(gum choose --header "? Что нужно на выходе?" \
    "1. Архитектура данных (справочники, документы, регистры)" \
    "2. Оценка трудоёмкости" \
    "3. Полное ТЗ на разработку ⭐" \
    "4. Всё вместе" \
    "5. Другое")

[[ "$OUTPUT" == "5. Другое" ]] && OUTPUT=$(gum input --placeholder "Укажите...")
echo -e "${GREEN}✓${NC} Выход: ${OUTPUT}"

# Сохраняем
CONTEXT="КОНТЕКСТ ИНТЕРВЬЮ (AGENT_5 TECH ARCHITECT):
- Кол-во пользователей: ${USERS}
- Требование к скорости: ${SPEED}
- Интеграции: ${INTEGRATIONS}
- Конфигурация 1С: ${CONFIG}
- Нужен на выходе: ${OUTPUT}"

echo "$CONTEXT" > "/Users/antonsahovskii/Documents/claude-agents/fm-review-system/.interview_context.txt"

echo ""
echo -e "${GREEN}✅ Интервью завершено!${NC}"
echo ""
echo "Теперь в Claude Code напиши:"
echo -e "${CYAN}  /architecture${NC} или ${CYAN}/tz${NC}"
