---
paths:
  - "workflows/**"
  - "scripts/run_agent.py"
---

# Pipeline (конвейер)

```
Agent 0 (Create) -> Agent 1 (Audit) -> Agent 2 (Simulator) -> Agent 4 (QA) -> Agent 5 (Tech Arch)
  -> Agent 3 (Defender) -> Quality Gate -> Agent 7 (Publish) -> Agent 8 (BPMN) -> Agent 6 (Presenter)
```

> Agent 3 анализирует findings агентов 1, 2, 4, 5 перед Quality Gate.
> Agent 2 в конвейере = /simulate-all. Режим /business — отдельно, перед бизнес-согласованием.

## Запуск

- В чате: "Запусти полный цикл ФМ FM-LS-PROFIT" (читает `workflows/PIPELINE_AUTO.md`)
- Скрипт: `python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT` (или `--parallel`)
- Меню: `./scripts/orchestrate.sh`

## Правила

- Quality Gate ОБЯЗАТЕЛЕН перед Agent 7: `./scripts/quality_gate.sh PROJECT_NAME`
- Коды: 0=OK, 1=CRITICAL (блокирует), 2=WARN (пропуск с --reason)
- Каждый агент читает результаты предыдущих из `PROJECT_*/AGENT_*/`
- Каждый агент создает `_summary.json` (схема: `schemas/agent-contracts.json`)

## Кросс-агентный поток

**При старте:** читает PROJECT_CONTEXT.md, сканирует AGENT_*/, читает ФМ из Confluence.

**При завершении:** сохраняет в AGENT_X_*/, создает _summary.json, обновляет PROJECT_CONTEXT.md, WORKPLAN.md.

| Агент | Читает от | Что использует |
|-------|-----------|----------------|
| Agent 1 | — | Чистый анализ ФМ |
| Agent 2 | Agent 1 | Замечания для фокуса симуляции |
| Agent 3 | Agent 1, 2 | Замечания для ответов |
| Agent 4 | Agent 1, 2 | Замечания и UX для тест-кейсов |
| Agent 5 | Agent 1, 2, 4 | Полная картина для архитектуры |
| Agent 6 | Все | Синтез для презентации |
| Agent 7 | Confluence | Управление контентом |
