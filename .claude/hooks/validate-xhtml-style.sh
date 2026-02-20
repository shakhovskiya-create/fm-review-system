#!/bin/bash
# Hook: PostToolUse -> Bash
# Проверяет что записанный XHTML контент соответствует стандартам Confluence:
# - Заголовки таблиц: rgb(255,250,230) (не синий)
# - Нет упоминаний AI/Agent/Claude/Bot в тексте
# - Автор = "Шаховский А.С."

set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Только для команд, работающих с Confluence (python3 скрипты публикации)
[ -z "$COMMAND" ] && exit 0
echo "$COMMAND" | grep -qiE 'publish_to_confluence|confluence_utils|update_page' || exit 0

# Проверяем вывод команды на проблемы
STDOUT=$(echo "$INPUT" | jq -r '.stdout // empty' 2>/dev/null || echo "")
[ -z "$STDOUT" ] && exit 0

WARNINGS=""

# Проверка синего цвета заголовков (запрещен)
if echo "$STDOUT" | grep -qi 'rgb(59,115,175)'; then
  WARNINGS="${WARNINGS}\n⚠️ XHTML содержит запрещенный синий цвет rgb(59,115,175) в заголовках таблиц. Используйте rgb(255,250,230)."
fi

# Проверка упоминаний AI/Agent
if echo "$STDOUT" | grep -qiE 'Agent [0-8]|Claude|GPT|ИИ агент|Bot|LLM|сгенерировано автоматически'; then
  WARNINGS="${WARNINGS}\n⚠️ Обнаружены запрещенные упоминания AI/Agent в контенте для Confluence. Автор должен быть 'Шаховский А.С.'"
fi

if [ -n "$WARNINGS" ]; then
  echo -e "ПРЕДУПРЕЖДЕНИЯ XHTML-валидации:$WARNINGS" >&2
  # Не блокируем (exit 0), но предупреждаем
fi

exit 0
