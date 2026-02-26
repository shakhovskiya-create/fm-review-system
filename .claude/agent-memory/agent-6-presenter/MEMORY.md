# Agent 6 Presenter — Memory

## Проект: PROJECT_SHPMNT_PROFIT / FM-LS-PROFIT

### Структура вывода
- Отчет: `projects/PROJECT_SHPMNT_PROFIT/REPORTS/PIPELINE-REPORT-v{version}-{date}.md`
- Summary JSON: `projects/PROJECT_SHPMNT_PROFIT/AGENT_6_PRESENTER/present_summary.json`
- Схема _summary.json для Agent 6: `{"presentations": N, "summaries": N, "total": N}`

### Источники данных
- Agent 1 audit: `AGENT_1_ARCHITECT/AUDIT-REPORT-v{ver}-{date}.md` + `audit_summary.json`
- Agent 2 UX: `AGENT_2_ROLE_SIMULATOR/UX-SIMULATION-v{ver}-{date}.md` + `simulate-all_summary.json`
- Agent 3 defense: `AGENT_3_DEFENDER/DEFENSE-PIPELINE-v{ver}-{date}.md` + `respond-all_summary.json`
- Agent 4 QA: `AGENT_4_QA_TESTER/TEST-CASES-v{ver}-{date}.md` + `generate-all_summary.json`
- Agent 5 arch: `AGENT_5_TECH_ARCHITECT/ARCHITECTURE-v{ver}.md`, `TZ-v{ver}.md`, `full_summary.json`
- Контекст: `projects/PROJECT_SHPMNT_PROFIT/PROJECT_CONTEXT.md`

### Правила
- Автор всегда «Шаховский А.С.» — без упоминания агентов/ИИ
- Цифры: часы, проценты, сроки — обязательны
- Язык: бизнес-терминология (не «агент», не «Claude»)
- Quality Gate PASS = 16 OK / 15 WARN / 0 FAIL (стандарт v1.0.4)

### История конвейеров
| Версия | Дата | Отчет |
|--------|------|-------|
| v1.0.4->v1.0.5 | 25.02.2026 | PIPELINE-REPORT-v1.0.5-2026-02-25.md |
| v1.0.6 | 13.02.2026 | PIPELINE-REPORT-v1.0.6-2026-02-13.md |
