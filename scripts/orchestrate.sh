#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ORCHESTRATE.SH — Мастер-оркестратор FM Review Pipeline
# ═══════════════════════════════════════════════════════════════
# Запуск: ./scripts/orchestrate.sh
#
# Единая точка входа для всех операций с ФМ:
# - Полный цикл review (Agent 1 → 2 → 4 → 5)
# - Создание новой ФМ (Agent 0)
# - Защита от замечаний (Agent 3)
# - Генерация презентации (Agent 6)
# - Управление проектами
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

header "FM REVIEW SYSTEM — Главное меню"

# ─── ГЛАВНОЕ МЕНЮ ────────────────────────────────────────────

ACTION=$(gum choose --header "Что делаем?" \
    "1. 🔄 Полный цикл review ФМ (рекомендуется)" \
    "2. 📝 Создать новую ФМ (Agent 0)" \
    "3. 🔍 Аудит ФМ (Agent 1)" \
    "4. 👤 Симуляция ролей (Agent 2)" \
    "5. 🛡️ Защита от замечаний (Agent 3)" \
    "6. 🧪 Генерация тестов (Agent 4)" \
    "7. 🏗️ Архитектура + ТЗ (Agent 5)" \
    "8. 📊 Презентация для стейкхолдеров (Agent 6)" \
    "9. 🔄 Публикация в Confluence (Agent 7)" \
    "10. 🎨 BPMN-диаграммы в Confluence (Agent 8)" \
    "11. 📁 Управление проектами" \
    "12. 📋 Статус pipeline" \
    "13. ▶️ Продолжить pipeline (resume)" \
    "14. 🔑 Проверка секретов")

case "$ACTION" in

