#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# QUALITY_GATE.SH — Проверка качества ФМ перед передачей v2.0
# ═══════════════════════════════════════════════════════════════
# Запуск: ./scripts/quality_gate.sh [PROJECT_NAME] [--reason "текст"]
#
# Проверяет:
# 1. Наличие обязательных разделов ФМ
# 2. Наличие результатов работы агентов
# 3. Наличие _summary.json сайдкаров (FC-07A)
# 4. Отсутствие открытых CRITICAL/HIGH замечаний
# 5. Матрица трассируемости (FC-10A)
# 6. Журнал аудита Confluence (FC-12B)
# 7. Полноту метаданных (версия, дата, паспорт)
# 8. Готовность к передаче в разработку
#
# Коды выхода: 0=готово, 1=критические ошибки, 2=предупреждения
# FC-08C: При коде 2 можно пропустить с --reason "обоснование"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

PROJECT=""
SKIP_REASON=""

# FC-08C: Обработка --reason для пропуска предупреждений
while [[ $# -gt 0 ]]; do
    case "$1" in
        --reason) SKIP_REASON="$2"; shift 2 ;;
        --reason=*) SKIP_REASON="${1#*=}"; shift ;;
        *) [[ -z "$PROJECT" ]] && PROJECT="$1"; shift ;;
    esac
done

if [[ -z "$PROJECT" ]]; then
    check_gum
    PROJECT=$(select_project)
fi

header "QUALITY GATE: ${PROJECT}"

PROJECT_DIR="${ROOT_DIR}/projects/${PROJECT}"
PASS=0
FAIL=0
WARN=0

check_pass() { ((++PASS)); echo -e "  ${GREEN}✅ $1${NC}"; }
check_fail() { ((++FAIL)); echo -e "  ${RED}❌ $1${NC}"; }
check_warn() { ((++WARN)); echo -e "  ${YELLOW}⚠️  $1${NC}"; }

# ─── 1. СТРУКТУРА ПРОЕКТА ───────────────────────────────────
subheader "1. Структура проекта"

# AG-02: FM_DOCUMENTS необязателен при Confluence-only
[[ -d "${PROJECT_DIR}/FM_DOCUMENTS" ]] && check_pass "FM_DOCUMENTS/" || check_warn "FM_DOCUMENTS/ отсутствует (допустимо при Confluence-only)"
[[ -f "${PROJECT_DIR}/README.md" ]] && check_pass "README.md" || check_warn "README.md отсутствует"
[[ -f "${PROJECT_DIR}/PROJECT_CONTEXT.md" ]] && check_pass "PROJECT_CONTEXT.md" || check_warn "PROJECT_CONTEXT.md отсутствует"
[[ -d "${PROJECT_DIR}/CHANGES" ]] && check_pass "CHANGES/" || check_warn "CHANGES/ отсутствует"

# ─── 2. ФМ ──────────────────────────────────────────────────
subheader "2. Функциональная модель"

if [[ -d "${PROJECT_DIR}/FM_DOCUMENTS" ]]; then
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
else
    FM_PATH=""
fi
if [[ -n "$FM_PATH" ]]; then
    check_pass "ФМ найдена: $(basename "$FM_PATH")"
    FM_VER=$(get_fm_version "$FM_PATH")
    [[ -n "$FM_VER" ]] && check_pass "Версия: ${FM_VER}" || check_warn "Версия не определена в имени файла"
else
    check_warn "ФМ не найдена в FM_DOCUMENTS/ (допустимо при Confluence-only)"
fi

# ─── 3. РЕЗУЛЬТАТЫ АГЕНТОВ ──────────────────────────────────
subheader "3. Результаты агентов"

# AG-11: учитываем старые и новые имена папок 7/8
AGENTS=("AGENT_1_ARCHITECT:Аудит" "AGENT_2_ROLE_SIMULATOR:Симуляция ролей" "AGENT_4_QA_TESTER:Тест-кейсы" "AGENT_5_TECH_ARCHITECT:Архитектура" "AGENT_7:Публикация в Confluence" "AGENT_8:BPMN диаграмма")

