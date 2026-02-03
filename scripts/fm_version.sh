#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# FM_VERSION.SH — Управление версиями ФМ
# ═══════════════════════════════════════════════════════════════
# Использование:
#   ./fm_version.sh diff   — сравнить две версии
#   ./fm_version.sh bump   — создать новую версию
#   ./fm_version.sh list   — список всех версий
#   ./fm_version.sh log    — история изменений

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
check_gum

COMMAND="${1:-menu}"

case "$COMMAND" in
# ─── МЕНЮ ───────────────────────────────────────────────────
menu)
    COMMAND=$(gum choose --header "Управление версиями ФМ:" \
        "list — Список версий" \
        "diff — Сравнить версии" \
        "bump — Создать новую версию" \
        "log — История изменений")
    COMMAND=$(echo "$COMMAND" | cut -d' ' -f1)
    exec "$0" "$COMMAND"
    ;;

# ─── СПИСОК ВЕРСИЙ ──────────────────────────────────────────
list)
    header "ВЕРСИИ ФМ"
    PROJECT=$(select_project)
    FM_DIR="${ROOT_DIR}/${PROJECT}/FM_DOCUMENTS"
    
    echo -e "${BOLD}Проект: ${PROJECT}${NC}"
    echo ""
    
    for f in "${FM_DIR}"/*.docx "${FM_DIR}"/*.md; do
        [[ -f "$f" ]] || continue
        fname=$(basename "$f")
        fdate=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$f" 2>/dev/null || date -r "$f" "+%Y-%m-%d %H:%M")
        fsize=$(du -h "$f" | cut -f1)
        ver=$(get_fm_version "$f")
        
        # Проверяем есть ли файл изменений
        changes_file="${FM_DIR}/$(basename "$f" .docx)-CHANGES.md"
        has_changes=""
        [[ -f "$changes_file" ]] && has_changes=" ${ICO_DOC}"
        
        echo -e "  ${GREEN}${ver:-—}${NC}  ${fname}  ${DIM}${fdate} (${fsize})${NC}${has_changes}"
    done
    ;;

# ─── DIFF МЕЖДУ ВЕРСИЯМИ ────────────────────────────────────
diff)
    header "СРАВНЕНИЕ ВЕРСИЙ ФМ"
    PROJECT=$(select_project)
    FM_DIR="${ROOT_DIR}/${PROJECT}/FM_DOCUMENTS"
    
    # Собираем список файлов с изменениями
    CHANGES_FILES=()
    for f in "${FM_DIR}"/*-CHANGES.md; do
        [[ -f "$f" ]] && CHANGES_FILES+=("$(basename "$f")")
    done
    
    if [[ ${#CHANGES_FILES[@]} -eq 0 ]]; then
        warn "Нет файлов изменений (*-CHANGES.md)"
        info "Файлы изменений создаются командой /apply в агентах"
        exit 0
    fi
    
    SELECTED=$(printf '%s\n' "${CHANGES_FILES[@]}" | gum choose --header "Какие изменения показать?")
    
    echo ""
    cat "${FM_DIR}/${SELECTED}"
    ;;

# ─── СОЗДАНИЕ НОВОЙ ВЕРСИИ ──────────────────────────────────
bump)
    header "СОЗДАНИЕ НОВОЙ ВЕРСИИ ФМ"
    PROJECT=$(select_project)
    FM_PATH=$(get_latest_fm "$PROJECT")
    CURRENT_VER=$(get_fm_version "$FM_PATH")
    
    info "Текущая версия: ${CURRENT_VER}"
    
    BUMP_TYPE=$(gum choose --header "Тип изменения:" \
        "patch — Исправления, опечатки (X.Y.Z+1)" \
        "minor — Новые требования, разделы (X.Y+1.0)" \
        "major — Существенный пересмотр (X+1.0.0)")
    
    BUMP=$(echo "$BUMP_TYPE" | cut -d' ' -f1)
    
    # Парсим версию
    IFS='.' read -r MAJOR MINOR PATCH <<< "${CURRENT_VER#v}"
    
    case "$BUMP" in
        patch) PATCH=$((PATCH + 1)) ;;
        minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
        major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    esac
    
    NEW_VER="v${MAJOR}.${MINOR}.${PATCH}"
    
    # Описание изменений
    DESCRIPTION=$(gum write --header "Опишите изменения (Ctrl+D для завершения):" \
        --placeholder "Что изменилось в этой версии...")
    
    success "Новая версия: ${NEW_VER}"
    info "Копируйте текущую ФМ и внесите изменения через агента"
    
    # Создаем файл изменений
    FM_DIR="${ROOT_DIR}/${PROJECT}/FM_DOCUMENTS"
    BASENAME=$(basename "$FM_PATH" | sed "s/${CURRENT_VER}/${NEW_VER}/")
    CHANGES_FILE="${FM_DIR}/$(echo "$BASENAME" | sed 's/\.docx$/-CHANGES.md/' | sed 's/\.md$/-CHANGES.md/')"
    
    cat > "$CHANGES_FILE" <<EOF
# Изменения ${NEW_VER} ($(date '+%Y-%m-%d'))

**Предыдущая версия:** ${CURRENT_VER}
**Тип:** ${BUMP}

## Описание

${DESCRIPTION}

## Правки

_Заполняется агентом при /apply_
EOF
    
    success "Файл изменений: ${CHANGES_FILE}"
    ;;

# ─── ИСТОРИЯ ────────────────────────────────────────────────
log)
    header "ИСТОРИЯ ИЗМЕНЕНИЙ"
    PROJECT=$(select_project)
    
    CHANGELOG="${ROOT_DIR}/${PROJECT}/CHANGELOG.md"
    if [[ -f "$CHANGELOG" ]]; then
        cat "$CHANGELOG"
    else
        warn "CHANGELOG.md не найден"
    fi
    ;;

*)
    error "Неизвестная команда: ${COMMAND}"
    echo "Использование: fm_version.sh {list|diff|bump|log}"
    ;;
esac
