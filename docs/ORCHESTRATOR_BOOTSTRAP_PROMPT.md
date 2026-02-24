# Промпт для внедрения AI-оркестратора в новый проект

> Скопируй этот промпт в Claude Code в целевом проекте. Claude сам создаст все файлы, хуки, labels и проверит что всё работает.
> Референсный проект: `fm-review-system` (github.com/shakhovskiya-create/fm-review-system)

---

## ПРОМПТ (копировать целиком)

```
Внедри в этот проект систему AI-оркестрации по образцу fm-review-system. Ниже полная спецификация — что создать, как настроить, как проверить. Делай всё последовательно, каждый шаг проверяй. НЕ сдавай результат без smoke-тестов и зелёного CI.

## 1. CLAUDE.md (корень проекта)

Создай CLAUDE.md (макс 50 строк). Обязательные секции:

```markdown
# CLAUDE.md - <НАЗВАНИЕ_ПРОЕКТА>

> <Краткое описание проекта — 1 строка>

## Роль

**Я — AI-оркестратор проекта <НАЗВАНИЕ>.** Задачи:
1. Маршрутизация запросов к субагентам
2. Управление инфраструктурой: хуки, скрипты, CI/CD, тесты

**Context pollution prevention:** НЕ читай файлы с отчётами/артефактами агентов напрямую — делегируй субагенту. Большие отчёты забивают контекстное окно.

## Правила

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `.claude/rules/common-rules.md`.

## Задачи

GitHub Issues + Kanban (GitHub Project). Sprint dashboard: `bash scripts/gh-tasks.sh sprint`
```

## 2. .claude/settings.json (хуки)

Создай `.claude/settings.json` с ПОЛНЫМ набором хуков. Для каждого хука — отдельный .sh скрипт в `.claude/hooks/`.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-start.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "matcher": "agent-.*",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/subagent-start.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-secrets.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-secrets.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "agent-.*",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/subagent-stop.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/precompact.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-stop.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

## 3. Хуки — скрипты (.claude/hooks/)

Создай ВСЕ 6 скриптов ниже. Каждый — `chmod +x`. Каждый начинается с `set -euo pipefail`.

### 3.1 session-start.sh (SessionStart)
Назначение: при старте сессии показать оркестратору контекст + открытые GitHub Issues.

```bash
#!/bin/bash
# SessionStart: контекст проекта + GitHub Issues оркестратора
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "=== $(basename "$PROJECT_DIR"): Session Start ==="

# Определяем OWNER/REPO из git remote
REPO_URL=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null || echo "")
if [[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
  GH_OWNER="${BASH_REMATCH[1]}"
  GH_REPO="${BASH_REMATCH[2]}"

  # Открытые задачи оркестратора
  issues=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
    --label "agent:orchestrator" --state open --limit 10 \
    --json number,title,labels \
    --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("sprint:"))] | join(", "))]"' 2>/dev/null || true)
  if [ -n "$issues" ]; then
    echo "GitHub Issues (orchestrator):"
    echo "$issues"
  fi

  # Sprint summary
  sprint_info=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
    --state open --limit 100 --json labels \
    --jq '[.[].labels[].name | select(startswith("sprint:"))] | group_by(.) | map("\(.[0]): \(length) open") | .[]' 2>/dev/null || true)
  [ -n "$sprint_info" ] && echo "Sprints: $sprint_info"
fi

echo "========================================="
exit 0
```

### 3.2 subagent-start.sh (SubagentStart)
Назначение: при старте субагента инжектировать его GitHub Issues.

```bash
#!/bin/bash
# SubagentStart: инжекция GitHub Issues для агента
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Определяем OWNER/REPO
REPO_URL=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null || echo "")
[[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]] || exit 0
GH_OWNER="${BASH_REMATCH[1]}"
GH_REPO="${BASH_REMATCH[2]}"

# Извлекаем имя агента из stdin
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
[ -z "$AGENT_NAME" ] && exit 0

# Маппинг имени: agent-backend -> backend, helper-* -> orchestrator
AGENT_LABEL=""
case "$AGENT_NAME" in
  agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
  helper-*) AGENT_LABEL="orchestrator" ;;
  *)        AGENT_LABEL="$AGENT_NAME" ;;
esac

