#!/bin/bash
# Hook: Stop
# Автоматически обновляет timestamp в PROJECT_CONTEXT.md при завершении ответа.
# Фиксирует факт работы агента для межсессионной преемственности.
#
# Конкурентность: запись последовательная (один агент за раз в пайплайне),
# блокировка не требуется. sed обновляет только маркер "Последняя сессия:".

set -euo pipefail
INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)

# Ищем активный проект (PROJECT_*)
for ctx_file in "$PROJECT_DIR"/projects/PROJECT_*/PROJECT_CONTEXT.md; do
  [ -f "$ctx_file" ] || continue

  # Обновляем timestamp последней сессии (если есть маркер)
  if grep -q "Последняя сессия:" "$ctx_file" 2>/dev/null; then
    sed -i "s|Последняя сессия:.*|Последняя сессия: $TIMESTAMP|" "$ctx_file" 2>/dev/null || true
  fi
done

# Обновляем timestamp в CONTEXT.md (progress file)
CONTEXT_FILE="$PROJECT_DIR/CONTEXT.md"
if [ -f "$CONTEXT_FILE" ]; then
  sed -i "s|^**Дата:**.*|**Дата:** $(date +%d.%m.%Y)|" "$CONTEXT_FILE" 2>/dev/null || true
fi

exit 0
