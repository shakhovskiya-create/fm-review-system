# Lead Auditor — Полный закрываемый аудит multi-agent системы FM Review

> **Роль:** Lead Auditor. Только констатация, без изменений кода.
> **Findings Ledger:** OPEN / CLOSED / ACCEPTED_RISK. CLOSED и ACCEPTED_RISK не поднимаются повторно. Новое finding = новый класс проблемы или регрессия (с доказательством).
> **Основа:** docs/MULTI_AGENT_AUDIT_REPORT.md (AG-01…AG-11 считаются закрытыми/принятыми по классам).

---

## A) COVERAGE

### Scanned paths

| Путь | Что проверено |
|------|----------------|
| `agents/` | Все 9 файлов: роли, входы/выходы, решения, запреты, блок «ПОСЛЕ /apply», эскалации |
| `scripts/orchestrate.sh` | Меню, порядок этапов, PIPELINE_ORDER/FILES, вызовы get_latest_fm, ветка 11.4 |
| `scripts/lib/common.sh` | ROOT_DIR, get_context_file, get_latest_fm, PIPELINE_STATE, init_pipeline_state, copy_to_clipboard |
| `scripts/quality_gate.sh` | FM_DOCUMENTS optional, папки 7/8, grep Открыт/Open |
| `scripts/new_project.sh` | Структура папок, CONFLUENCE_PAGE_ID, CHANGES/ |
| `scripts/publish_to_confluence.py` | _get_page_id, DOC_PATH, использование lib |
| `scripts/export_from_confluence.py` | _get_page_id, PROJECT |
| `scripts/publish-bpmn.py` | _get_page_id_from_project, load_env |
| `workflows/fm-workflows.md` | Сценарии, критерий согласования |
| `CLAUDE.md` | Контракт Confluence, канон, автосохранение, нумерация |
| `docs/PROMPTS.md` | Пути к агентам 7/8, структура проектов |
| `docs/CONTRACT_CONFLUENCE_FM.md` | Чеклист закрепления |
| `docs/READINESS_CHECK.md` | Соответствие контракту |
| `docs/MULTI_AGENT_AUDIT_REPORT.md` | Ledger: AG-01…AG-11 (не переоткрываются) |
| `docs/FINAL_AUDIT_AND_ARCHITECTURE.md` | Упоминание |
| `projects/PROJECT_*/` | Наличие CONFLUENCE_PAGE_ID, CHANGES, структура (выборочно) |

### Excluded paths (и почему)

| Путь | Причина |
|------|--------|
| `scripts/*.js`, `scripts/node_modules/` | BPMN-генерация; не оркестрация и не контракты агентов |
| `scripts/*.py` (кроме publish_to_confluence, export_from_confluence, publish-bpmn) | Вспомогательные (add_navigation, check_*, fix_*, etc.); не критичны для детерминизма пайплайна |
| `templates/`, `schemas/` | Контентные шаблоны; не меняют поведение агентов/оркестрации |
| `exports/` | Артефакты экспорта; не источник решений |
| `.env`, `.env.local` | Секреты; не сканируются |

---

## B) SYSTEM MAP

### Agent → Inputs → Outputs → Allowed decisions → Must escalate