issues=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
  --label "agent:${AGENT_LABEL}" --state open --limit 10 \
  --json number,title,labels \
  --jq '.[] | "#\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("priority:"))] | join(", "))]"' 2>/dev/null || true)

if [ -n "$issues" ]; then
  echo ""
  echo "GitHub Issues (назначены тебе):"
  echo "$issues"
  echo "ОБЯЗАТЕЛЬНО: прочитай issues, возьми приоритетную (gh-tasks.sh start N), по завершении закрой (gh-tasks.sh done N)"
fi

exit 0
```

### 3.3 block-secrets.sh (PreToolUse: Write, Edit)
Назначение: блокирует запись секретов (API-ключей, токенов) в файлы.

```bash
#!/bin/bash
# PreToolUse: блокировка записи секретов в файлы
set -euo pipefail

INPUT=$(cat)
TEXT=$(echo "$INPUT" | jq -r '(.tool_input.content // "") + "\n" + (.tool_input.new_string // "")' 2>/dev/null || echo "")
[ -z "$TEXT" ] && exit 0

# Паттерны: Anthropic (sk-ant-), GitHub (ghp_/gho_/ghs_), Slack (xox-), AWS (AKIA), PEM keys
# Минимальная длина после префикса предотвращает false positive на коротких примерах
if echo "$TEXT" | grep -qE '(sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|xox[bpras]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)'; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // "unknown"' 2>/dev/null || echo "unknown")
  echo "BLOCKED: Обнаружен секрет в записи в файл '$FILE_PATH'. Секреты хранить в env/secrets manager, не в файлах." >&2
  exit 2
fi

exit 0
```

### 3.4 subagent-stop.sh (SubagentStop)
Назначение: предупреждение если агент не закрыл свои issues.

```bash
#!/bin/bash
# SubagentStop: проверка что агент обновил свои GitHub Issues
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REPO_URL=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null || echo "")
[[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]] || exit 0
GH_OWNER="${BASH_REMATCH[1]}"
GH_REPO="${BASH_REMATCH[2]}"

INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
[ -z "$AGENT_NAME" ] && exit 0

AGENT_LABEL=""
case "$AGENT_NAME" in
  agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
  helper-*) AGENT_LABEL="orchestrator" ;;
  *)        AGENT_LABEL="$AGENT_NAME" ;;
esac

open_issues=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
  --label "agent:${AGENT_LABEL}" --label "status:in-progress" \
  --state open --json number --jq 'length' 2>/dev/null || echo "0")

if [ "$open_issues" -gt 0 ] 2>/dev/null; then
  echo "WARNING: У агента ${AGENT_NAME} есть ${open_issues} незакрытых issues (status:in-progress)."
  echo "Закрой: bash scripts/gh-tasks.sh done <N> --comment 'Результат + DoD'"
  echo ""
  echo "ОБЯЗАТЕЛЬНЫЙ формат --comment (DoD):"
  echo "  ## Результат"
  echo "  [Что сделано]"
  echo "  ## Было -> Стало"
  echo "  - [Изменение]"
  echo "  ## DoD"
  echo "  - [x] Tests pass"
  echo "  - [x] No regression"
  echo "  - [x] AC met"
  echo "  - [x] Artifacts: [файлы]"
  echo "  - [x] Docs updated (N/A)"
  echo "  - [x] No hidden debt"
fi

exit 0
```

### 3.5 precompact.sh (PreCompact — Context Monitor)
Назначение: предупреждение при переполнении контекстного окна.

```bash
#!/bin/bash
# PreCompact: предупреждение о переполнении контекста
set -euo pipefail

echo "=== Context Monitor: компакция запущена ==="
echo ""
echo "WARNING: Контекстное окно переполнено."
echo "ДЕЙСТВИЯ:"
echo "  1) Зафиксируй текущий прогресс (commit или комментарий в issue)"
echo "  2) Обнови GitHub Issues — закрой выполненные, добавь комментарии к незавершённым"
echo "  3) Если задача большая — сделай commit и сообщи пользователю"
echo ""
echo "========================================="
exit 0
```

### 3.6 session-stop.sh (Stop)
Назначение: логирование завершения сессии.

```bash
#!/bin/bash
# Stop: логирование завершения сессии
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "$(date -Iseconds) | session_end" >> "$LOG_DIR/sessions.log"
exit 0
```

## 4. scripts/gh-tasks.sh (GitHub Issues CLI)

Создай `scripts/gh-tasks.sh` (chmod +x). Скрипт автоматически определяет OWNER/REPO из git remote.

ВАЖНО: вместо хардкода REPO, определяй динамически:

```bash
# В начале скрипта:
REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
  REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  PROJECT_OWNER="${BASH_REMATCH[1]}"
