# Закрепление: контракт Confluence как единственного источника ФМ

> Единый чеклист для проверки: все ли правила соблюдены в коде и документации.

---

## 1. Confluence — единственный источник правды

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Все читают ФМ из Confluence (REST API, PAGE_ID) | CLAUDE.md § 3.1 (блок CONFLUENCE = ЕДИНСТВЕННЫЙ ИСТОЧНИК ФМ) | ✅ |
| Правки в тело страницы вносит только Agent 7 (PUT) | CLAUDE.md, агенты 1–5 (ПОСЛЕ /apply: передать Agent 7) | ✅ |
| Агенты 0–5 передают изменения Agent 7 для публикации | CLAUDE.md, README, agents/AGENT_1..5 | ✅ |
| Word/DOCX не источник актуальной ФМ | CLAUDE.md (запрещено), README (режимы) | ✅ |

---

## 2. Версионность и дата

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Версионность полностью в Confluence (version.number при каждом PUT) | CLAUDE.md (канон п.2), Agent 7, CONFLUENCE_TEMPLATE | ✅ |
| Дата в мета-таблице — автоматически при обновлении | CLAUDE.md (канон п.3), Agent 7, CONFLUENCE_TEMPLATE (Дата: авто) | ✅ |
| История версий доступна в UI (Page History) | CLAUDE.md, Agent 7 | ✅ |

---

## 3. Таблица изменений на странице

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| На странице ФМ ведётся таблица «История версий» (Номер \| Дата \| Автор \| Изменения) | CONFLUENCE_TEMPLATE.md, CLAUDE.md (канон п.4) | ✅ |
| При каждом обновлении — новая строка с кратким описанием | CLAUDE.md (правила, § 5 Обязательные метаданные), Agent 7 | ✅ |
| В API version.message — краткое описание версии | Agent 7 (инструкция PUT) | ✅ |

---

## 4. PAGE_ID из файла проекта

| Проверка | Где реализовано | Статус |
|----------|-----------------|--------|
| publish_to_confluence.py: PAGE_ID из пути к doc или env PROJECT | scripts/publish_to_confluence.py (_get_page_id, путь projects/...) | ✅ |
| export_from_confluence.py: --project=NAME или env PROJECT | scripts/export_from_confluence.py (_get_page_id, --project=) | ✅ |
| publish-bpmn.py: env PROJECT → файл projects/PROJECT/CONFLUENCE_PAGE_ID | scripts/publish-bpmn.py (_get_page_id_from_project) | ✅ |
| new_project создаёт файл CONFLUENCE_PAGE_ID | scripts/new_project.sh | ✅ |

---

## 5. Режимы работы с ФМ и публикация

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Confluence-only (рекомендуется): ФМ только в Confluence | README (Режимы работы с ФМ) | ✅ |
| Confluence + FM_DOCUMENTS (legacy): источник истины — Confluence | README, CLAUDE.md | ✅ |
| quality_gate не требует FM_DOCUMENTS (warn при отсутствии) | scripts/quality_gate.sh | ✅ |
| Меню 11.4 «Публикация ФМ»: при наличии docx — скрипт по пути к файлу; при Confluence-only — подсказка: Agent 7 или `--from-file` | orchestrate.sh, publish_to_confluence.py | ✅ |
| Обновление тела страницы без docx: `publish_to_confluence.py --from-file <body.xhtml> --project PROJECT` или Agent 7 в Claude Code | README, скрипт (режим --from-file) | ✅ |

---

## 6. Критерий завершения согласования и верификация

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Согласование завершено = статус Approved + нет открытых комментариев | workflows/fm-workflows.md, CLAUDE.md (Бизнес-согласование) | ✅ |
| Проверка: вручную (Confluence UI) или скриптом по API (комментарии к странице); при автоматизации — критерий «готово» = 0 открытых комментариев | Контракт (этот раздел) | ✅ |
| После каждого PUT в Confluence — верификация: GET страницы и проверка ключевых фрагментов; обновление считается применённым только после успешной верификации | Agent 7 (инструкция), CLAUDE.md § 6 | ✅ |

---

## 7. BPMN

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Цепочка: generate-bpmn.js (JSON → .drawio) + publish-bpmn.py (загрузка в Confluence) | README (BPMN-диаграммы), AGENT_8_BPMN_DESIGNER.md, CLAUDE.md | ✅ |

---

## 8. Библиотеки scripts/lib (AG-13)

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| confluence_utils.py, contract_validator.py — вне текущего контура публикации; скрипты publish_to_confluence.py и оркестрация их не используют | README, этот раздел | ✅ |
| При необходимости retry/lock/валидации контрактов — подключать явно и описать в контракте | Контракт (этот раздел) | ✅ |

## 9. Автономный /apply (APPLY_MODE, APPLY_SCOPE)

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| При env APPLY_MODE=auto агенты 1, 2, 4 не спрашивают «какие правки применить»; применяют по APPLY_SCOPE | Контракт (этот раздел), агенты (инструкция) | ✅ |
| APPLY_SCOPE=critical_high — применить только CRITICAL и HIGH; all — все; иначе — запросить у пользователя | Контракт | ✅ |
| Без APPLY_MODE=auto решение о наборе правок — за человеком (эскалация) | CLAUDE.md, агенты | ✅ |

## 10. Контекст и папки проектов

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| Контекст интервью по проекту: .interview_context_${PROJECT}.txt | scripts/lib/common.sh (get_context_file), orchestrate (export PROJECT) | ✅ |
| Канон контекста проекта: PROJECT_[NAME]/PROJECT_CONTEXT.md | CLAUDE.md (Автосохранение) | ✅ |
| CHANGES/: new_project создаёт; FM-*-CHANGES.md по правилу в CHANGES/ | new_project.sh, CLAUDE.md § 9 | ✅ |
| Папки агентов 7/8: AGENT_7_PUBLISHER, AGENT_8_BPMN_DESIGNER (новые); quality_gate принимает и старые имена | new_project.sh, quality_gate.sh | ✅ |
| Pipeline state: per-project, `projects/PROJECT/.pipeline_state.json`; меню 12 показывает состояние выбранного проекта | scripts/lib/common.sh (get_pipeline_state_file), orchestrate.sh | ✅ |

## 11. Автономный запуск пайплайна (AUTONOMOUS, run_agent.py)

| Проверка | Где зафиксировано | Статус |
|----------|-------------------|--------|
| При AUTONOMOUS=1 и ANTHROPIC_API_KEY оркестратор вызывает run_agent.py вместо копирования промпта в буфер | scripts/orchestrate.sh (полный цикл) | ✅ |
| run_agent.py: --project, --agent 0-8, --command; сохраняет результат в projects/PROJECT/AGENT_X_*/ | scripts/experimental/run_agent.py (FC-03: перенесен в experimental/) | ✅ |

---

## Быстрая проверка (команды)

```bash
# Quality gate не падает без FM_DOCUMENTS
./scripts/quality_gate.sh PROJECT_SHPMNT_PROFIT

# PAGE_ID из файла (если в проекте заполнен CONFLUENCE_PAGE_ID)
export PROJECT=PROJECT_SHPMNT_PROFIT
python3 scripts/export_from_confluence.py --project=PROJECT_SHPMNT_PROFIT --both
```

---

**Дата закрепления:** 2025-02-06  
**Следующая проверка:** при изменении правил Confluence/агентов/скриптов — пройти чеклист выше.