| Agent | Inputs | Outputs | Allowed decisions | Must escalate |
|-------|--------|---------|-------------------|---------------|
| Agent 0 (Creator) | PROJECT_CONTEXT, .interview_context_${PROJECT}, ответы интервью | Контент ФМ (для Agent 7), PROJECT_*/AGENT_0_CREATOR/ | Структура разделов, формулировки | Смена формата ФМ, новый проект без подтверждения |
| Agent 1 (Architect) | Confluence (PAGE_ID), PROJECT_CONTEXT, AGENT_* | AGENT_1_ARCHITECT/*.md; при /apply — передать Agent 7 | Классификация замечаний, предложение правок | Применение всех правок без выбора пользователя |
| Agent 2 (Role Simulator) | Confluence, AGENT_1_ARCHITECT, PROJECT_CONTEXT | AGENT_2_ROLE_SIMULATOR/*.md; при /apply — передать Agent 7 | Приоритизация UX-правок | Изменение структуры документа |
| Agent 3 (Defender) | AGENT_1/2/4, Confluence, PROJECT_CONTEXT | AGENT_3_DEFENDER/*.md; при /apply — передать Agent 7 | Классификация A–I, аргументация | Принятие/отклонение без решения пользователя |
| Agent 4 (QA Tester) | AGENT_1/2, Confluence, PROJECT_CONTEXT | AGENT_4_QA_TESTER/*.md; при /apply — передать Agent 7 | Приоритет тестов | Изменение требований без трассировки к finding |
| Agent 5 (Tech Architect) | AGENT_1/2/4, Confluence, PROJECT_CONTEXT | AGENT_5_TECH_ARCHITECT/*.md; при /apply — передать Agent 7 | Решения 1С, оценка | Изменение бизнес-правил (зона Agent 1) |
| Agent 6 (Presenter) | Все AGENT_*/, Confluence, PROJECT_CONTEXT | AGENT_6_PRESENTER/*; не пишет в Confluence | Формат и аудитория | Публикация в Confluence (делегирует Agent 7) |
| Agent 7 (Publisher) | PAGE_ID (файл/env), контент от 0–5, PROJECT_CONTEXT | Confluence (PUT), AGENT_7_PUBLISHER/*, обновление PROJECT_CONTEXT (URL) | GET перед PUT, комментарий версии | Создание страницы в другом space без подтверждения |
| Agent 8 (BPMN Designer) | Confluence (ФМ), AGENT_1/2/7, bpmn-processes/*.json | scripts/bpmn-processes/, scripts/output/, вложения Confluence | Нотация и разметка BPMN | Изменение текста ФМ на странице |

### Artifact → Owner → Write path → Read path

| Artifact | Owner | Write path | Read path |
|----------|--------|------------|-----------|
| Тело страницы ФМ (Confluence) | Agent 7 | PUT /rest/api/content/{PAGE_ID} | Все агенты (GET), Agent 7 (верификация) |
| PROJECT_CONTEXT.md | Агенты 0–5, 7 | projects/PROJECT_*/PROJECT_CONTEXT.md | Все агенты, quality_gate |
| .interview_context_${PROJECT}.txt | agent*_*.sh / пользователь | ROOT_DIR (get_context_file) | Агенты при /audit и т.д. |
| CONFLUENCE_PAGE_ID | Человек / Agent 7 (при первой публикации) | projects/PROJECT_*/CONFLUENCE_PAGE_ID | publish_to_confluence, export_from_confluence, publish-bpmn (при PROJECT) |
| CHANGES/ (FM-*-CHANGES.md) | Агенты 1–5 при /apply | projects/PROJECT_*/CHANGES/ | quality_gate (наличие папки), трассировка |
| AGENT_*/*.md | Соответствующий агент | projects/PROJECT_*/AGENT_X_*/ | Следующие агенты, orchestrate (контекст этапов) |
| .pipeline_state.json | orchestrate (common.sh) | ROOT_DIR/.pipeline_state.json | orchestrate (меню 12 «Статус pipeline») |

---

## C) FINDINGS (только новые или регрессия)

Ссылки на Ledger: AG-01…AG-11 в docs/MULTI_AGENT_AUDIT_REPORT.md считаются закрытыми/принятыми; ниже — только новые классы или доказанная регрессия.

---

### AG-12 — Регрессия Confluence-only в меню «Публикация ФМ в Confluence» (REGRESSION)

- **ID:** AG-12  
- **Severity:** M (Medium)  
- **Evidence:**  
  - `scripts/orchestrate.sh` строки 311–318: ветка «11. Управление проектами» → «4. Публикация ФМ в Confluence» вызывает `FM_PATH=$(get_latest_fm "$PROJECT")` без `2>/dev/null || true`.  
  - В `scripts/lib/common.sh` функция `get_latest_fm` при отсутствии `FM_DOCUMENTS` или файлов вызывает `error` и возвращает 1. При `set -e` скрипт завершается с ошибкой.  
  - В том же блоке: `if [[ -n "$FM_PATH" ]]; then python3 ... publish_to_confluence.py "$FM_PATH"; else error "ФМ не найдена..."; fi` — для Confluence-only проекта ветка всегда «ФМ не найдена», т.е. сценарий «только Confluence» не поддерживается этим пунктом меню.  