else
  echo "ERROR: не могу определить GitHub repo из git remote" >&2
  exit 1
fi
```

Команды которые ОБЯЗАН поддерживать gh-tasks.sh:
- `create --title "..." --agent <name> --sprint <N> --body "..." [--priority P] [--type T]` — **--body ОБЯЗАТЕЛЕН** (образ результата + AC)
- `start <issue_number>` — status:planned -> status:in-progress + Kanban "In Progress"
- `done <issue_number> --comment "..."` — **--comment ОБЯЗАТЕЛЕН** (результат + DoD checklist). Закрыть + Kanban "Done"
- `block <issue_number> --reason "..."` — status:blocked
- `list [--agent X] [--sprint N] [--status S]`
- `my-tasks --agent <name>` — открытые задачи агента
- `sprint [N]` — dashboard (In Progress / Planned / Blocked / Done / Progress: X/Y)

Каждая команда create/start/done синхронизирует статус на Kanban-доске (GitHub Project).

Enforcement (ЖЁСТКО):
- `create` без `--body` → exit 1, показать шаблон: `## Образ результата\n## Acceptance Criteria\n- [ ] AC1`
- `done` без `--comment` → exit 1, показать шаблон: `## Результат\n## DoD\n- [x] Tests pass\n- [x] AC met`

Внутренние функции:
- `_remove_status_labels` — убирает все status:* метки
- `_sync_project_status` — обновляет колонку на Kanban через `gh project item-edit`
- `_validate_artifacts` — cross-check: сверяет `git diff HEAD~1 --name-only` с текстом `--comment`, выводит WARNING для файлов не упомянутых в Artifacts (не блокирует, но ловит checkbox-ticking)

При `create` — автоматически `gh project item-add` в Project board.

Используй референс: github.com/shakhovskiya-create/fm-review-system/blob/main/scripts/gh-tasks.sh

## 5. .claude/rules/common-rules.md

Создай файл с правилами. Claude Code автоматически загружает файлы из `.claude/rules/`.

Обязательные правила (каждое — отдельная секция):

### Smoke-тесты перед сдачей
НЕ сдавать результат без smoke-тестов. После ЛЮБЫХ изменений:
1. Запустить изменённые скрипты — проверить exit code
2. Запустить тесты проекта (pytest / jest / go test) — 0 failures
3. После `git push` — дождаться CI: `gh run watch --exit-status`. CI ДОЛЖЕН быть зелёный
4. При ошибке — исправить и повторить. НЕ сообщать "готово" пока CI не зелёный

### Deviation Rules (отклонение от плана)
4 уровня:
1. Косметика (пробелы, форматирование) — исправить молча
2. Мелкие улучшения — исправить, пометить
3. Изменение scope — СПРОСИТЬ пользователя
4. Противоречие плану — STOP, не продолжать

### GitHub Issues — persistent task tracking (ОБЯЗАТЕЛЬНО)
**Первое действие агента:**
1. SubagentStart-хук инжектирует назначенные issues — прочитать их
2. Если есть issue со status:in-progress — продолжить эту задачу
3. Если есть issues со status:planned — взять приоритетную, выполнить `bash scripts/gh-tasks.sh start <N>`

**Во время работы:**
4. Обнаружил новую проблему → создать issue: `bash scripts/gh-tasks.sh create ...`
5. Встретил блокер → пометить: `bash scripts/gh-tasks.sh block <N> --reason "..."`

**Последнее действие агента:**
6. Закрыть выполненные issues: `bash scripts/gh-tasks.sh done <N> --comment "Результат + DoD"`
7. Если задача не завершена — оставить status:in-progress, добавить комментарий с прогрессом

**Железное правило:** ни один агент не завершает работу без обновления своих GitHub Issues.

### Definition of Done (DoD) — обязательный чеклист

**При закрытии ЛЮБОГО issue** агент ОБЯЗАН включить DoD-чеклист в `--comment`:

