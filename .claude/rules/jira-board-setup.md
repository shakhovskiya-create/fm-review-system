# Jira Board 39 — настройка (ручная, через UI)

## Quick Filters (только через Jira UI)

> Quick Filters нельзя создать через REST API в Jira Server.
> Путь: Board 39 → Configure → Quick Filters → Add Quick Filter

### Существующие фильтры
| Имя | JQL |
|-----|-----|
| Только мои задачи | `assignee = currentUser()` |
| Последние обновления | `updatedDate >= -1d` |

### Рекомендуемые фильтры (добавить вручную)
| Имя | JQL | Описание |
|-----|-----|---------|
| Блокеры | `priority in (Blocker, Critical, Highest)` | Задачи с высоким приоритетом |
| Зависшие | `updatedDate < -3d AND status != "Готово"` | Без обновлений >3 дней |
| Ошибки | `type = "Ошибка"` | Только баги |
| Эпики | `type = Epic` | Только эпики |

## Dashboard (только через Jira UI)

> Dashboard нельзя создать через REST API в Jira Server (405 Method Not Allowed).
> Путь: Dashboards → Create Dashboard

### Рекомендуемый дашборд: "Profitability Service: Sprint"

Гаджеты:
1. **Sprint Burndown** — Board 39, текущий спринт
2. **Filter Results** — JQL: `project=EKFLAB AND labels="product:profitability" AND status!="Готово" ORDER BY priority DESC`
3. **Two Dimensional Filter Statistics** — по type/status, фильтр product:profitability
4. **Pie Chart** — по component, фильтр product:profitability

## WIP Limits (настроены через API)

Board 39 сконфигурирован:
- Колонка "Нужно сделать": без лимита
- Колонка "В работе": max = 5
- Колонка "Выполнено": без лимита

API для обновления WIP:
```bash
# PUT /rest/greenhopper/1.0/rapidviewconfig/columns
# Обязательно включать currentStatisticsField и mappedStatuses
```

## Column IDs (Board 39)

| Колонка | ID | Status ID |
|---------|-----|-----------|
| Нужно сделать | 429 | 10000 |
| В работе | 430 | 10157 |
| Выполнено | 431 | 10001 |