# ═══════════════════════════════════════════════════════════════
# 1. ПОЛНЫЙ ЦИКЛ REVIEW
# ═══════════════════════════════════════════════════════════════
"1."*)
    header "ПОЛНЫЙ ЦИКЛ REVIEW"
    
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    FM_VER=""
    [[ -n "$FM_PATH" ]] && FM_VER=$(get_fm_version "$FM_PATH")
    
    info "Проект: ${PROJECT}"
    [[ -n "$FM_PATH" ]] && info "ФМ: $(basename "$FM_PATH") (${FM_VER})" || info "ФМ: Confluence (PAGE_ID из проекта)"
    echo ""
    
    # Выбор этапов
    STAGES=$(gum choose --no-limit --header "Какие этапы включить? (Space для выбора)" \
        "Agent 1: Аудит (бизнес + 1С) ⭐" \
        "Agent 2: Симуляция ролей" \
        "Agent 4: Тест-кейсы" \
        "Agent 5: Архитектура + ТЗ" \
        "Agent 6: Презентация" \
        "Agent 7: Публикация в Confluence" \
        "Agent 8: BPMN в Confluence")
    
    init_pipeline_state "$PROJECT" "${FM_PATH:-Confluence}"
    
    echo ""
    subheader "PIPELINE"
    
    # Определяем порядок
    PIPELINE_ORDER=("AGENT_1" "AGENT_2" "AGENT_4" "AGENT_5" "AGENT_7" "AGENT_8" "AGENT_6")
    PIPELINE_NAMES=("Аудит" "Симуляция" "Тест-кейсы" "Архитектура" "Публикация" "BPMN" "Презентация")
    PIPELINE_FILES=("AGENT_1_ARCHITECT" "AGENT_2_ROLE_SIMULATOR" "AGENT_4_QA_TESTER" "AGENT_5_TECH_ARCHITECT" "AGENT_7_PUBLISHER" "AGENT_8_BPMN_DESIGNER" "AGENT_6_PRESENTER")
    
    for i in "${!PIPELINE_ORDER[@]}"; do
        agent="${PIPELINE_NAMES[$i]}"
        agent_file="${ROOT_DIR}/agents/${PIPELINE_FILES[$i]}.md"
        
        if echo "$STAGES" | grep -q "${agent}"; then
            echo -e "${MAGENTA}  [$((i+1))] ${agent}${NC} — ожидание"
        else
            echo -e "${DIM}  [$((i+1))] ${agent} — пропущен${NC}"
        fi
    done
    
    echo ""
    info "Pipeline инициализирован."
    info "Для каждого этапа будет подготовлен промпт с контекстом предыдущих этапов."
    echo ""
    
    # Запуск первого активного этапа
    for i in "${!PIPELINE_ORDER[@]}"; do
        agent="${PIPELINE_NAMES[$i]}"
        agent_md="${PIPELINE_FILES[$i]}.md"
        
        if echo "$STAGES" | grep -q "${agent}"; then
            subheader "Запуск: ${agent}"
            
            # Собираем контекст из предыдущих этапов
            PREV_CONTEXT=""
            for dir in "${ROOT_DIR}/projects/${PROJECT}"/AGENT_*/; do
                [[ -d "$dir" ]] || continue
                for f in "$dir"/*.md; do
                    [[ -f "$f" ]] || continue
                    PREV_CONTEXT="${PREV_CONTEXT}\nФайл предыдущего анализа: $f"
                done
            done
            
            FULL_CONTEXT="Проект: ${PROJECT}
ФМ: ${FM_PATH}
Версия: ${FM_VER}
${PREV_CONTEXT}"
            
            case "${agent_md}" in
                AGENT_7_PUBLISHER.md) CMD="/publish" ;;
                AGENT_8_BPMN_DESIGNER.md) CMD="/bpmn" ;;
                AGENT_1_ARCHITECT.md) CMD="/audit" ;;
                AGENT_2_ROLE_SIMULATOR.md) CMD="/simulate-all" ;;
                AGENT_4_QA_TESTER.md) CMD="/generate-all" ;;
                AGENT_5_TECH_ARCHITECT.md) CMD="/full" ;;
                AGENT_6_PRESENTER.md) CMD="/auto" ;;
                *) CMD="/auto" ;;
            esac

            # FC-08C: Обязательный Quality Gate перед Agent 7 (после Agent 5)
            if [[ "${agent_md}" == "AGENT_7_PUBLISHER.md" ]]; then
                subheader "QUALITY GATE (FC-08C): обязательная проверка перед публикацией"
                QG_EXIT=0
                bash "${SCRIPTS_DIR}/quality_gate.sh" "${PROJECT}" || QG_EXIT=$?

                if [[ $QG_EXIT -eq 1 ]]; then
                    error "Quality Gate: КРИТИЧЕСКИЕ ОШИБКИ. Публикация заблокирована."
                    error "Исправьте ошибки и запустите pipeline повторно."
                    exit 1
                elif [[ $QG_EXIT -eq 2 ]]; then
                    warn "Quality Gate: есть предупреждения."
                    if [[ -n "${AUTONOMOUS:-}" ]]; then
                        warn "Автономный режим: предупреждения пропускаются автоматически."
                        bash "${SCRIPTS_DIR}/quality_gate.sh" "${PROJECT}" --reason "Автопропуск в автономном режиме" >/dev/null 2>&1 || true
                    else
                        if gum confirm "Продолжить публикацию с предупреждениями?"; then
                            REASON=$(gum input --placeholder "Причина пропуска предупреждений..." --header "Укажите причину (обязательно):")
                            if [[ -z "$REASON" ]]; then
                                error "Причина пропуска не указана. Публикация отменена."
                                continue
                            fi
                            bash "${SCRIPTS_DIR}/quality_gate.sh" "${PROJECT}" --reason "$REASON" >/dev/null 2>&1 || true
                            success "Предупреждения пропущены. Причина записана."
                        else
                            warn "Публикация отменена. Исправьте предупреждения."
                            continue
                        fi
                    fi
                else
                    success "Quality Gate: все проверки пройдены."
                fi
                echo ""
            fi

            # Автономный режим: вызов через Claude Code SDK (run_agent.py)
            # FC-22: перенесен из experimental/ в scripts/, использует claude-code-sdk
            if [[ -n "${AUTONOMOUS:-}" ]]; then
                AGENT_NUM=1
                case "${agent_md}" in
                    AGENT_0_CREATOR.md) AGENT_NUM=0 ;;
                    AGENT_1_ARCHITECT.md) AGENT_NUM=1 ;;
                    AGENT_2_ROLE_SIMULATOR.md) AGENT_NUM=2 ;;
                    AGENT_3_DEFENDER.md) AGENT_NUM=3 ;;
                    AGENT_4_QA_TESTER.md) AGENT_NUM=4 ;;
                    AGENT_5_TECH_ARCHITECT.md) AGENT_NUM=5 ;;
                    AGENT_6_PRESENTER.md) AGENT_NUM=6 ;;
                    AGENT_7_PUBLISHER.md) AGENT_NUM=7 ;;
                    AGENT_8_BPMN_DESIGNER.md) AGENT_NUM=8 ;;
                esac
                export FM_PATH FM_VER
                if python3 "${SCRIPTS_DIR}/run_agent.py" --project "${PROJECT}" --agent "${AGENT_NUM}" --command "${CMD}"; then
                    complete_pipeline_agent "${PIPELINE_ORDER[$i]}" "done"
                    success "${agent} завершен (autonomous)"
                else
                    warn "${agent} завершился с ошибкой"
                fi
            else
                launch_claude_code "${ROOT_DIR}/agents/${agent_md}" "$CMD" "$FULL_CONTEXT"
                gum confirm "Этап '${agent}' завершен?" && {
                    complete_pipeline_agent "${PIPELINE_ORDER[$i]}" "done"
                    success "${agent} завершен"
                } || {
                    warn "${agent} пропущен"
                }
            fi
            echo ""
        fi
    done
    
    success "Pipeline завершен!"
    ;;

# ═══════════════════════════════════════════════════════════════
# 2. СОЗДАНИЕ НОВОЙ ФМ
# ═══════════════════════════════════════════════════════════════
"2."*)
    header "СОЗДАНИЕ НОВОЙ ФМ (Agent 0)"
    
    # Спрашиваем: новый проект или существующий?
    PROJ_ACTION=$(gum choose --header "Куда сохранять ФМ?" \
        "1. Создать новый проект" \
        "2. Добавить в существующий")
    
    if [[ "$PROJ_ACTION" == "1."* ]]; then
        bash "${SCRIPTS_DIR}/new_project.sh"
        PROJECT=$(list_projects | tail -1)
    else
        PROJECT=$(select_project)
    fi
    export PROJECT
    
    # Запускаем интервью Agent 0
    bash "${SCRIPTS_DIR}/agent0_new.sh"
    
    # Добавляем контекст проекта
    CONTEXT=$(load_context)
    CONTEXT="${CONTEXT}\nПроект: ${PROJECT}"
    echo -e "$CONTEXT" > "$(get_context_file)"
    
    launch_claude_code "${ROOT_DIR}/agents/AGENT_0_CREATOR.md" "/new" "$CONTEXT"
    ;;

# ═══════════════════════════════════════════════════════════════
# 3-7. ОТДЕЛЬНЫЕ АГЕНТЫ
# ═══════════════════════════════════════════════════════════════
"3."*)
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    bash "${SCRIPTS_DIR}/agent1_audit.sh"
    CONTEXT=$(load_context)
    CONTEXT="${CONTEXT}\nПроект: ${PROJECT}\nФМ: ${FM_PATH}"
    launch_claude_code "${ROOT_DIR}/agents/AGENT_1_ARCHITECT.md" "/audit" "$CONTEXT"
    ;;

"4."*)
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    bash "${SCRIPTS_DIR}/agent2_simulate.sh"
    CONTEXT=$(load_context)
    launch_claude_code "${ROOT_DIR}/agents/AGENT_2_ROLE_SIMULATOR.md" "/simulate-all" "$CONTEXT"
    ;;

"5."*)
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    bash "${SCRIPTS_DIR}/agent3_defend.sh"
    CONTEXT=$(load_context)
    launch_claude_code "${ROOT_DIR}/agents/AGENT_3_DEFENDER.md" "/respond-all" "$CONTEXT"
    ;;

"6."*)
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    bash "${SCRIPTS_DIR}/agent4_test.sh"
    CONTEXT=$(load_context)
    launch_claude_code "${ROOT_DIR}/agents/AGENT_4_QA_TESTER.md" "/generate-all" "$CONTEXT"
    ;;

"7."*)
    PROJECT=$(select_project)
    export PROJECT
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
    bash "${SCRIPTS_DIR}/agent5_architect.sh"
    CONTEXT=$(load_context)
    launch_claude_code "${ROOT_DIR}/agents/AGENT_5_TECH_ARCHITECT.md" "/full" "$CONTEXT"
    ;;

# ═══════════════════════════════════════════════════════════════
# 8. ПРЕЗЕНТАЦИЯ
# ═══════════════════════════════════════════════════════════════
"8."*)
    header "ПРЕЗЕНТАЦИЯ ДЛЯ СТЕЙКХОЛДЕРОВ (Agent 6)"
    PROJECT=$(select_project)
    
    AUDIENCE=$(gum choose --header "Для кого презентация?" \
        "1. Заказчик (бизнес-язык, ROI, сроки) ⭐" \
        "2. Руководство (высокоуровнево, стратегия)" \
        "3. Разработчики (техника, архитектура, оценка)" \
        "4. Все стейкхолдеры (универсальная)")
    
    FORMAT=$(gum choose --header "В каком формате?" \
        "1. Markdown отчет" \
        "2. Confluence страница (через API)" \
        "3. Miro доска (через MCP)" \
        "4. PPTX презентация")
    
    CONTEXT="Проект: ${PROJECT}
Аудитория: ${AUDIENCE}
Формат: ${FORMAT}"
    
    launch_claude_code "${ROOT_DIR}/agents/AGENT_6_PRESENTER.md" "/present" "$CONTEXT"
    ;;

# ═══════════════════════════════════════════════════════════════
# 9. ПУБЛИКАЦИЯ В CONFLUENCE (Agent 7 Publisher)
# ═══════════════════════════════════════════════════════════════
"9."*)
    header "ПУБЛИКАЦИЯ В CONFLUENCE (Agent 7)"
    PROJECT=$(select_project)
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null || true)
    
    PUBLISH_ACTION=$(gum choose --header "Что делаем?" \
        "1. Публикация/обновление страницы ФМ в Confluence ⭐" \
        "2. Прочитать ФМ из Confluence" \
        "3. Валидация страницы в Confluence" \
        "4. Отчет о публикации")
    
    CONTEXT="Проект: ${PROJECT}
ФМ: ${FM_PATH}
Действие: ${PUBLISH_ACTION}"
    
    case "$PUBLISH_ACTION" in
        "1."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_7_PUBLISHER.md" "/publish" "$CONTEXT" ;;
        "2."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_7_PUBLISHER.md" "/read" "$CONTEXT" ;;
        "3."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_7_PUBLISHER.md" "/verify" "$CONTEXT" ;;
        "4."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_7_PUBLISHER.md" "/report" "$CONTEXT" ;;
    esac
    ;;

# ═══════════════════════════════════════════════════════════════
# 10. BPMN-ДИАГРАММЫ В CONFLUENCE (Agent 8)
# ═══════════════════════════════════════════════════════════════
"10."*)
    header "BPMN-ДИАГРАММЫ В CONFLUENCE (Agent 8)"
    PROJECT=$(select_project)
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null || true)
    
    BPMN_ACTION=$(gum choose --header "Что делаем?" \
        "1. Создать BPMN-диаграмму из ФМ ⭐" \
        "2. Обновить существующую BPMN" \
        "3. Валидация диаграммы" \
        "4. Опубликовать в Confluence")
    
    CONTEXT="Проект: ${PROJECT}
ФМ: ${FM_PATH}
Действие: ${BPMN_ACTION}"
    
    case "$BPMN_ACTION" in
        "1."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_8_BPMN_DESIGNER.md" "/bpmn" "$CONTEXT" ;;
        "2."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_8_BPMN_DESIGNER.md" "/bpmn-update" "$CONTEXT" ;;
        "3."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_8_BPMN_DESIGNER.md" "/bpmn-validate" "$CONTEXT" ;;
        "4."*) launch_claude_code "${ROOT_DIR}/agents/AGENT_8_BPMN_DESIGNER.md" "/bpmn-publish" "$CONTEXT" ;;
    esac
    ;;

# ═══════════════════════════════════════════════════════════════
# 11. УПРАВЛЕНИЕ ПРОЕКТАМИ
# ═══════════════════════════════════════════════════════════════
"11."*)
    header "УПРАВЛЕНИЕ ПРОЕКТАМИ"
    
    PROJ_ACTION=$(gum choose --header "Что делаем?" \
        "1. Создать новый проект" \
        "2. Версия ФМ: diff между версиями" \
        "3. Версия ФМ: создать новую версию" \
        "4. Публикация ФМ в Confluence" \
        "5. Публикация BPMN в Confluence" \
        "6. Список проектов и статусы")

    case "$PROJ_ACTION" in
        "1."*) bash "${SCRIPTS_DIR}/new_project.sh" ;;
        "2."*) bash "${SCRIPTS_DIR}/fm_version.sh" diff ;;
        "3."*) bash "${SCRIPTS_DIR}/fm_version.sh" bump ;;
        "4."*)
            # Публикация ФМ в Confluence (legacy: из docx; Confluence-only: обновление через Agent 7 или --from-file)
            PROJECT=$(select_project)
            export PROJECT
            FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true
            if [[ -n "$FM_PATH" ]]; then
                python3 "${SCRIPTS_DIR}/publish_to_confluence.py" "$FM_PATH"
            else
                info "ФМ в файлах не найдена (режим Confluence-only). Обновление тела страницы: Agent 7 в Claude Code или: python3 scripts/publish_to_confluence.py --from-file <body.xhtml> --project $PROJECT"
            fi
            ;;
        "5."*)
            # Публикация BPMN через Agent 8
            PROJECT=$(select_project)
            launch_claude_code "${ROOT_DIR}/agents/AGENT_8_BPMN_DESIGNER.md" "/bpmn-publish" "Проект: ${PROJECT}"
            ;;
        "6."*)
            header "ПРОЕКТЫ"
            for dir in "${ROOT_DIR}"/projects/PROJECT_*/; do
                [[ -d "$dir" ]] || continue
                proj=$(basename "$dir")
                fm=$(get_latest_fm "$proj" 2>/dev/null || echo "нет ФМ")
                ver=$(get_fm_version "$fm" 2>/dev/null || echo "—")
                
                # Считаем результаты агентов
                agent_count=0
                for agent_dir in "${dir}"/AGENT_*/; do
                    [[ -d "$agent_dir" ]] && files=$(ls "$agent_dir"/*.md 2>/dev/null | wc -l)
                    agent_count=$((agent_count + files))
                done
                
                echo -e "  ${BOLD}${proj}${NC} ${DIM}(${ver})${NC} — ${agent_count} отчетов"
            done
            ;;
    esac
    ;;

# ═══════════════════════════════════════════════════════════════
# 12. СТАТУС PIPELINE (per-project, AG-14)
# ═══════════════════════════════════════════════════════════════
"12."*)
    header "СТАТУС PIPELINE"
    PROJECT=$(select_project)
    PIPELINE_STATE=$(get_pipeline_state_file "$PROJECT")
    if [[ -f "${PIPELINE_STATE}" ]] && command -v jq &>/dev/null; then
        jq '.' "${PIPELINE_STATE}"
    elif [[ -f "${PIPELINE_STATE}" ]]; then
        cat "${PIPELINE_STATE}"
    else
        warn "Pipeline не инициализирован для ${PROJECT}. Запустите полный цикл review для этого проекта."
    fi
    ;;

# ═══════════════════════════════════════════════════════════════
# 13. ПРОДОЛЖИТЬ PIPELINE (resume)
# ═══════════════════════════════════════════════════════════════
"13."*)
    header "ПРОДОЛЖИТЬ PIPELINE (RESUME)"
    PROJECT=$(select_project)
    PIPELINE_STATE=$(get_pipeline_state_file "$PROJECT")

    if [[ ! -f "${PIPELINE_STATE}" ]]; then
        error "Чекпоинт не найден для ${PROJECT}. Нечего продолжать."
        exit 1
    fi

    if command -v jq &>/dev/null; then
        completed=$(jq -r '.completed_steps | length' "$PIPELINE_STATE" 2>/dev/null) || completed=0
        failed=$(jq -r '.failed_steps | length' "$PIPELINE_STATE" 2>/dev/null) || failed=0
        cost=$(jq -r '.total_cost_usd' "$PIPELINE_STATE" 2>/dev/null) || cost="?"
        info "Завершено шагов: ${completed}, Неудавшихся: ${failed}, Стоимость: \$${cost}"
    fi

    if gum confirm "Продолжить pipeline с последнего чекпоинта?"; then
        python3 "${SCRIPTS_DIR}/run_agent.py" --pipeline --project "${PROJECT}" --resume
    else
        info "Отменено."
    fi
    ;;

# ═══════════════════════════════════════════════════════════════
# 14. ПРОВЕРКА СЕКРЕТОВ
# ═══════════════════════════════════════════════════════════════
"14."*)
    bash "${SCRIPTS_DIR}/check-secrets.sh" --verbose
    ;;

*)
    error "Неизвестное действие"
    ;;
esac