- **Risk:** Пользователь Confluence-only проекта при выборе «Публикация ФМ в Confluence» из меню получает падение скрипта или сообщение «ФМ не найдена»; ожидание — обновление страницы из контекста (без docx).  
- **Failure mode:** Детерминированный отказ пункта меню для проектов без FM_DOCUMENTS; расхождение с заявленным режимом «Confluence-only» в CONTRACT и quality_gate.  
- **What must be formalized:** Правило/контракт: «Пункт меню 11.4 либо (a) явно помечен как legacy (только при наличии FM_DOCUMENTS), либо (b) при отсутствии FM_PATH вызывает обновление Confluence по PAGE_ID (например, только метаданные/история версий) без docx». Плюс в коде: вызов get_latest_fm в этой ветке с `2>/dev/null || true` и явная обработка пустого FM_PATH (сообщение или альтернативный путь).

---

### AG-13 — Библиотеки lib без использования (MISSING_SPEC)

- **ID:** AG-13  
- **Severity:** L (Low)  
- **Evidence:**  
  - `scripts/lib/confluence_utils.py` и `scripts/lib/contract_validator.py` присутствуют.  
  - По всему репозиторию (в т.ч. все `.py` в `scripts/`) нет ни одного `import confluence_utils` или `import contract_validator` (или эквивалента через `lib.`).  
  - Упоминания только в самих файлах (docstring/примеры) и в `todos.md`.  
- **Risk:** Неясный контракт: код либо мёртвый, либо «на будущее». Изменения в этих модулях не влияют на наблюдаемое поведение; возможна ложная уверенность, что retry/lock/валидация используются.  
- **Failure mode:** Предположение, что Confluence-операции идут через confluence_utils (locking, rollback), при том что publish_to_confluence.py их не использует — расхождение ожиданий и реализации.  
- **What must be formalized:** Спецификация: либо (a) «confluence_utils / contract_validator — обязательные зависимости» и явное подключение в publish_to_confluence.py / оркестрации, либо (b) «вне контура текущего контракта, не используются» — и вынести в отдельный каталог/документировать как экспериментальные.
- **Решено (FC-01, 07.02.2026):** confluence_utils.py интегрирован в publish_to_confluence.py v3.0 (вариант a). contract_validator.py перенесен в scripts/experimental/ (вариант b).

---

### AG-14 — Единый глобальный pipeline state (MISSING_SPEC)

- **ID:** AG-14  
- **Severity:** L (Low)  
- **Evidence:**  
  - `scripts/lib/common.sh`: `PIPELINE_STATE="${ROOT_DIR}/.pipeline_state.json"` — один файл в корне репозитория.  
  - `init_pipeline_state "$PROJECT" "${FM_PATH:-Confluence}"` перезаписывает этот файл при каждом запуске «Полный цикл review».  
  - Меню «12. Статус pipeline» выводит содержимое этого файла без привязки к проекту в текущем выборе.  
- **Risk:** При переключении между проектами состояние пайплайна относится к последнему запущенному циклу. Пользователь может интерпретировать «Статус pipeline» как статус другого проекта.  
- **Failure mode:** Неверное решение на основе «статуса» (например, считать, что текущий проект уже прошёл этап, который на самом деле был у другого проекта).  
- **What must be formalized:** Спецификация: либо (a) «pipeline state — один глобальный, отображаемый статус всегда для последнего запуска» (зафиксировать в README/оркестрации), либо (b) «состояние per-project» — путь вида `projects/${PROJECT}/.pipeline_state.json` и чтение в меню 12 по выбранному/текущему проекту.

---

### AG-15 — Нет сценария «обновить Confluence без docx» для меню 11.4 (MISSING_SPEC)

- **ID:** AG-15  
- **Severity:** M (Medium)  
- **Evidence:**  
  - `scripts/publish_to_confluence.py` требует аргумент — путь к docx (`sys.argv[1]`); при отсутствии — выход с сообщением «Usage: ... path-to-docx».  
  - Нет режима «обновить страницу по PAGE_ID без загрузки docx» (например, только таблица «История версий» или метаданные).  
  - CONTRACT и README закрепляют режим Confluence-only; при этом единственный скрипт публикации в Confluence из оркестрации — Word→Confluence.  
- **Risk:** В режиме Confluence-only обновление контента страницы после правок агентов возможно только вручную в Confluence или через недокументированный/внешний путь; пункт меню 11.4 для таких проектов бесполезен или вводит в заблуждение.  
- **Failure mode:** Ожидание «нажал 11.4 — страница обновилась» не выполняется для Confluence-only; снижение доверия к контракту «Confluence — единственный источник».  
- **What must be formalized:** Спецификация режимов публикации: (1) legacy: docx → Confluence (текущее поведение); (2) Confluence-only: явно описать, что «обновление тела страницы в этом режиме — через Agent 7 вручную/через API по решению человека», и не привязывать пункт меню 11.4 к обновлению тела для Confluence-only, либо ввести отдельный сценарий/кнопку «обновить метаданные/историю по PAGE_ID».

