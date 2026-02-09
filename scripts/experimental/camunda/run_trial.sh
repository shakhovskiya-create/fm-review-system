#!/bin/bash
# Пробная интеграция Camunda Cloud + BPMN -> PNG
# Запуск: bash scripts/experimental/camunda/run_trial.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "╔══════════════════════════════════════════════╗"
echo "║  CAMUNDA BPMN TRIAL - Пробная интеграция     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# --- ШАГ 1: Установка зависимостей ---
echo "=== ШАГ 1: Установка зависимостей ==="
if [ ! -d "node_modules" ]; then
  npm install --no-audit --no-fund 2>&1
  echo ""
fi

# --- ШАГ 2: Camunda Cloud аутентификация ---
echo "=== ШАГ 2: Camunda Cloud аутентификация ==="
if [ -n "${CAMUNDA_CONSOLE_CLIENT_ID:-}" ]; then
  python3 camunda_client.py || echo "[WARN] Camunda Cloud недоступен, продолжаем локально"
else
  echo "[SKIP] CAMUNDA_CONSOLE_CLIENT_ID не задан, пропускаем"
fi
echo ""

# --- ШАГ 3: JSON -> BPMN 2.0 XML ---
echo "=== ШАГ 3: Конвертация JSON -> BPMN 2.0 XML ==="
node json_to_bpmn.js --all
echo ""

# --- ШАГ 4: BPMN -> PNG ---
echo "=== ШАГ 4: Рендер BPMN -> PNG ==="
node render_png.js --all
echo ""

# --- Итог ---
echo "╔══════════════════════════════════════════════╗"
echo "║  РЕЗУЛЬТАТ                                   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "BPMN файлы:"
ls -la output/*.bpmn 2>/dev/null | awk '{print "  " $NF}'
echo ""
echo "PNG файлы:"
ls -la output/*.png 2>/dev/null | awk '{print "  " $NF " (" $5 " bytes)"}'
echo ""
echo "Открыть PNG: open output/*.png"
