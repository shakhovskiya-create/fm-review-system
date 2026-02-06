#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# QUALITY_GATE.SH — Проверка качества ФМ перед передачей
# ═══════════════════════════════════════════════════════════════
# Запуск: ./scripts/quality_gate.sh [PROJECT_NAME]
#
# Проверяет:
# 1. Наличие обязательных разделов ФМ
# 2. Наличие результатов работы агентов
# 3. Отсутствие открытых CRITICAL/HIGH замечаний
# 4. Полноту метаданных (версия, дата, паспорт)
# 5. Готовность к передаче в разработку

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT="${1:-}"
if [[ -z "$PROJECT" ]]; then
    check_gum
    PROJECT=$(select_project)
fi

header "QUALITY GATE: ${PROJECT}"

PROJECT_DIR="${ROOT_DIR}/projects/${PROJECT}"
PASS=0
FAIL=0
WARN=0

check_pass() { ((PASS++)); echo -e "  ${GREEN}✅ $1${NC}"; }
check_fail() { ((FAIL++)); echo -e "  ${RED}❌ $1${NC}"; }
check_warn() { ((WARN++)); echo -e "  ${YELLOW}⚠️  $1${NC}"; }

# ─── 1. СТРУКТУРА ПРОЕКТА ───────────────────────────────────
subheader "1. Структура проекта"

[[ -d "${PROJECT_DIR}/FM_DOCUMENTS" ]] && check_pass "FM_DOCUMENTS/" || check_fail "FM_DOCUMENTS/ отсутствует"
[[ -f "${PROJECT_DIR}/README.md" ]] && check_pass "README.md" || check_warn "README.md отсутствует"
[[ -f "${PROJECT_DIR}/PROJECT_CONTEXT.md" ]] && check_pass "PROJECT_CONTEXT.md" || check_warn "PROJECT_CONTEXT.md отсутствует"

# ─── 2. ФМ ──────────────────────────────────────────────────
subheader "2. Функциональная модель"

FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null)
if [[ -n "$FM_PATH" ]]; then
    check_pass "ФМ найдена: $(basename "$FM_PATH")"
    FM_VER=$(get_fm_version "$FM_PATH")
    [[ -n "$FM_VER" ]] && check_pass "Версия: ${FM_VER}" || check_warn "Версия не определена в имени файла"
else
    check_fail "ФМ не найдена в FM_DOCUMENTS/"
fi

# ─── 3. РЕЗУЛЬТАТЫ АГЕНТОВ ──────────────────────────────────
subheader "3. Результаты агентов"

AGENTS=("AGENT_1_ARCHITECT:Аудит" "AGENT_2_ROLE_SIMULATOR:Симуляция ролей" "AGENT_4_QA_TESTER:Тест-кейсы" "AGENT_5_TECH_ARCHITECT:Архитектура" "AGENT_7_MIGRATOR:Публикация в Confluence" "AGENT_8_EPC_DESIGNER:ePC диаграмма")

for agent_info in "${AGENTS[@]}"; do
    agent_dir=$(echo "$agent_info" | cut -d: -f1)
    agent_name=$(echo "$agent_info" | cut -d: -f2)
    agent_path="${PROJECT_DIR}/${agent_dir}"
    
    if [[ -d "$agent_path" ]]; then
        md_count=$(ls "$agent_path"/*.md 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$md_count" -gt 0 ]]; then
            check_pass "${agent_name}: ${md_count} отчет(ов)"
        else
            check_warn "${agent_name}: папка есть, отчетов нет"
        fi
    else
        check_warn "${agent_name}: не выполнен"
    fi
done

# ─── 4. ОТКРЫТЫЕ ЗАМЕЧАНИЯ ──────────────────────────────────
subheader "4. Открытые замечания"

OPEN_CRITICAL=0
OPEN_HIGH=0

for report in "${PROJECT_DIR}"/AGENT_1_ARCHITECT/*.md; do
    [[ -f "$report" ]] || continue
    # Ищем незакрытые CRITICAL/HIGH
    OPEN_CRITICAL=$((OPEN_CRITICAL + $(grep -c "CRITICAL.*Открыт" "$report" 2>/dev/null || echo 0)))
    OPEN_HIGH=$((OPEN_HIGH + $(grep -c "HIGH.*Открыт" "$report" 2>/dev/null || echo 0)))
done

[[ $OPEN_CRITICAL -eq 0 ]] && check_pass "Нет открытых CRITICAL" || check_fail "${OPEN_CRITICAL} открытых CRITICAL"
[[ $OPEN_HIGH -eq 0 ]] && check_pass "Нет открытых HIGH" || check_warn "${OPEN_HIGH} открытых HIGH"

# ─── 5. CHANGELOG ───────────────────────────────────────────
subheader "5. Документация"

[[ -f "${PROJECT_DIR}/CHANGELOG.md" ]] && check_pass "CHANGELOG.md" || check_warn "CHANGELOG.md отсутствует"

# ─── 6. CONFLUENCE & MIRO ──────────────────────────────────
subheader "6. Confluence & Miro"

if [[ -f "${PROJECT_DIR}/PROJECT_CONTEXT.md" ]]; then
    CONFLUENCE_URL=$(grep -o "https://[^ ]*atlassian.net/wiki/[^ ]*" "${PROJECT_DIR}/PROJECT_CONTEXT.md" 2>/dev/null | head -1)
    MIRO_URL=$(grep -o "https://miro.com/[^ ]*" "${PROJECT_DIR}/PROJECT_CONTEXT.md" 2>/dev/null | head -1)
    
    [[ -n "$CONFLUENCE_URL" ]] && check_pass "Confluence URL: найден" || check_warn "Confluence URL: не найден (Agent 7 не выполнен?)"
    [[ -n "$MIRO_URL" ]] && check_pass "Miro Board: найден" || check_warn "Miro Board: не найден (Agent 8 не выполнен?)"
else
    check_warn "PROJECT_CONTEXT.md не найден — Confluence/Miro статус не проверен"
fi

# ─── ИТОГ ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed: ${PASS}${NC}  ${YELLOW}Warnings: ${WARN}${NC}  ${RED}Failed: ${FAIL}${NC}"

if [[ $FAIL -eq 0 && $WARN -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}ГОТОВО К ПЕРЕДАЧЕ В РАЗРАБОТКУ ${ICO_OK}${NC}"
elif [[ $FAIL -eq 0 ]]; then
    echo -e "  ${YELLOW}${BOLD}ГОТОВО С ОГОВОРКАМИ ${ICO_WARN}${NC}"
else
    echo -e "  ${RED}${BOLD}НЕ ГОТОВО — ЕСТЬ КРИТИЧЕСКИЕ ПРОБЛЕМЫ ${ICO_FAIL}${NC}"
fi
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
