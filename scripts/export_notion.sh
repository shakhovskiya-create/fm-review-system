#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# EXPORT_NOTION.SH — Экспорт ФМ в Notion через Claude Code + MCP
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

header "ЭКСПОРТ ФМ В NOTION"

PROJECT=$(select_project)
FM_PATH=$(get_latest_fm "$PROJECT")
FM_VER=$(get_fm_version "$FM_PATH")

info "Проект: ${PROJECT}"
info "ФМ: $(basename "$FM_PATH") (${FM_VER})"

STRUCTURE=$(gum choose --header "Структура в Notion:" \
    "1. Единая страница (весь документ) ⭐" \
    "2. Дерево страниц (раздел = страница)" \
    "3. База данных (требование = запись)")

INCLUDE=$(gum choose --no-limit --header "Что включить? (Space для выбора)" \
    "ФМ (основной документ) ⭐" \
    "Результаты аудита (Agent 1)" \
    "UX-находки (Agent 2)" \
    "Тест-кейсы (Agent 4)" \
    "Архитектура + ТЗ (Agent 5)" \
    "Все результаты агентов")

CONTEXT="ЭКСПОРТ В NOTION
Проект: ${PROJECT}
ФМ: ${FM_PATH}
Версия: ${FM_VER}
Структура: ${STRUCTURE}
Включить: ${INCLUDE}

ИНСТРУКЦИЯ:
1. Прочитай ФМ из ${FM_PATH}
2. Создай страницу/базу в Notion через MCP (notion-mcp)
3. Структурируй согласно выбранному формату
4. Добавь метаданные: версия, дата, статус
5. Для базы данных: каждое требование = отдельная запись с полями:
   - ID, Раздел, Текст требования, Приоритет, Статус, Связанные требования"

echo "$CONTEXT" > "${CONTEXT_FILE}"
launch_claude_code "${ROOT_DIR}/agents/AGENT_7_MIGRATOR.md" "/migrate" "$CONTEXT"
