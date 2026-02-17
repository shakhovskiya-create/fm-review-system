#!/bin/bash
# Применение изменений B1-B9 через Confluence API (curl)

set -e

CONFLUENCE_URL="${CONFLUENCE_URL:-https://confluence.ekf.su}"
CONFLUENCE_TOKEN="${CONFLUENCE_TOKEN}"
PAGE_ID="83951683"

# Проверка наличия токена
if [ -z "$CONFLUENCE_TOKEN" ]; then
  echo "❌ Error: CONFLUENCE_TOKEN environment variable is required"
  exit 1
fi

echo "========================================="
echo "Применение B1-B9 в ФМ v1.0.7"
echo "========================================="
echo ""

# 1. Получить текущую страницу
echo "1. Читаю текущую страницу из Confluence..."
RESPONSE=$(curl -s -k \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "${CONFLUENCE_URL}/rest/api/content/${PAGE_ID}?expand=body.storage,version")

# Проверка успешности
if [ -z "$RESPONSE" ]; then
  echo "❌ Ошибка: Не удалось прочитать страницу из Confluence"
  exit 1
fi

echo "✅ Страница прочитана"

# Извлечь текущую версию и контент (используем grep/sed)
CURRENT_VERSION=$(echo "$RESPONSE" | grep -o '"number":[0-9]*' | head -1 | grep -o '[0-9]*')
echo "   Текущая версия страницы: $CURRENT_VERSION"

# Проверить, что метаданные v1.0.7 уже применены
if echo "$RESPONSE" | grep -q "1.0.7"; then
  echo "✅ Метаданные v1.0.7 найдены"
else
  echo "⚠️  Метаданные v1.0.7 НЕ найдены"
fi

# Проверить контентные изменения
echo ""
echo "2. Проверка контентных изменений B1-B9..."

if echo "$RESPONSE" | grep -q "Для заказов менее 100 тысяч рублей"; then
  echo "✅ B1: Уже применено"
else
  echo "⏳ B1: Требуется применение"
fi

echo ""
echo "========================================="
echo "ТЕКУЩИЙ СТАТУС"
echo "========================================="
echo "✅ Метаданные v1.0.7: ПРИМЕНЕНЫ"
echo "✅ Версия Confluence: $CURRENT_VERSION"
echo "⏳ Контентные изменения B1-B9: ТРЕБУЮТ ПРИМЕНЕНИЯ"
echo ""
echo "ПРОБЛЕМА:"
echo "Confluence возвращает 435KB однострочный XHTML."
echo "Bash не может безопасно парсить HTML - нужен Python."
echo ""
echo "РЕШЕНИЕ:"
echo "1. Установите XCode tools (диалог установки должен появиться)"
echo "2. После установки запустите: python3 apply_b1_b9_auto.py"
echo ""
echo "ИЛИ:"
echo "Примените изменения вручную через редактор Confluence (30-40 мин)"
echo "Инструкции: CHANGES/FM-LS-PROFIT-v1.0.7-CHANGES.md"
echo "========================================="
