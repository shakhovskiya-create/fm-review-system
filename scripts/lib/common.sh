#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# COMMON.SH — Общие функции для всех скриптов FM Review System
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ─── ПУТИ ───────────────────────────────────────────────────
ROOT_DIR="/Users/antonsahovskii/Documents/claude-agents/fm-review-system"
SCRIPTS_DIR="${ROOT_DIR}/scripts"
TEMPLATES_DIR="${ROOT_DIR}/templates"
CONTEXT_FILE="${ROOT_DIR}/.interview_context.txt"
PIPELINE_STATE="${ROOT_DIR}/.pipeline_state.json"

# ─── ЦВЕТА ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─── ИКОНКИ ─────────────────────────────────────────────────
ICO_OK="✅"
ICO_FAIL="❌"
ICO_WARN="⚠️"
ICO_INFO="ℹ️"
ICO_WORK="🔧"
ICO_DOC="📄"
ICO_AGENT="🤖"
ICO_STAR="⭐"

# ─── УТИЛИТЫ ────────────────────────────────────────────────

header() {
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

subheader() {
    echo -e "${CYAN}─── $1 ───${NC}"
}

success() {
    echo -e "${GREEN}${ICO_OK} $1${NC}"
}

warn() {
    echo -e "${YELLOW}${ICO_WARN} $1${NC}"
}

error() {
    echo -e "${RED}${ICO_FAIL} $1${NC}"
}

info() {
    echo -e "${BLUE}${ICO_INFO} $1${NC}"
}

# ─── ПРОВЕРКИ ────────────────────────────────────────────────

check_gum() {
    if ! command -v gum &>/dev/null; then
        error "gum не установлен. Установка: brew install gum"
        exit 1
    fi
}

check_jq() {
    if ! command -v jq &>/dev/null; then
        warn "jq не установлен (brew install jq). Некоторые функции недоступны."
    fi
}

# ─── ПРОЕКТЫ ─────────────────────────────────────────────────

list_projects() {
    local projects=()
    for dir in "${ROOT_DIR}"/projects/PROJECT_*/; do
        [[ -d "$dir" ]] && projects+=("$(basename "$dir")")
    done
    printf '%s\n' "${projects[@]}"
}

select_project() {
    local projects
    projects=$(list_projects)
    if [[ -z "$projects" ]]; then
        error "Нет проектов. Создайте: ./scripts/new_project.sh"
        exit 1
    fi
    echo "$projects" | gum choose --header "Выберите проект:"
}

get_latest_fm() {
    local project_dir="${ROOT_DIR}/projects/$1/FM_DOCUMENTS"
    if [[ ! -d "$project_dir" ]]; then
        error "Папка FM_DOCUMENTS не найдена в $1"
        return 1
    fi
    # Ищем последнюю версию .docx или .md
    local latest
    latest=$(ls -t "${project_dir}"/*.docx "${project_dir}"/*.md 2>/dev/null | head -1)
    if [[ -z "$latest" ]]; then
        error "ФМ не найдена в ${project_dir}"
        return 1
    fi
    echo "$latest"
}

get_fm_version() {
    local filename
    filename=$(basename "$1")
    # Извлекаем версию из имени файла (FM-XXX-vX.Y.Z.ext)
    echo "$filename" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1
}

# ─── PIPELINE STATE ──────────────────────────────────────────

init_pipeline_state() {
    local project="$1"
    local fm_path="$2"
    cat > "${PIPELINE_STATE}" <<EOF
{
    "project": "${project}",
    "fm_path": "${fm_path}",
    "fm_version": "$(get_fm_version "$fm_path")",
    "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "current_agent": null,
    "completed_agents": [],
    "results": {}
}
EOF
}

update_pipeline_agent() {
    local agent="$1"
    local status="$2"
    if command -v jq &>/dev/null; then
        local tmp
        tmp=$(mktemp)
        jq --arg agent "$agent" --arg status "$status" \
            '.current_agent = $agent | .results[$agent] = $status' \
            "${PIPELINE_STATE}" > "$tmp" && mv "$tmp" "${PIPELINE_STATE}"
    fi
}

complete_pipeline_agent() {
    local agent="$1"
    local result_file="$2"
    if command -v jq &>/dev/null; then
        local tmp
        tmp=$(mktemp)
        jq --arg agent "$agent" --arg file "$result_file" \
            '.completed_agents += [$agent] | .results[$agent] = {"status": "done", "file": $file}' \
            "${PIPELINE_STATE}" > "$tmp" && mv "$tmp" "${PIPELINE_STATE}"
    fi
}

# ─── CLAUDE CODE INTEGRATION ────────────────────────────────

launch_claude_code() {
    local agent_file="$1"
    local command="$2"
    local context="${3:-}"

    info "Запуск Claude Code с агентом: $(basename "$agent_file")"
    
    local prompt="Прочитай и используй роль из ${agent_file}"
    
    if [[ -n "$context" ]]; then
        prompt="${prompt}\n\nКонтекст:\n${context}"
    fi
    
    prompt="${prompt}\n\n${command}"
    
    echo -e "$prompt" | pbcopy
    
    success "Промпт скопирован в буфер обмена"
    echo -e "${CYAN}  Вставьте в Claude Code (Cmd+V) и нажмите Enter${NC}"
    echo ""
}

# ─── КОНТЕКСТ ────────────────────────────────────────────────

save_context() {
    local agent="$1"
    shift
    {
        echo "КОНТЕКСТ ИНТЕРВЬЮ (${agent}):"
        echo "Дата: $(date '+%Y-%m-%d %H:%M')"
        for line in "$@"; do
            echo "- ${line}"
        done
    } > "${CONTEXT_FILE}"
    success "Контекст сохранен: ${CONTEXT_FILE}"
}

load_context() {
    if [[ -f "${CONTEXT_FILE}" ]]; then
        cat "${CONTEXT_FILE}"
    else
        echo ""
    fi
}
