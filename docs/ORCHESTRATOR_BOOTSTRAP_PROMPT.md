# Каталог инфраструктурных плагинов для мультиагентных проектов

> Список компонентов, которые оркестратор разворачивает в **существующем** проекте.
> Проект уже есть, Claude Code уже работает, агенты уже зарегистрированы.
> Промпт описывает **что добавить/обновить** в инфраструктуре проекта.
> Референс: `fm-review-system` (github.com/shakhovskiya-create/fm-review-system)

---

## ПРОМПТ (скопировать в Claude Code целевого проекта)

```
В этом проекте уже есть Claude Code и мультиагентная система. Ниже каталог инфраструктурных плагинов — проверь каждый компонент, добавь недостающие, обнови устаревшие. Не перезаписывай существующее — дополняй. Каждый шаг проверяй smoke-тестом.

## Плагин 1: CLAUDE.md — секции оркестратора

Открой существующий CLAUDE.md. Убедись что есть эти секции (добавь недостающие):

```markdown
## Роль оркестратора

**Context pollution prevention:** НЕ читай файлы с отчётами/артефактами агентов напрямую — делегируй субагенту.

## Задачи

GitHub Issues + Kanban (GitHub Project). Sprint dashboard: `bash scripts/gh-tasks.sh sprint`

## Правила

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `.claude/rules/common-rules.md`.
```

Если CLAUDE.md > 60 строк — вынеси справочный контент в `.claude/rules/` (Claude Code загружает их автоматически).

## Плагин 2: Хуки (.claude/settings.json + .claude/hooks/)

Открой `.claude/settings.json`. Добавь в секцию `hooks` недостающие события (merge с существующими, не перезаписывай):

**Требуемые события:**

| Событие | Скрипт | Назначение |
|---------|--------|------------|
| SessionStart | session-start.sh | Контекст проекта + открытые GitHub Issues оркестратора |
| SubagentStart (matcher: `agent-.*`) | subagent-start.sh | Инжекция GitHub Issues для агента |
| PreToolUse Write | block-secrets.sh | Блокировка записи секретов в файлы |
| PreToolUse Edit | block-secrets.sh | Блокировка записи секретов в файлы |
| SubagentStop (matcher: `agent-.*`) | subagent-stop.sh | Проверка что агент обновил свои issues + DoD шаблон |
| PreCompact | precompact.sh | Предупреждение при переполнении контекста |
| Stop | session-stop.sh | Логирование завершения сессии |

**Формат записи в settings.json:**

```json
{
  "EventName": [
    {
      "matcher": "опционально",
      "hooks": [
        {
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/script-name.sh",
          "timeout": 10
        }
      ]
    }
  ]
}
```

Для каждого хука создай `.sh` скрипт в `.claude/hooks/` (chmod +x, set -euo pipefail).

### 2.1 session-start.sh (SessionStart)

Показывает при старте сессии: имя проекта, открытые GitHub Issues оркестратора, sprint summary.

```bash
#!/bin/bash
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
echo "=== $(basename "$PROJECT_DIR"): Session Start ==="

REPO_URL=$(git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null || echo "")
if [[ "$REPO_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
  GH_OWNER="${BASH_REMATCH[1]}"
  GH_REPO="${BASH_REMATCH[2]}"

  issues=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
    --label "agent:orchestrator" --state open --limit 10 \
    --json number,title,labels \
    --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("sprint:"))] | join(", "))]"' 2>/dev/null || true)
  [ -n "$issues" ] && echo "GitHub Issues (orchestrator):" && echo "$issues"

  sprint_info=$(gh issue list --repo "${GH_OWNER}/${GH_REPO}" \
    --state open --limit 100 --json labels \
    --jq '[.[].labels[].name | select(startswith("sprint:"))] | group_by(.) | map("\(.[0]): \(length) open") | .[]' 2>/dev/null || true)
  [ -n "$sprint_info" ] && echo "Sprints: $sprint_info"
fi

