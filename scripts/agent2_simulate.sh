#!/bin/bash

# AGENT_2 ROLE SIMULATOR — Интерактивный лаунчер
# Запуск: ./agent2_simulate.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_2: ROLE SIMULATOR — Симуляция ролей${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Роль
ROLE=$(gum choose --header "? Какую роль симулировать глубже всего?" \
    "1. Менеджер по продажам ⭐" \
    "2. Руководитель отдела продаж" \
    "3. Кладовщик/логист" \
    "4. Бухгалтер/финансист" \
    "5. Другое")

[[ "$ROLE" == "5. Другое" ]] && ROLE=$(gum input --placeholder "Укажите роль...")
echo -e "${GREEN}✓${NC} Роль: ${ROLE}"

# ШАГ 2: Объём сделок
VOLUME=$(gum choose --header "? Сколько сделок в день у одного менеджера?" \
    "1. До 10 сделок" \
    "2. 10-30 сделок ⭐" \
    "3. 30-50 сделок" \
    "4. Больше 50 сделок" \
    "5. Другое")

[[ "$VOLUME" == "5. Другое" ]] && VOLUME=$(gum input --placeholder "Укажите количество...")
echo -e "${GREEN}✓${NC} Объём: ${VOLUME}"

# ШАГ 3: Боли
PAIN=$(gum choose --header "? Что сейчас бесит пользователей?" \
    "1. Долгое согласование ⭐" \
    "2. Много кликов/полей" \
    "3. Непонятные ошибки" \
    "4. Не знаю — нужно выяснить" \
    "5. Другое")

[[ "$PAIN" == "5. Другое" ]] && PAIN=$(gum input --placeholder "Опишите боли...")
echo -e "${GREEN}✓${NC} Боль: ${PAIN}"

# ШАГ 4: Время на сделку
TIME=$(gum choose --header "? За сколько минут должна проходить типовая сделка?" \
    "1. До 2 минут" \
    "2. 2-5 минут ⭐" \
    "3. 5-15 минут" \
    "4. Не критично — главное контроль" \
    "5. Другое")

[[ "$TIME" == "5. Другое" ]] && TIME=$(gum input --placeholder "Укажите время...")
echo -e "${GREEN}✓${NC} Время: ${TIME}"

# Сохраняем
CONTEXT="КОНТЕКСТ ИНТЕРВЬЮ (AGENT_2 ROLE SIMULATOR):
- Роль для симуляции: ${ROLE}
- Объём сделок: ${VOLUME}
- Главная боль: ${PAIN}
- Целевое время сделки: ${TIME}"

echo "$CONTEXT" > "/Users/antonsahovskii/Documents/claude-agents/fm-review-system/.interview_context.txt"

echo ""
echo -e "${GREEN}✅ Интервью завершено!${NC}"
echo ""
echo "Теперь в Claude Code напиши:"
echo -e "${CYAN}  /simulate${NC}"