```
## DoD
- [x] Tests pass
- [x] No regression
- [x] AC met
- [x] Artifacts: [список файлов/страниц]
- [x] Docs updated (или N/A)
- [x] No hidden debt
```

Скрипт `gh-tasks.sh done` НЕ закроет issue без `--comment`. Это enforcement.
Artifact cross-check: скрипт сверяет git diff с комментарием, выводит WARNING если файлы не упомянуты.

### Обязательные комментарии к GitHub Issues

**При создании (`--body` обязателен):**
```
## Образ результата
[Что должно появиться/измениться]

## Acceptance Criteria
- [ ] AC1
- [ ] AC2
```

**При закрытии (`--comment` обязателен):**
```
## Результат
[Кратко что сделано]

## Было -> Стало
- [Изменение]

## DoD
[Чеклист выше]
```

### Context pollution prevention
НЕ читай файлы с отчётами/артефактами агентов напрямую — делегируй субагенту. Большие отчёты забивают контекстное окно.

## 6. scripts/setup-orchestrator.sh

Создай одноразовый скрипт начальной настройки (chmod +x).

Что он делает:
1. Определяет OWNER/REPO из git remote
2. Создаёт GitHub Labels:
   - agent:* — по одному на каждого агента проекта (НАСТРОЙ ПОД ПРОЕКТ)
   - sprint:1..5
   - status:planned, status:in-progress, status:blocked
   - priority:critical, priority:high, priority:medium, priority:low
   - type:feature, type:bug, type:infra, type:finding
3. Создаёт GitHub Project (Kanban board)
4. Выводит URL Kanban и подсказку для создания первой задачи

ВАЖНО: список агентов в setup-orchestrator.sh — адаптировать под конкретный проект!

## 7. Порядок внедрения

1. Создай ВСЕ файлы из пунктов 1-6
2. `chmod +x .claude/hooks/*.sh scripts/*.sh`
3. Запусти `bash scripts/setup-orchestrator.sh` — создаст labels + Kanban
4. Проверь каждый хук:
   - block-secrets.sh: safe content -> exit 0; content с реальным секретом -> exit 2
   - gh-tasks.sh без аргументов -> usage
   - gh-tasks.sh sprint -> доска
5. Проверь JSON: `python3 -c "import json; json.load(open('.claude/settings.json')); print('OK')"`
6. Запусти тесты проекта — 0 failures
7. Commit, push, дождись зелёного CI: `gh run watch --exit-status`
8. Создай первую задачу: `bash scripts/gh-tasks.sh create --title "Начальная настройка" --agent orchestrator --sprint 1 --priority high`

## 8. Чеклист (НЕ сдавать без)

```
[ ] CLAUDE.md создан (< 50 строк, context pollution prevention)
[ ] .claude/settings.json — валидный JSON, все 6 хуков зарегистрированы
[ ] .claude/hooks/ — 6 скриптов, все chmod +x, все exit 0 на safe input
[ ] block-secrets.sh — БЛОКИРУЕТ реальные API-ключи и private keys
[ ] scripts/gh-tasks.sh — create/start/done/block/list/sprint работают
[ ] gh-tasks.sh create без --body → exit 1 (enforcement работает)
[ ] gh-tasks.sh done без --comment → exit 1 (enforcement работает)
[ ] gh-tasks.sh done с --comment → artifact cross-check WARNING если файлы не упомянуты
[ ] scripts/setup-orchestrator.sh — labels + Kanban созданы на GitHub
[ ] .claude/rules/common-rules.md — smoke-тесты, deviation rules, GitHub Issues, DoD, context prevention
[ ] Тесты проекта — 0 failures
[ ] git push + CI зелёный
[ ] Первая задача создана на Kanban (с --body!)
```
```

---

## Адаптация под конкретный проект

При запуске промпта в новом проекте — подскажи Claude:

1. **Список агентов** — замени дефолтный список на реальных агентов проекта
2. **Тестовый фреймворк** — укажи что запускать (pytest / jest / go test / etc.)
3. **Доменные guard-хуки** — добавь специфичные ограничения по аналогии с block-secrets.sh
4. **MCP серверы** — добавь `enabledMcpjsonServers` в settings.json если используешь
5. **DoD** — адаптируй чеклист под проект (например: "Docker image built" для микросервисов, "Migrations tested" для БД-проектов)
