# Failed Attempts — Поврежденные файлы

**Дата:** 29 января 2026

---

## Что здесь

Попытки применить 32 изменения к FM-LS-PROFIT-v1.2.0.docx с использованием неподходящих инструментов.

### Файлы

1. **FM-LS-PROFIT-v1.2.1.docx** (511 KB)
   - Создан: pack.py (Python)
   - Проблема: Отсутствует папка `_rels/` внутри DOCX архива
   - Результат: Не открывается в Word, python-docx выдает KeyError

2. **FM-LS-PROFIT-v1.2.1-FIXED.docx** (420 KB)
   - Создан: Попытка восстановления через копирование _rels/
   - Проблема: XML syntax errors в document.xml
   - Результат: Не открывается

3. **FM-LS-PROFIT-v1.2.1-REPAIRED.docx** (525 KB)
   - Создан: Попытка восстановления через unzip/zip
   - Проблема: Структура DOCX нарушена
   - Результат: Не открывается

4. **FM-LS-PROFIT-v1.2.1-DRAFT.md** (222 KB)
5. **FM-LS-PROFIT-v1.2.1-DRAFT.md.bak** (204 KB)
   - Создан: Pandoc (DOCX → Markdown)
   - Проблема: Pandoc ломает таблицы и форматирование при обратной конвертации
   - Результат: Markdown файлы, но DOCX собранный из них ломается

---

## Почему сломались

### pack.py (Python)

```python
# Проблема: pack.py не создает папку _rels/ при упаковке
# DOCX требует строгую структуру:
# [Content_Types].xml
# _rels/
#   .rels
# word/
#   document.xml
#   _rels/
#     document.xml.rels
```

**Ошибка:**
```
KeyError: "no relationship of type
'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'
in collection"
```

**Причина:** Отсутствует `_rels/.rels` — критический файл связей DOCX.

### Pandoc

```bash
# Workflow:
pandoc FM-LS-PROFIT-v1.2.0.docx -o draft.md --extract-media=./media
# Редактирование draft.md
pandoc draft.md -o FM-LS-PROFIT-v1.2.1.docx --reference-doc=template.docx
```

**Проблема:** Pandoc не сохраняет:
- Сложные таблицы (с объединенными ячейками)
- Нестандартные стили
- Tracked changes
- Комментарии Word
- Точное форматирование (отступы, выравнивание)

**Результат:** "Я не знаю что там у тебя случилось но ты весь документ поломал. и таблицы и текст. Все сломалось и съехало." — отзыв пользователя.

---

## Решение

**Используется:** .NET OpenXML SDK

```bash
cd PROJECT_SHPMNT_PROFIT
dotnet run --project ./tools/NET -- batch \
    ./FM_DOCUMENTS/FM-LS-PROFIT-v1.2.0.docx \
    ./tools/NET/changes.json \
    --tracked \
    --author "Шаховский А.С." \
    --output ./FM_DOCUMENTS/FM-LS-PROFIT-v1.2.1-DRAFT.docx
```

**Преимущества:**
- Microsoft OpenXML SDK — официальный инструмент
- 100% сохранение структуры DOCX
- Полная поддержка tracked changes
- Работа с таблицами, стилями, комментариями
- Нет конвертации в промежуточные форматы

**Подробнее:** [PROJECT_SHPMNT_PROFIT/tools/NET/SKILL.md](file:///Users/antonsahovskii/Documents/claude-agents/fm-review-system/PROJECT_SHPMNT_PROFIT/tools/NET/SKILL.md)

---

## Урок

❌ **НЕ ИСПОЛЬЗОВАТЬ** для редактирования DOCX:
- Python pack.py/unpack.py
- Pandoc (DOCX ↔ Markdown)
- python-docx (только для чтения)
- Прямое редактирование XML

✅ **ИСПОЛЬЗОВАТЬ:**
- .NET OpenXML SDK (`PROJECT_*/tools/NET/`)
- См. [CLAUDE.md](file:///Users/antonsahovskii/Documents/claude-agents/fm-review-system/CLAUDE.md) § 3.1
