# SKILL: Инструменты для работы с документами

## Структура

```
tools/
├── SKILL.md              ← ТЫ ЗДЕСЬ (обзор)
├── NET/                  ← .NET OpenXML SDK (рекомендуется)
│   ├── SKILL.md          ← Подробная инструкция
│   ├── DocxTools.csproj
│   ├── Program.cs
│   └── bin/
└── docx_tools/           ← Python (backup)
    ├── SKILL.md
    └── *.py
```

---

## Рекомендация: используй .NET версию

**Для редактирования DOCX → читай `./NET/SKILL.md`**

Преимущества:
- Microsoft OpenXML SDK — официальный инструмент
- 100% сохранение форматирования
- Полная поддержка tracked changes
- Работа с комментариями

---

## Быстрый старт

Из директории `PROJECT_SHPMNT_PROFIT`:

```bash
# Информация о документе
dotnet run --project ./tools/NET -- info ./FM_DOCUMENTS/FILE.docx

# Замена с tracked changes
dotnet run --project ./tools/NET -- replace ./FM_DOCUMENTS/FILE.docx "старый" "новый" --tracked

# Массовые замены
dotnet run --project ./tools/NET -- batch ./FM_DOCUMENTS/FILE.docx ./tools/NET/changes.json --tracked
```

Подробнее: **`./NET/SKILL.md`**