---

## D) TOP RISKS (≤10, Impact × Likelihood)

| # | Risk | Impact | Likelihood | I×L |
|---|------|--------|------------|-----|
| 1 | Рассинхрон Confluence и FM_DOCUMENTS (два режима) | High | High | High |
| 2 | Потеря правок при нескольких /apply в Confluence (перезапись) | High | Med | Med-High |
| 3 | Неверный PAGE_ID при смене проекта (env/файл) | High | Med | Med-High |
| 4 | Confluence-only: пункт меню 11.4 падает / бесполезен (AG-12) | Med | High | Med-High |
| 5 | Рассинхрон контекста (docs/PROJECT_CONTEXT vs project PROJECT_CONTEXT) | Med | High | Med |
| 6 | Нет сценария «обновить Confluence без docx» (AG-15) | Med | High | Med |
| 7 | Перезапись .interview_context при двух сессиях одного проекта | Med | Med | Med |
| 8 | Цикл бизнес-согласования без машиночитаемого критерия выхода | Med | Low | Low-Med |
| 9 | Глобальный pipeline state — путаница проектов (AG-14) | Low | Med | Low |
| 10 | Библиотеки lib не в контракте (AG-13) — ложные ожидания | Low | Med | Low |

---

## E) HUMAN-IN-THE-LOOP

Где человек обязателен и почему:

| Место | Причина |
|-------|---------|
| Выбор объёма применяемых правок (/apply) | Агенты 1, 2, 4 при /apply должны спрашивать «все / только критические / номера». Решение о наборе правок — за человеком; иначе риск неконтролируемого изменения ФМ. |
| Подтверждение первой записи в Confluence / смена PAGE_ID | Перед первым PUT новой страницы или смены целевой страницы — dry-run и явное подтверждение; иначе запись в неверную страницу или space. |
| Бизнес-согласование (Approved) | Переход в «Approved» и «отправка на согласование» — решение заказчика; критерий «нет открытых комментариев» проверяем человеком или вручную. |
| Создание проекта и заполнение CONFLUENCE_PAGE_ID | new_project создаёт placeholder; реальный PAGE_ID задаётся человеком при первой публикации или по контракту с подтверждением. |
| Разрешение конфликтов (Confluence vs локальные артефакты) | При расхождении «какая версия верная» решает человек. |
| Запуск каждого этапа пайплайна (orchestrate) | launch_claude_code копирует промпт в буфер; пользователь вставляет в Claude Code и нажимает Enter; без человека этапы не выполняются. |

---

## FINAL VERDICT

**Можно ли системе работать автономно без человека?**

**НЕТ.**

**Конкретные блокирующие места:**

1. **Запуск этапов:** Оркестратор не вызывает Claude/агентов программно; он готовит промпт и копирует в буфер — выполнение каждого этапа требует человека (вставить в Claude Code, подтвердить завершение). Без этого пайплайн не продвигается.

2. **Решение по /apply:** Выбор «какие замечания применить» (все / критические / номера) не формализован для автономного режима; без человека применение всех правок подряд запрещено инструкциями агентов (эскалация).

3. **Публикация в Confluence:** Скрипт publish_to_confluence.py работает только от пути к docx; для Confluence-only нет автоматического пути «обновить страницу по PAGE_ID». Обновление тела страницы после правок агентов в Confluence-only режиме предполагает человека или отдельный не описанный в контракте механизм.

4. **Бизнес-согласование:** Критерий «согласование завершено» (Approved + нет открытых комментариев) не проверяется автоматически в скриптах; переход в Approved и фиксация — за человеком.

5. **PAGE_ID и первая публикация:** Назначение и проверка CONFLUENCE_PAGE_ID при создании/смене проекта — за человеком; иначе риск записи в неверную страницу.

Устранение пунктов 1–2 и формализация 3–5 (включая сценарий обновления Confluence без docx и/или явное закрепление ручных шагов) могли бы сузить зону обязательного human-in-the-loop, но полная автономия «без человека» при текущей спецификации и реализации недостижима.

---

**Дата аудита:** 2026-02-06  
**Ledger:** AG-01…AG-11 — без изменений (не переоткрывались). Новые: AG-12 (регрессия), AG-13, AG-14, AG-15 (MISSING_SPEC / логический пробел).
