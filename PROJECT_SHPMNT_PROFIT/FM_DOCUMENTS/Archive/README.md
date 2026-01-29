# ARCHIVE - Старые версии и промежуточные файлы

**Дата создания архива:** 29 января 2026

---

## Структура

### v1.0/
Начальные версии документа (v1.0, v1.0.2, v1.0.3)
- FM-LS-PROFIT-v1.0*.docx
- *.bak файлы

### v1.1.0/
Версия 1.1.0 и промежуточные бэкапы
- FM-LS-PROFIT-v1.1.0.docx
- FM-LS-PROFIT-v1.1.0-clean.docx
- *.bak файлы

### v1.2.0/
Бэкапы версии 1.2.0
- FM-LS-PROFIT-v1.2.0-OLD.docx
- FM-LS-PROFIT-v1.2.0-backup.docx
- FM-LS-PROFIT-v1.2.0-RESTORED.docx
- *.bak файлы
- template_fs.docx

### failed_attempts/
Поврежденные файлы (попытки через pack.py и Pandoc)
- FM-LS-PROFIT-v1.2.1.docx (corrupted by pack.py)
- FM-LS-PROFIT-v1.2.1-FIXED.docx (attempt to repair)
- FM-LS-PROFIT-v1.2.1-REPAIRED.docx (attempt to repair)
- FM-LS-PROFIT-v1.2.1-DRAFT.md* (Pandoc markdown attempts)

**Причина:** Python инструменты pack.py и Pandoc не сохраняют структуру DOCX.
**Решение:** Используется .NET OpenXML SDK (PROJECT_SHPMNT_PROFIT/tools/NET/)

### scripts/
Старые Python скрипты (не используются)
- integrate_*.py
- update_metadata_*.py
- verify_*.py

**Заменены на:** .NET OpenXML SDK инструмент

### reports/
Отчеты и анализы для старых версий

#### reports/v1.1.0/
- FM-LS-PROFIT-v1.1.0-CHANGES.md
- FM-LS-PROFIT-v1.1.0-LOGIC-REVIEW.md
- FM-LS-PROFIT-v1.1.0-READABILITY.md

#### reports/v1.2.0/
- FM-LS-PROFIT-v1.2.0-CHECK.md
- FM-LS-PROFIT-v1.2.0-FIXES-PROPOSALS.md
- FM-LS-PROFIT-v1.2.0-INTEGRATED-CHANGES.md
- FM-LS-PROFIT-v1.2.0-LOGIC-FIXES.md
- FM-LS-PROFIT-v1.2.0-VERIFICATION-REPORT.md
- APPLIED_CHANGES_REPORT.md
- INTEGRATION-SUMMARY.txt
- README-v1.2.0.md

---

## Текущие рабочие файлы

Находятся в `FM_DOCUMENTS/` (не в архиве):
- **FM-LS-PROFIT-v1.2.0.docx** — стабильная версия
- **FM-LS-PROFIT-v1.2.1-DRAFT.docx** — новая версия (в работе)
- **FM-LS-PROFIT-v1.2.1-AGREED-SOLUTIONS.md** — согласованные изменения
- **FM-LS-PROFIT-v1.2.1-CHANGES.md** — список изменений

---

## История

1. **v1.0** (28.01.2026) — Начальная версия
2. **v1.1.0** (28.01.2026) — Первый анализ и исправления
3. **v1.2.0** (29.01.2026) — 22 логических исправления
4. **v1.2.1** (в работе) — 32 дополнительных исправления

---

## Инструменты

**Используется:** .NET OpenXML SDK (`PROJECT_SHPMNT_PROFIT/tools/NET/`)

**Устарело:**
- Python pack.py/unpack.py (ломает структуру DOCX)
- Pandoc (ломает форматирование)
- python-docx (ломает стили)

**См. также:** [CLAUDE.md](file:///Users/antonsahovskii/Documents/claude-agents/fm-review-system/CLAUDE.md) § 3.1
