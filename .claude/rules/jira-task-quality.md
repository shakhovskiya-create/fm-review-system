# Jira Task Quality Standard

## Description Format (ОБЯЗАТЕЛЬНО)

Jira Server НЕ поддерживает Markdown. Описания ТОЛЬКО в Jira Wiki Markup.

### Конвертация MD → Wiki

| Markdown | Jira Wiki |
|----------|-----------|
| `## Заголовок` | `h2. Заголовок` |
| `### Подзаголовок` | `h3. Подзаголовок` |
| `- [ ] Пункт` | `* ( ) Пункт` |
| `- [x] Пункт` | `* (x) Пункт` |
| `- Пункт` | `* Пункт` |
| `` `код` `` | `{{код}}` |
| `**жирный**` | `*жирный*` |

### Шаблон описания (wiki markup)

```
h2. Образ результата
[Что конкретно появится/изменится — 1-3 предложения на русском]

h2. Acceptance Criteria
* ( ) AC1: конкретный критерий
* ( ) AC2: конкретный критерий

h2. Scope
Файлы: [список затрагиваемых файлов]
```

### Запрещено в описании
- `## ` (markdown заголовок) — использовать `h2.`
- `- [ ]` (markdown checkbox) — использовать `* ( )`
- `**text**` (markdown bold) — использовать `*text*`
- Английский язык в заголовках и образе результата

## Smart Checklist (ОБЯЗАТЕЛЬНО)

### При создании задачи
`jira-tasks.sh create` автоматически ставит 6 пунктов DoD (все unchecked `-`):
```
- Tests pass
- No regression
- AC met
- Artifacts listed
- Docs updated (or N/A)
- No hidden debt
```

### При закрытии задачи
Все пункты ДОЛЖНЫ быть:
- `+` (checked/DONE) — пункт выполнен
- `x` (skipped) — пункт неприменим (например "Docs updated" → `x Docs updated: N/A`)

ЗАПРЕЩЕНО оставлять `-` (unchecked) при закрытии. `jira-tasks.sh done` блокирует.

### Кастомизация Smart Checklist
Если задача требует специфических проверок — ДОБАВИТЬ пункты (не удалять стандартные):
```
- Tests pass
- No regression
- AC met
- Artifacts listed
- Docs updated (or N/A)
- No hidden debt
- Confluence опубликован (специфика)
- SE ревью пройдено (специфика)
```

## Валидация (автоматическая)

`jira-tasks.sh done` при закрытии проверяет:
1. `--comment` обязателен (exit 1 без него)
2. Smart Checklist: все `-` → ошибка (exit 1)
3. Artifact cross-check: файлы из `git diff` vs текст комментария

## Процесс разработки (end-to-end)

### Создание задачи
1. `jira-tasks.sh create --title "..." --body "..."` — описание НА РУССКОМ в wiki markup
2. Smart Checklist ставится автоматически (6 пунктов, все `-`)
3. Если нужны доп. пункты — добавить через API сразу

### Работа над задачей
1. `jira-tasks.sh start EKFLAB-N` → статус "В работе"
2. По мере работы: обновлять Smart Checklist пункты на `+`
3. Если пункт N/A: обновить на `x` с пояснением

### Закрытие задачи
1. Убедиться: все пункты `+` или `x` (нет `-`)
2. `jira-tasks.sh done EKFLAB-N --comment "Результат: ... Файлы: ..."`
3. Комментарий: РЕЗУЛЬТАТ + Было→Стало (НЕ дублировать DoD, он в чеклисте)

### Epic
1. Подзадачи закрываются по одной с полным DoD
2. Epic закрывается ПОСЛЕДНИМ — скрипт проверяет children
3. Epic Smart Checklist: `+ All children closed`, `+ AC met`, etc.