echo "========================================="
exit 0
```

### 2.2 subagent-start.sh (SubagentStart)

Инжектирует назначенные GitHub Issues при старте субагента.

```bash
#!/bin/bash
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

### 2.3 block-secrets.sh (PreToolUse: Write, Edit)

Блокирует запись секретов (API-ключей, токенов, PEM-ключей) в файлы.

```bash
#!/bin/bash
set -euo pipefail

INPUT=$(cat)
TEXT=$(echo "$INPUT" | jq -r '(.tool_input.content // "") + "\n" + (.tool_input.new_string // "")' 2>/dev/null || echo "")
[ -z "$TEXT" ] && exit 0

if echo "$TEXT" | grep -qE '(sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|xox[bpras]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)'; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // "unknown"' 2>/dev/null || echo "unknown")
  echo "BLOCKED: Обнаружен секрет в записи в файл '$FILE_PATH'. Секреты хранить в env/secrets manager, не в файлах." >&2
  exit 2
fi

exit 0
```

### 2.4 subagent-stop.sh (SubagentStop)

Предупреждает если агент не закрыл свои issues. Показывает DoD-шаблон.

```bash
#!/bin/bash
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

### 2.5 precompact.sh (PreCompact)

Предупреждение при переполнении контекстного окна.

```bash
#!/bin/bash
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

### 2.6 session-stop.sh (Stop)

Логирование завершения сессии.

```bash
#!/bin/bash
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "$(date -Iseconds) | session_end" >> "$LOG_DIR/sessions.log"
exit 0
```

## Плагин 3: Task Tracking — scripts/gh-tasks.sh

Проверь есть ли `scripts/gh-tasks.sh`. Если нет — создай (chmod +x). Скрипт определяет OWNER/REPO из git remote (не хардкодь).

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

**Обязательные команды:**

| Команда | Описание | Enforcement |
|---------|----------|-------------|
| `create --title "..." --agent <name> --sprint <N> --body "..."` | Создать issue | **--body ОБЯЗАТЕЛЕН** → exit 1 если пустой |
| `start <N>` | status:planned → status:in-progress + Kanban | — |
| `done <N> --comment "..."` | Закрыть issue + Kanban "Done" | **--comment ОБЯЗАТЕЛЕН** → exit 1 если пустой |
| `block <N> --reason "..."` | status:blocked | — |
| `list [--agent X] [--sprint N] [--status S]` | Список issues | — |
| `my-tasks --agent <name>` | Открытые задачи агента | — |
| `sprint [N]` | Dashboard: In Progress / Planned / Blocked / Done | — |

**Внутренние функции:**
- `_remove_status_labels` — убирает все status:* метки перед установкой новой
- `_sync_project_status` — обновляет колонку на Kanban через `gh project item-edit`
- `_validate_artifacts` — cross-check: сверяет `git diff HEAD~1 --name-only` с текстом `--comment`, выводит WARNING для файлов не упомянутых в Artifacts (не блокирует, но ловит checkbox-ticking)

При `create` — автоматически `gh project item-add` в Project board.

Референс: github.com/shakhovskiya-create/fm-review-system/blob/main/scripts/gh-tasks.sh

## Плагин 4: GitHub Labels + Kanban — scripts/setup-project.sh

Проверь есть ли `scripts/setup-project.sh` (или аналог). Если нет — создай одноразовый скрипт (chmod +x).

Что он делает:
1. Определяет OWNER/REPO из git remote
2. Создаёт GitHub Labels (idempotent — если label уже есть, пропускает):
   - `agent:*` — по одному на каждого агента проекта (**адаптируй список**)
   - `sprint:1` ... `sprint:5`
   - `status:planned`, `status:in-progress`, `status:blocked`
   - `priority:critical`, `priority:high`, `priority:medium`, `priority:low`
   - `type:feature`, `type:bug`, `type:infra`, `type:finding`
3. Создаёт GitHub Project (Kanban board) если не существует
4. Выводит URL Kanban

## Плагин 5: Правила — .claude/rules/common-rules.md