for agent_info in "${AGENTS[@]}"; do
    agent_key=$(echo "$agent_info" | cut -d: -f1)
    agent_name=$(echo "$agent_info" | cut -d: -f2)
    # AGENT_7: PUBLISHER или MIGRATOR; AGENT_8: BPMN_DESIGNER или EPC_DESIGNER
    if [[ "$agent_key" == "AGENT_7" ]]; then
        agent_path="${PROJECT_DIR}/AGENT_7_PUBLISHER"
        [[ -d "$agent_path" ]] || agent_path="${PROJECT_DIR}/AGENT_7_MIGRATOR"
    elif [[ "$agent_key" == "AGENT_8" ]]; then
        agent_path="${PROJECT_DIR}/AGENT_8_BPMN_DESIGNER"
        [[ -d "$agent_path" ]] || agent_path="${PROJECT_DIR}/AGENT_8_EPC_DESIGNER"
    else
        agent_path="${PROJECT_DIR}/${agent_key}"
    fi
    
    if [[ -d "$agent_path" ]]; then
        md_count=$(find "$agent_path" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
        if [[ "${md_count:-0}" -gt 0 ]]; then
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

# AG-07: статус открыто — "Открыт" или "Open"
for report in "${PROJECT_DIR}"/AGENT_1_ARCHITECT/*.md; do
    [[ -f "$report" ]] || continue
    n_c=$(grep -cE "CRITICAL.*(Открыт|Open)" "$report" 2>/dev/null) || n_c=0
    n_h=$(grep -cE "HIGH.*(Открыт|Open)" "$report" 2>/dev/null) || n_h=0
    OPEN_CRITICAL=$((OPEN_CRITICAL + ${n_c:-0}))
    OPEN_HIGH=$((OPEN_HIGH + ${n_h:-0}))
done

[[ $OPEN_CRITICAL -eq 0 ]] && check_pass "Нет открытых CRITICAL" || check_fail "${OPEN_CRITICAL} открытых CRITICAL"
[[ $OPEN_HIGH -eq 0 ]] && check_pass "Нет открытых HIGH" || check_warn "${OPEN_HIGH} открытых HIGH"

# ─── 5. _SUMMARY.JSON САЙДКАРЫ (FC-07A) ─────────────────────
subheader "5. Сайдкары _summary.json (FC-07A)"

SUMMARY_COUNT=0
SUMMARY_FAILED=0
for agent_dir in "${PROJECT_DIR}"/AGENT_*/; do
    [[ -d "$agent_dir" ]] || continue
    agent_name=$(basename "$agent_dir")
    summary_found=$(find "$agent_dir" -maxdepth 2 -name '*_summary.json' 2>/dev/null | head -1)
    if [[ -n "$summary_found" ]]; then
        # Проверяем обязательные поля
        if command -v jq &>/dev/null; then
            has_required=$(jq -e '.agent and .command and .status and .project' "$summary_found" 2>/dev/null && echo "yes" || echo "no")
            if [[ "$has_required" == "yes" ]]; then
                status=$(jq -r '.status' "$summary_found")
                check_pass "${agent_name}: _summary.json (status=${status})"
                ((SUMMARY_COUNT++)) || true
            else
                check_warn "${agent_name}: _summary.json невалидный (нет обязательных полей)"
                ((SUMMARY_FAILED++)) || true
            fi
        else
            check_pass "${agent_name}: _summary.json найден"
            ((SUMMARY_COUNT++)) || true
        fi
    else
        md_count=$(find "$agent_dir" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
        if [[ "${md_count:-0}" -gt 0 ]]; then
            check_warn "${agent_name}: отчеты есть, но _summary.json отсутствует"
        fi
    fi
done
[[ $SUMMARY_COUNT -gt 0 ]] && check_pass "Всего валидных _summary.json: ${SUMMARY_COUNT}" || check_warn "Ни одного _summary.json не найдено"

# ─── 6. МАТРИЦА ТРАССИРУЕМОСТИ (FC-10A) ─────────────────────
subheader "6. Трассируемость (FC-10A)"

TRACE_MATRIX=$(find "${PROJECT_DIR}/AGENT_4_QA_TESTER" -name 'traceability-matrix.json' 2>/dev/null | head -1) || true
if [[ -n "$TRACE_MATRIX" ]]; then
    if command -v jq &>/dev/null; then
        total=$(jq -r '.summary.totalFindings // 0' "$TRACE_MATRIX" 2>/dev/null)
        covered=$(jq -r '.summary.covered // 0' "$TRACE_MATRIX" 2>/dev/null)
        uncovered=$(jq -r '.summary.uncovered // 0' "$TRACE_MATRIX" 2>/dev/null)
        check_pass "Матрица трассируемости: ${total} замечаний, ${covered} покрыто, ${uncovered} без тестов"
        [[ "${uncovered:-0}" -gt 0 ]] && check_warn "${uncovered} замечаний без тестов"
    else
        check_pass "Матрица трассируемости найдена"
    fi
else
    check_warn "Матрица трассируемости отсутствует (создается Agent 4)"
fi

# ─── 6.5 JSON FINDINGS COVERAGE (CRITICAL-A1) ────────────────
subheader "6.5. JSON findings coverage (CRITICAL-A1)"

FINDINGS_JSON=$(find "${PROJECT_DIR}/AGENT_1_ARCHITECT" -name '*_findings.json' 2>/dev/null | head -1) || true
if [[ -n "$FINDINGS_JSON" ]] && command -v jq &>/dev/null; then
    total_findings=$(jq '.findings | length' "$FINDINGS_JSON" 2>/dev/null) || total_findings=0
    crit_findings=$(jq '[.findings[] | select(.severity == "CRITICAL")] | length' "$FINDINGS_JSON" 2>/dev/null) || crit_findings=0
    check_pass "JSON findings: ${total_findings} (${crit_findings} CRITICAL)"

    # Check if all CRITICAL findings from Agent 1 are covered by Agent 4 test cases
    if [[ -n "$TRACE_MATRIX" && "$crit_findings" -gt 0 ]]; then
        uncovered_crit=$(jq -r --slurpfile findings "$FINDINGS_JSON" '
            [($findings[0].findings[] | select(.severity == "CRITICAL") | .id)] as $crit_ids |
            [.entries[] | select(.status == "covered") | .findingId] as $covered |
            [$crit_ids[] | select(. as $id | $covered | index($id) | not)]
            | length
        ' "$TRACE_MATRIX" 2>/dev/null) || uncovered_crit=""
        if [[ -n "$uncovered_crit" && "$uncovered_crit" -gt 0 ]]; then
            check_fail "${uncovered_crit} CRITICAL findings без покрытия тестами"
        elif [[ -n "$uncovered_crit" ]]; then
            check_pass "Все CRITICAL findings покрыты тестами"
        fi
    fi
else
    check_warn "JSON findings не найден (_findings.json от Agent 1)"
fi

# ─── 7. ЖУРНАЛ АУДИТА CONFLUENCE (FC-12B) ────────────────────
subheader "7. Журнал аудита Confluence (FC-12B)"

AUDIT_LOG_DIR="${SCRIPTS_DIR}/.audit_log"
if [[ -d "$AUDIT_LOG_DIR" ]]; then
    log_files=$(find "$AUDIT_LOG_DIR" -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${log_files:-0}" -gt 0 ]]; then
        check_pass "Журнал аудита: ${log_files} файл(ов)"
        # Проверяем что все записи от Agent 7
        if command -v jq &>/dev/null; then
            for logfile in "${AUDIT_LOG_DIR}"/*.jsonl; do
                [[ -f "$logfile" ]] || continue
                non_publisher=$(jq -r 'select(.agent != "Agent7_Publisher" and .agent != "unknown" and .agent != "system") | .agent' "$logfile" 2>/dev/null | sort -u)
                if [[ -n "$non_publisher" ]]; then
                    check_warn "Записи в Confluence от агентов кроме Agent 7: ${non_publisher}"
                fi
            done
        fi
    else
        check_warn "Журнал аудита пуст"
    fi
else
    check_warn "Журнал аудита отсутствует (создается при первой записи в Confluence)"
fi

# ─── 8. CHANGELOG ───────────────────────────────────────────
subheader "8. Документация"

[[ -f "${PROJECT_DIR}/CHANGELOG.md" ]] && check_pass "CHANGELOG.md" || check_warn "CHANGELOG.md отсутствует"

# ─── 8.5 BUSINESS REVIEW TIMEOUT (D1) ─────────────────────
subheader "8.5. Бизнес-ревью: лимиты"

MAX_ITERATIONS=5
MAX_DAYS=7
CONTEXT_FILE="${PROJECT_DIR}/PROJECT_CONTEXT.md"

if [[ -f "$CONTEXT_FILE" ]]; then
    ITER_COUNT=$(grep -oP 'iteration_count:\s*\K[0-9]+' "$CONTEXT_FILE" 2>/dev/null | tail -1) || true
    REVIEW_START=$(grep -oP 'review_start_date:\s*\K[0-9]{4}-[0-9]{2}-[0-9]{2}' "$CONTEXT_FILE" 2>/dev/null | tail -1) || true

    if [[ -n "$ITER_COUNT" ]]; then
        if [[ "$ITER_COUNT" -ge "$MAX_ITERATIONS" ]]; then
            check_fail "Бизнес-ревью: ${ITER_COUNT}/${MAX_ITERATIONS} итераций — лимит исчерпан"
        elif [[ "$ITER_COUNT" -ge $((MAX_ITERATIONS - 1)) ]]; then
            check_warn "Бизнес-ревью: ${ITER_COUNT}/${MAX_ITERATIONS} итераций — осталась 1"
        else
            check_pass "Бизнес-ревью: ${ITER_COUNT}/${MAX_ITERATIONS} итераций"
        fi
    fi

    if [[ -n "$REVIEW_START" ]]; then
        START_EPOCH=$(date -d "$REVIEW_START" +%s 2>/dev/null) || true
        if [[ -n "$START_EPOCH" ]]; then
            NOW_EPOCH=$(date +%s)
            DAYS_ELAPSED=$(( (NOW_EPOCH - START_EPOCH) / 86400 ))
            if [[ "$DAYS_ELAPSED" -ge "$MAX_DAYS" ]]; then
                check_fail "Бизнес-ревью: ${DAYS_ELAPSED}/${MAX_DAYS} дней — таймаут"
            elif [[ "$DAYS_ELAPSED" -ge $((MAX_DAYS - 2)) ]]; then
                check_warn "Бизнес-ревью: ${DAYS_ELAPSED}/${MAX_DAYS} дней — осталось $((MAX_DAYS - DAYS_ELAPSED))"
            else
                check_pass "Бизнес-ревью: ${DAYS_ELAPSED}/${MAX_DAYS} дней"
            fi
        fi
    fi
fi

# ─── 8.6 VERSION COHERENCE ─────────────────────────────────
subheader "8.6. Когерентность версий"

# Собираем FM-версию из разных источников
VER_CONTEXT=""
VER_SUMMARY=""
VER_CONFLUENCE=""
if [[ -f "$CONTEXT_FILE" ]]; then
    VER_CONTEXT=$(grep -oP 'Версия ФМ:\s*\K[0-9]+\.[0-9]+\.[0-9]+' "$CONTEXT_FILE" 2>/dev/null | head -1) || true
fi
# Ищем версию в _summary.json файлах
for summary in "${PROJECT_DIR}"/AGENT_*/*_summary.json; do
    [[ -f "$summary" ]] || continue
    if command -v jq &>/dev/null; then
        s_ver=$(jq -r '.fmVersion // empty' "$summary" 2>/dev/null) || true
        if [[ -n "$s_ver" && -z "$VER_SUMMARY" ]]; then
            VER_SUMMARY="$s_ver"
        elif [[ -n "$s_ver" && "$s_ver" != "$VER_SUMMARY" ]]; then
            check_warn "Версия в $(basename "$summary") ($s_ver) отличается от других summary ($VER_SUMMARY)"
        fi
    fi
done

# CRITICAL-A2: проверка версии из Confluence (если доступен)
_QG_PAGE_ID=""
_QG_PAGE_ID_FILE="${PROJECT_DIR}/CONFLUENCE_PAGE_ID"
[[ -f "$_QG_PAGE_ID_FILE" ]] && _QG_PAGE_ID=$(tr -d '[:space:]' < "$_QG_PAGE_ID_FILE") || true
_QG_CONFLUENCE_URL="${CONFLUENCE_URL:-}"
_QG_CONFLUENCE_TOKEN="${CONFLUENCE_TOKEN:-}"

if [[ -n "$_QG_PAGE_ID" && -n "$_QG_CONFLUENCE_URL" && -n "$_QG_CONFLUENCE_TOKEN" ]] && command -v curl &>/dev/null; then
    _page_body=$(curl -sf -m 10 \
        -H "Authorization: Bearer ${_QG_CONFLUENCE_TOKEN}" \
        -H "Accept: application/json" \
        "${_QG_CONFLUENCE_URL}/rest/api/content/${_QG_PAGE_ID}?expand=body.storage" 2>/dev/null) || true
    if [[ -n "$_page_body" ]] && command -v jq &>/dev/null; then
        _body_html=$(jq -r '.body.storage.value // empty' <<< "$_page_body" 2>/dev/null) || true
        if [[ -n "$_body_html" ]]; then
            VER_CONFLUENCE=$(echo "$_body_html" | grep -oP 'Версия ФМ[^0-9]*\K[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
        fi
    fi
fi

# Сравниваем все три источника
_local_ver="${VER_CONTEXT:-${VER_SUMMARY:-}}"
if [[ -n "$VER_CONFLUENCE" && -n "$_local_ver" ]]; then
    if [[ "$VER_CONFLUENCE" == "$_local_ver" ]]; then
        check_pass "Версия когерентна: ${_local_ver} (Confluence == local)"
    else
        check_fail "Версия рассинхронизирована: Confluence=${VER_CONFLUENCE}, local=${_local_ver}"
    fi
elif [[ -n "$VER_CONFLUENCE" ]]; then
    check_pass "Версия из Confluence: ${VER_CONFLUENCE}"
elif [[ -n "$VER_CONTEXT" && -n "$VER_SUMMARY" ]]; then
    if [[ "$VER_CONTEXT" == "$VER_SUMMARY" ]]; then
        check_pass "Версия когерентна: ${VER_CONTEXT} (context == summaries, Confluence недоступен)"
    else
        check_warn "Версия рассинхронизирована: PROJECT_CONTEXT=${VER_CONTEXT}, summaries=${VER_SUMMARY}"
    fi
elif [[ -n "$VER_CONTEXT" ]]; then
    check_pass "Версия из PROJECT_CONTEXT: ${VER_CONTEXT} (Confluence и summaries для сравнения нет)"
elif [[ -n "$VER_SUMMARY" ]]; then
    check_pass "Версия из summaries: ${VER_SUMMARY} (PROJECT_CONTEXT не содержит версию)"
else
    check_warn "FM-версия не определена ни в PROJECT_CONTEXT.md, ни в _summary.json"
fi

# ─── 9. CONFLUENCE & BPMN ──────────────────────────────────
subheader "9. Confluence & BPMN/диаграммы"

# FC-14: Проверяем наличие CONFLUENCE_PAGE_ID и URL Confluence (ekf.su, не atlassian.net)
PAGE_ID_FILE="${PROJECT_DIR}/CONFLUENCE_PAGE_ID"
if [[ -f "$PAGE_ID_FILE" ]]; then
    PAGE_ID=$(cat "$PAGE_ID_FILE" | tr -d '[:space:]')
    [[ -n "$PAGE_ID" ]] && check_pass "Confluence PAGE_ID: ${PAGE_ID}" || check_warn "CONFLUENCE_PAGE_ID файл пуст"
else
    # Альтернатива: искать PAGE_ID в PROJECT_CONTEXT.md
    if [[ -f "${PROJECT_DIR}/PROJECT_CONTEXT.md" ]]; then
        CONFLUENCE_URL=$(grep -o "https://confluence[^ ]*ekf[^ ]*" "${PROJECT_DIR}/PROJECT_CONTEXT.md" 2>/dev/null | head -1) || true
        [[ -n "$CONFLUENCE_URL" ]] && check_pass "Confluence URL: найден" || check_warn "Confluence PAGE_ID и URL не найдены (Agent 7 не выполнен?)"
    else
        check_warn "CONFLUENCE_PAGE_ID и PROJECT_CONTEXT.md не найдены"
    fi
fi

# Проверка BPMN-диаграмм (drawio attachments или файлы)
BPMN_COUNT=$(find "${PROJECT_DIR}/AGENT_8_BPMN_DESIGNER" -name '*.drawio' 2>/dev/null | wc -l | tr -d ' ') || true
if [[ "${BPMN_COUNT:-0}" -gt 0 ]]; then
    check_pass "BPMN-диаграммы: ${BPMN_COUNT} файл(ов)"
else
    check_warn "BPMN-диаграммы не найдены (Agent 8 не выполнен?)"
fi

# ─── ИТОГ ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed: ${PASS}${NC}  ${YELLOW}Warnings: ${WARN}${NC}  ${RED}Failed: ${FAIL}${NC}"

if [[ $FAIL -eq 0 && $WARN -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}ГОТОВО К ПЕРЕДАЧЕ В РАЗРАБОТКУ ${ICO_OK}${NC}"
    EXIT_CODE=0
elif [[ $FAIL -eq 0 ]]; then
    echo -e "  ${YELLOW}${BOLD}ГОТОВО С ОГОВОРКАМИ (${WARN} предупреждений) ${ICO_WARN}${NC}"
    # FC-08C: Если передана причина пропуска, логируем и пропускаем
    if [[ -n "$SKIP_REASON" ]]; then
        echo -e "  ${CYAN}Пропуск предупреждений по причине: ${SKIP_REASON}${NC}"
        # Записываем в PROJECT_CONTEXT.md
        CONTEXT_FILE="${PROJECT_DIR}/PROJECT_CONTEXT.md"
        if [[ -f "$CONTEXT_FILE" ]]; then
            echo "" >> "$CONTEXT_FILE"
            echo "### $(date '+%Y-%m-%d %H:%M') — QUALITY GATE: пропуск предупреждений" >> "$CONTEXT_FILE"
            echo "**Причина:** ${SKIP_REASON}" >> "$CONTEXT_FILE"
            echo "**Предупреждений:** ${WARN}" >> "$CONTEXT_FILE"
        fi
        # Структурированный audit trail (JSONL)
        QG_AUDIT_DIR="${SCRIPT_DIR}/.audit_log"
        mkdir -p "$QG_AUDIT_DIR"
        QG_AUDIT_FILE="${QG_AUDIT_DIR}/quality_gate_overrides.jsonl"
        QG_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)
        jq -nc \
            --arg ts "$QG_TIMESTAMP" --arg prj "$PROJECT" \
            --argjson warn "$WARN" --argjson fail "$FAIL" \
            --arg reason "$SKIP_REASON" --argjson pid "$$" \
            '{timestamp:$ts, project:$prj, warnings:$warn, failed:$fail, reason:$reason, pid:$pid}' \
            >> "$QG_AUDIT_FILE"
        EXIT_CODE=0
    else
        EXIT_CODE=2
    fi
else
    echo -e "  ${RED}${BOLD}НЕ ГОТОВО — ЕСТЬ КРИТИЧЕСКИЕ ПРОБЛЕМЫ (${FAIL}) ${ICO_FAIL}${NC}"
    echo -e "  ${RED}Критические ошибки нельзя пропустить. Исправьте и повторите.${NC}"
    "${SCRIPT_DIR}/notify.sh" --level ERROR --event "quality_gate_blocked" \
        --project "$PROJECT" --message "Quality Gate blocked: ${FAIL} critical failures, ${WARN} warnings" 2>/dev/null || true
    EXIT_CODE=1
fi
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"

# Exit codes: 0=ready, 1=critical fail (cannot skip), 2=warnings (can skip with --reason)
exit $EXIT_CODE
