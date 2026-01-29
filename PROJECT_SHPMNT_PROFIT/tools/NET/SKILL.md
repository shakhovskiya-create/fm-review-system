# SKILL: Редактирование DOCX файлов (.NET OpenXML SDK)

## Триггер

Когда пользователь просит:
- Отредактировать / изменить / исправить .docx файл
- Сделать ревью / рецензию документа Word
- Внести правки в функциональную модель / ТЗ / спецификацию
- Заменить текст в документе
- Добавить комментарии к документу

**→ Используй этот инструмент.**

---

## Расположение

```
PROJECT_SHPMNT_PROFIT/
├── FM_DOCUMENTS/                ← документы .docx
│   └── FM-LS-SHPMNT-PROFIT.docx
├── tools/
│   └── NET/                     ← ТЫ ЗДЕСЬ
│       ├── SKILL.md
│       ├── DocxTools.csproj
│       ├── Program.cs
│       └── bin/
└── ...
```

**Рабочая директория:** `PROJECT_SHPMNT_PROFIT`

---

## Быстрые команды

Все команды запускать из `PROJECT_SHPMNT_PROFIT/`:

```bash
# Информация о документе
dotnet run --project ./tools/NET -- info ./FM_DOCUMENTS/FILE.docx

# Поиск текста
dotnet run --project ./tools/NET -- find ./FM_DOCUMENTS/FILE.docx "текст"

# Замена с tracked changes
dotnet run --project ./tools/NET -- replace ./FM_DOCUMENTS/FILE.docx "старый" "новый" --tracked

# Массовые замены из JSON
dotnet run --project ./tools/NET -- batch ./FM_DOCUMENTS/FILE.docx ./tools/NET/changes.json --tracked

# Добавить комментарий
dotnet run --project ./tools/NET -- comment ./FM_DOCUMENTS/FILE.docx "текст" "комментарий"

# Принять все изменения
dotnet run --project ./tools/NET -- accept ./FM_DOCUMENTS/FILE.docx --output ./FM_DOCUMENTS/FILE-clean.docx

# Отклонить все изменения  
dotnet run --project ./tools/NET -- reject ./FM_DOCUMENTS/FILE.docx
```

---

## Workflow

### 1. Анализ документа

```bash
cd /Users/antonsahovskii/Documents/claude-agents/fm-review-system/PROJECT_SHPMNT_PROFIT
dotnet run --project ./tools/NET -- info ./FM_DOCUMENTS/FM-LS-SHPMNT-PROFIT.docx
```

### 2. Массовые замены

```bash
# Создать JSON
cat > ./tools/NET/changes.json << 'EOF'
{
    "старый текст 1": "новый текст 1",
    "старый текст 2": "новый текст 2"
}
EOF

# Применить с tracked changes
dotnet run --project ./tools/NET -- batch ./FM_DOCUMENTS/FM-LS-SHPMNT-PROFIT.docx ./tools/NET/changes.json --tracked --author "Claude" --output ./FM_DOCUMENTS/FM-LS-SHPMNT-PROFIT-reviewed.docx
```

### 3. Проверка результата

```bash
dotnet run --project ./tools/NET -- info ./FM_DOCUMENTS/FM-LS-SHPMNT-PROFIT-reviewed.docx
```

---

## Правила

1. **ВСЕГДА `--tracked`** — пользователь увидит изменения в Word
2. **ВСЕГДА `--output`** в новый файл для массовых изменений
3. **Проверяй `info`** до и после
4. **Сообщай статистику** — сколько замен, какие не найдены

---

## Пример отчёта

```
✅ Готово! Изменения в FM-LS-SHPMNT-PROFIT-reviewed.docx:

Выполнено:
  ✓ "30 дней" → "45 дней": 3 замены
  ✓ "1С:ERP" → "1С:ERP 2.5": 12 замен
  ⚠ "устаревший термин": не найдено

📊 Итого: 15 замен в режиме рецензирования

Откройте в Word для просмотра и принятия изменений.
```

---

## Пересборка (если нужно)

```bash
cd /Users/antonsahovskii/Documents/claude-agents/fm-review-system/PROJECT_SHPMNT_PROFIT/tools/NET
rm -rf bin obj
dotnet restore
dotnet build -c Release
```