Проверь есть ли `.claude/rules/common-rules.md`. Создай или дополни следующими секциями:

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
3. Если есть issues со status:planned — взять приоритетную: `bash scripts/gh-tasks.sh start <N>`

**Во время работы:**
4. Обнаружил новую проблему → `bash scripts/gh-tasks.sh create ...`
5. Встретил блокер → `bash scripts/gh-tasks.sh block <N> --reason "..."`

**Последнее действие агента:**
6. Закрыть выполненные: `bash scripts/gh-tasks.sh done <N> --comment "Результат + DoD"`
7. Если не завершена — оставить status:in-progress, добавить комментарий с прогрессом

**Железное правило:** ни один агент не завершает работу без обновления своих GitHub Issues.

### Definition of Done (DoD) — обязательный чеклист

**При закрытии ЛЮБОГО issue** агент ОБЯЗАН включить в `--comment`:

```
## DoD
- [x] Tests pass
- [x] No regression
- [x] AC met
- [x] Artifacts: [список файлов/страниц]
- [x] Docs updated (или N/A)
- [x] No hidden debt
```

`gh-tasks.sh done` НЕ закроет issue без `--comment`. Artifact cross-check сверяет git diff с комментарием.

### Обязательные комментарии к GitHub Issues

**При создании (`--body`):**
```
## Образ результата
[Что должно появиться/измениться]

## Acceptance Criteria
- [ ] AC1
- [ ] AC2
```

**При закрытии (`--comment`):**
```
## Результат
[Кратко что сделано]

## Было -> Стало
- [Изменение]

## DoD
[Чеклист выше]
```

### Context pollution prevention
НЕ читай файлы с отчётами/артефактами агентов напрямую — делегируй субагенту.

## Порядок выполнения

1. Прочитай существующие CLAUDE.md, .claude/settings.json, .claude/rules/ — пойми что уже есть
2. Добавь недостающие плагины (1-5), не трогая существующий контент
3. `chmod +x .claude/hooks/*.sh scripts/*.sh`
4. Запусти `bash scripts/setup-project.sh` — создаст labels + Kanban (если ещё нет)
5. Smoke-тест хуков:
   - block-secrets.sh: safe → exit 0; с секретом → exit 2
   - gh-tasks.sh без аргументов → usage
   - gh-tasks.sh sprint → доска
6. Проверь JSON: `python3 -c "import json; json.load(open('.claude/settings.json')); print('OK')"`
7. Запусти тесты проекта — 0 failures
8. Commit, push, CI: `gh run watch --exit-status`

## Чеклист верификации

```
[ ] CLAUDE.md содержит секции оркестратора (context prevention, правила, задачи)
[ ] .claude/settings.json — валидный JSON, все 7 хуков зарегистрированы
[ ] .claude/hooks/ — скрипты chmod +x, exit 0 на safe input
[ ] block-secrets.sh — БЛОКИРУЕТ реальные API-ключи и private keys
[ ] scripts/gh-tasks.sh — create/start/done/block/list/sprint работают
[ ] gh-tasks.sh create без --body → exit 1
[ ] gh-tasks.sh done без --comment → exit 1
[ ] gh-tasks.sh done с --comment → artifact cross-check WARNING если файлы не упомянуты
[ ] GitHub Labels созданы (agent:*, sprint:*, status:*, priority:*, type:*)
[ ] .claude/rules/common-rules.md — smoke-тесты, deviation rules, GitHub Issues, DoD
[ ] Тесты проекта — 0 failures
[ ] git push + CI зелёный
```
```

---

## Что адаптировать

Пользователь подсказывает оркестратору при запуске:

1. **Агенты** — какие субагенты есть в проекте (для labels и маппинга в хуках)
2. **Тестовый фреймворк** — pytest / jest / go test / etc.
3. **Guard-хуки** — доменные ограничения (SQL injection, PII, etc.)
4. **MCP серверы** — Confluence, Langfuse, Playwright и т.д.
5. **DoD** — специфичные пункты ("Docker image built", "Migrations tested", etc.)
6. **Секреты** — Infisical / Vault / другой secret manager
