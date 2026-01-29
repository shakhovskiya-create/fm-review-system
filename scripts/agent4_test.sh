#!/bin/bash

# AGENT_4 QA TESTER — Интерактивный лаунчер
# Запуск: ./agent4_test.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  AGENT_4: QA TESTER — Генерация тест-кейсов${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ШАГ 1: Фокус тестирования
FOCUS=$(gum choose --header "? На чём фокус тестирования?" \
    "1. Скорость операций (SLA, время отклика)" \
    "2. Защита от манипуляций ⭐" \
    "3. Корректность расчётов" \
    "4. Полное покрытие (всё вместе)" \
    "5. Другое")

[[ "$FOCUS" == "5. Другое" ]] && FOCUS=$(gum input --placeholder "Укажите фокус...")
echo -e "${GREEN}✓${NC} Фокус: ${FOCUS}"

# ШАГ 2: Время сделки
TIME=$(gum choose --header "? За сколько должна проходить типичная сделка?" \
    "1. До 2 минут" \
    "2. 2-5 минут ⭐" \
    "3. 5-15 минут" \
    "4. Не знаю — нужно определить" \
    "5. Другое")

[[ "$TIME" == "5. Другое" ]] && TIME=$(gum input --placeholder "Укажите время...")
echo -e "${GREEN}✓${NC} Время: ${TIME}"

# ШАГ 3: Манипуляции
MANIPULATIONS=$(gum choose --header "? Какие манипуляции уже были в компании?" \
    "1. Изменение документов задним числом ⭐" \
    "2. Превышение лимитов/скидок" \
    "3. Отгрузка без оплаты" \
    "4. Не было / не знаю" \
    "5. Другое")

[[ "$MANIPULATIONS" == "5. Другое" ]] && MANIPULATIONS=$(gum input --placeholder "Опишите...")
echo -e "${GREEN}✓${NC} Манипуляции: ${MANIPULATIONS}"

# ШАГ 4: Объём тестов
SCOPE=$(gum choose --header "? Какой объём тест-плана нужен?" \
    "1. Только критические сценарии (быстро)" \
    "2. Основные + манипуляции ⭐" \
    "3. Полный тест-план (долго)" \
    "4. Только smoke-тесты" \
    "5. Другое")

[[ "$SCOPE" == "5. Другое" ]] && SCOPE=$(gum input --placeholder "Укажите объём...")
echo -e "${GREEN}✓${NC} Объём: ${SCOPE}"

# Сохраняем
CONTEXT="КОНТЕКСТ ИНТЕРВЬЮ (AGENT_4 QA TESTER):
- Фокус тестирования: ${FOCUS}
- Целевое время сделки: ${TIME}
- Известные манипуляции: ${MANIPULATIONS}
- Объём тест-плана: ${SCOPE}"

echo "$CONTEXT" > "/Users/antonsahovskii/Documents/claude-agents/fm-review-system/.interview_context.txt"

echo ""
echo -e "${GREEN}✅ Интервью завершено!${NC}"
echo ""
echo "Теперь в Claude Code напиши:"
echo -e "${CYAN}  /tests${NC}"
