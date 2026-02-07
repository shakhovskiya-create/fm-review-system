# Проверка готовности системы к работе

> Итог тщательной проверки (дата: 2025-02-06).

---

## ✅ Готово к работе

### Агенты и скрипты

| Компонент | Статус |
|-----------|--------|
| Агенты 0–8 | Все 9 файлов в `agents/`: CREATOR, ARCHITECT, ROLE_SIMULATOR, DEFENDER, QA_TESTER, TECH_ARCHITECT, PRESENTER, **PUBLISHER**, **BPMN_DESIGNER** |
| Скрипты интервью | agent0_new.sh … agent5_architect.sh присутствуют и вызываются из orchestrate |
| orchestrate.sh | Меню 1–12; PIPELINE_FILES с AGENT_7_PUBLISHER, AGENT_8_BPMN_DESIGNER; команды /publish, /bpmn |
| new_project.sh | Создаёт CHANGES/, CONFLUENCE_PAGE_ID, папки AGENT_7_PUBLISHER, AGENT_8_BPMN_DESIGNER |
| quality_gate.sh | FM_DOCUMENTS необязателен (warn); проверяет оба варианта папок 7/8; раздел 6 — «Confluence & BPMN/диаграммы» |
| common.sh | get_context_file() по проекту; CONTEXT_FILE через get_context_file при save/load |

### Confluence как единственный источник

| Проверка | Статус |
|----------|--------|
| CLAUDE.md: блок «CONFLUENCE = ЕДИНСТВЕННЫЙ ИСТОЧНИК ФМ» и канон (4 пункта) | ✅ |
| Все агенты читают ФМ из Confluence; только Agent 7 вносит правки в тело страницы | ✅ (агенты 1–5: «передать Agent 7») |
| Версионность и дата в Confluence; таблица «История версий» при каждом обновлении | ✅ (CLAUDE, Agent 7, CONFLUENCE_TEMPLATE) |
| Контракт закреплён | ✅ docs/CONTRACT_CONFLUENCE_FM.md |

### PAGE_ID и режимы

| Проверка | Статус |
|----------|--------|
| publish_to_confluence.py: PAGE_ID из пути к doc или env PROJECT | ✅ _get_page_id() |
| export_from_confluence.py: --project= или env PROJECT | ✅ |
| publish-bpmn.py: env PROJECT → файл проекта | ✅ _get_page_id_from_project() |
| README: режимы Confluence-only и legacy, PAGE_ID | ✅ |
| Критерий завершения согласования (workflows, CLAUDE) | ✅ |

### Документация

| Файл | Статус |
|------|--------|
| README.md | Режимы ФМ, BPMN, ссылка на CONTRACT, структура проекта |
| docs/PROMPTS.md | Пути к AGENT_7_PUBLISHER, AGENT_8_BPMN_DESIGNER; этап 3 «Confluence + BPMN»; структура с CHANGES/, 7, 8 |
| docs/CONTRACT_CONFLUENCE_FM.md | Чеклист закрепления контракта |
| workflows/fm-workflows.md | Критерий завершения согласования; Agent 7/8 с правильными именами |
| docs/CONFLUENCE_TEMPLATE.md | Таблица «История версий» обязательна, новая строка при обновлении |

### BPMN

| Проверка | Статус |
|----------|--------|
| generate-bpmn.js + publish-bpmn.py | Документированы в README, AGENT_8, CLAUDE |
| Команды /bpmn, /bpmn-update, /bpmn-validate, /bpmn-publish | В orchestrate для Agent 8 |

---

## ⚠️ Не блокирует работу (при желании донастроить)

- **AGENT_6_PRESENTER:** упоминает экспорт в Miro и PPTX — допустимо как опции форматов; основной поток — Confluence и отчёты.
- **orchestrate:** в форматах презентации есть «Miro доска (через MCP)» — опциональный формат, не обязателен.
- **quality_gate:** проверка MIRO_URL остаётся как опция (warn); BPMN в Confluence не привязан к этому URL.
- **docs/CHANGELOG.md:** исторические упоминания MIGRATOR/EPC - не влияют на текущий запуск. CHAT_CONTEXT.md и todos.md перенесены в docs/archive/ (FC-05).

---

## Быстрая проверка перед использованием

```bash
# 1. Меню открывается (нужен gum: brew install gum)
bash scripts/orchestrate.sh

# 2. Quality gate для проекта
bash scripts/quality_gate.sh PROJECT_SHPMNT_PROFIT

# 3. Контракт (чеклист)
# Открыть docs/CONTRACT_CONFLUENCE_FM.md и пройти разделы 1–8
```

---

## Вердикт

**Система готова к работе.** Все критические правила закреплены, скрипты и агенты согласованы с контрактом Confluence как единственного источника ФМ. Опциональные упоминания Miro (Presenter, quality_gate) не мешают основному сценарию: чтение ФМ из Confluence, правки через Agent 7, версионность и таблица изменений на странице, BPMN через generate-bpmn.js и publish-bpmn.py.
