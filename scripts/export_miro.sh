#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# EXPORT_MIRO.SH — Экспорт процесса в Miro через MCP
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

header "ЭКСПОРТ В MIRO"

PROJECT=$(select_project)
FM_PATH=$(get_latest_fm "$PROJECT")

DIAGRAM_TYPE=$(gum choose --header "Тип диаграммы:" \
    "1. BPMN-процесс (основной бизнес-процесс) ⭐" \
    "2. Диаграмма состояний (статусы документа)" \
    "3. Схема интеграций (взаимодействие систем)" \
    "4. Архитектура данных (объекты 1С)" \
    "5. Матрица ролей (RACI)")

BOARD=$(gum choose --header "Куда размещать?" \
    "1. Создать новую доску" \
    "2. Добавить на существующую")

BOARD_URL=""
if [[ "$BOARD" == "2."* ]]; then
    BOARD_URL=$(gum input --header "URL доски Miro:" --placeholder "https://miro.com/app/board/...")
fi

CONTEXT="ЭКСПОРТ В MIRO
Проект: ${PROJECT}
ФМ: ${FM_PATH}
Тип диаграммы: ${DIAGRAM_TYPE}
Доска: ${BOARD_URL:-новая}

ИНСТРУКЦИЯ:
1. Прочитай ФМ из ${FM_PATH}
2. Извлеки процесс/состояния/интеграции в зависимости от типа
3. Используй Miro MCP для создания диаграммы:
   - Для BPMN: flowchart с ролями как swim lanes
   - Для состояний: state diagram с переходами
   - Для интеграций: блок-схема систем и потоков данных
   - Для архитектуры: ER-диаграмма объектов 1С
   - Для RACI: таблица в Miro
4. Используй цвета: зеленый=автоматически, желтый=ручное действие, красный=блокировка
5. Добавь легенду и метаданные (версия ФМ, дата)"

echo "$CONTEXT" > "${CONTEXT_FILE}"
launch_claude_code "${ROOT_DIR}/AGENT_8_EPC_DESIGNER.md" "/epc" "$CONTEXT"
