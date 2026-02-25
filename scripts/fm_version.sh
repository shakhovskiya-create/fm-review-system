#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# FM_VERSION.SH — Управление версиями ФМ
# ═══════════════════════════════════════════════════════════════
# Использование:
#   ./fm_version.sh diff   — сравнить две версии
#   ./fm_version.sh bump   — создать новую версию
#   ./fm_version.sh list   — список всех версий
#   ./fm_version.sh log    — история изменений
set -euo pipefail

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
    FM_DIR="${ROOT_DIR}/projects/${PROJECT}/FM_DOCUMENTS"

    echo -e "${BOLD}Проект: ${PROJECT}${NC}"
    echo ""
    
    for f in "${FM_DIR}"/*.docx "${FM_DIR}"/*.md; do
        [[ -f "$f" ]] || continue
        fname=$(basename "$f")
        fdate=$(date -r "$f" "+%Y-%m-%d %H:%M" 2>/dev/null || stat -c '%y' "$f" 2>/dev/null | cut -d. -f1)
        fsize=$(du -h "$f" | cut -f1)
        ver=$(get_fm_version "$f")
        
        # Проверяем есть ли файл изменений (FM_DOCUMENTS/ или CHANGES/)
        changes_file="${FM_DIR}/$(basename "$f" .docx)-CHANGES.md"
        changes_dir="${ROOT_DIR}/projects/${PROJECT}/CHANGES"
        has_changes=""
        [[ -f "$changes_file" ]] && has_changes=" ${ICO_DOC}"
        [[ -z "$has_changes" ]] && ls "${changes_dir}/"*CHANGES*.md &>/dev/null && has_changes=" ${ICO_DOC}"
        
        echo -e "  ${GREEN}${ver:-—}${NC}  ${fname}  ${DIM}${fdate} (${fsize})${NC}${has_changes}"
    done
    ;;

# ─── DIFF МЕЖДУ ВЕРСИЯМИ ────────────────────────────────────
diff)
    header "СРАВНЕНИЕ ВЕРСИЙ ФМ"
    PROJECT=$(select_project)
    FM_DIR="${ROOT_DIR}/projects/${PROJECT}/FM_DOCUMENTS"

    # Собираем список файлов с изменениями (FM_DOCUMENTS/ и CHANGES/)
    CHANGES_FILES=()
    for f in "${FM_DIR}"/*-CHANGES.md "${ROOT_DIR}/projects/${PROJECT}/CHANGES/"*-CHANGES.md; do
        [[ -f "$f" ]] && CHANGES_FILES+=("$f")
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
    
    # Создаем файл изменений в CHANGES/ (стандартная папка)
    CHANGES_DIR="${ROOT_DIR}/projects/${PROJECT}/CHANGES"
    mkdir -p "$CHANGES_DIR"
    BASENAME=$(basename "$FM_PATH" | sed "s/${CURRENT_VER}/${NEW_VER}/")
    CHANGES_FILE="${CHANGES_DIR}/$(echo "$BASENAME" | sed 's/\.docx$/-CHANGES.md/' | sed 's/\.md$/-CHANGES.md/')"
    
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
    
    CHANGELOG="${ROOT_DIR}/projects/${PROJECT}/CHANGELOG.md"
    if [[ -f "$CHANGELOG" ]]; then
        cat "$CHANGELOG"
    else
        warn "CHANGELOG.md не найден"
    fi
    ;;

# ─── АВТОМАТИЧЕСКИЙ ПАТЧ (FC-11C) ──────────────────────────
auto-patch)
    # Вызывается агентами при /apply для автоматического увеличения Z
    # Использование: fm_version.sh auto-patch PROJECT "описание изменений"
    PROJECT="${2:-}"
    DESCRIPTION="${3:-Автоматический патч после /apply}"

    if [[ -z "$PROJECT" ]]; then
        error "Укажите проект: fm_version.sh auto-patch PROJECT_NAME \"описание\""
        exit 1
    fi

    # Пытаемся определить текущую версию из Confluence PAGE_ID или FM_DOCUMENTS
    PAGE_ID_FILE="${ROOT_DIR}/projects/${PROJECT}/CONFLUENCE_PAGE_ID"
    FM_PATH=$(get_latest_fm "$PROJECT" 2>/dev/null) || true

    if [[ -n "$FM_PATH" ]]; then
        CURRENT_VER=$(get_fm_version "$FM_PATH")
    else
        CURRENT_VER=""
    fi

    # Если версия не определена из файла, читаем из PROJECT_CONTEXT.md
    if [[ -z "$CURRENT_VER" ]]; then
        CONTEXT_FILE="${ROOT_DIR}/projects/${PROJECT}/PROJECT_CONTEXT.md"
        if [[ -f "$CONTEXT_FILE" ]]; then
            CURRENT_VER=$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' "$CONTEXT_FILE" | tail -1)
        fi
    fi

    if [[ -z "$CURRENT_VER" ]]; then
        CURRENT_VER="v1.0.0"
        echo "Версия не определена, используется v1.0.0"
    fi

    # Парсим и увеличиваем патч
    IFS='.' read -r MAJOR MINOR PATCH <<< "${CURRENT_VER#v}"
    PATCH=$((PATCH + 1))
    NEW_VER="v${MAJOR}.${MINOR}.${PATCH}"

    # Создаем файл изменений в CHANGES/
    CHANGES_DIR="${ROOT_DIR}/projects/${PROJECT}/CHANGES"
    mkdir -p "$CHANGES_DIR"
    CHANGES_FILE="${CHANGES_DIR}/FM-${NEW_VER}-CHANGES.md"

    cat > "$CHANGES_FILE" <<EOFCHANGES
# Изменения ${NEW_VER} ($(date '+%Y-%m-%d'))

**Предыдущая версия:** ${CURRENT_VER}
**Тип:** patch (автоматический, FC-11C)

## Описание

${DESCRIPTION}
EOFCHANGES

    echo "${NEW_VER}"
    ;;

*)
    error "Неизвестная команда: ${COMMAND}"
    echo "Использование: fm_version.sh {list|diff|bump|auto-patch|log}"
    ;;
esac
