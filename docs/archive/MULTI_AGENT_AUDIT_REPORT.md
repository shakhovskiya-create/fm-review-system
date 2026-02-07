# Аудит multi-agent системы FM Review

> **Роль:** Ведущий аудитор multi-agent систем. Только констатация и рекомендации, без изменений кода.
> **Дата:** актуализировано по состоянию репозитория.
> **Основа:** дерево файлов, agents/, scripts/, docs/, workflows/, CLAUDE.md.

---

## 0) EXEC_SUMMARY

- **Масштабируемость:** **Частично.** После исправлений: (1) гейт допускает Confluence-only (FM_DOCUMENTS необязателен); (2) единственный писатель тела страницы — Agent 7, 1–5 передают изменения ему; (3) контекст интервью по проекту (`.interview_context_${PROJECT}.txt`); (4) канон контекста — projects/…/PROJECT_CONTEXT.md; (5) new_project создаёт CHANGES/, CONFLUENCE_PAGE_ID; (6) quality_gate учитывает оба варианта папок 7/8.
- **Топ-3 системных риска (смягчены):** (1) **Источник истины** — два режима явно допущены (Confluence-only или FM_DOCUMENTS); (2) **Write-collision** — в инструкциях 1–5 закреплено «передать Agent 7» и верификация; (3) **PAGE_ID** — файл CONFLUENCE_PAGE_ID создаётся в new_project, скрипты по-прежнему могут использовать env.

---

## 1) AGENTS_MAP

| AgentName | Purpose | Inputs | Outputs | AllowedDecisions | MustEscalate |
|-----------|---------|--------|---------|------------------|--------------|
| Agent 0 (Creator) | Создание ФМ с нуля, интервью, структура | PROJECT_CONTEXT, .interview_context.txt, ответы интервью | Контент ФМ (для Agent 7), PROJECT_[NAME]/ | Структура разделов, формулировки | Смена формата ФМ, новый проект без подтверждения |
| Agent 1 (Architect) | Аудит ФМ (бизнес + 1С), поиск дыр | Confluence (PAGE_ID), PROJECT_CONTEXT, AGENT_* | AGENT_1_ARCHITECT/*.md, findings; при /apply — правки в Confluence | Классификация замечаний, предложение правок | Применение всех правок без выбора пользователя |
| Agent 2 (Role Simulator) | Симуляция ролей, UX, обходы | Confluence, AGENT_1_ARCHITECT, PROJECT_CONTEXT | AGENT_2_ROLE_SIMULATOR/*.md; при /apply — правки в Confluence | Приоритизация UX-правок | Изменение структуры документа |
| Agent 3 (Defender) | Ответы на замечания, классификация A–I | AGENT_1/2/4, Confluence, PROJECT_CONTEXT | AGENT_3_DEFENDER/*.md; при /apply — правки в Confluence | Классификация, аргументация | Принятие/отклонение без решения пользователя |
| Agent 4 (QA Tester) | Тест-кейсы, покрытие, манипуляции | AGENT_1/2, Confluence, PROJECT_CONTEXT | AGENT_4_QA_TESTER/*.md; при /apply — правки в Confluence | Приоритет тестов | Изменение требований без трассировки к finding |
| Agent 5 (Tech Architect) | Архитектура 1С, ТЗ, оценка | AGENT_1/2/4, Confluence, PROJECT_CONTEXT | AGENT_5_TECH_ARCHITECT/*.md; при /apply — правки в Confluence | Решения 1С, оценка | Изменение бизнес-правил (зона Agent 1) |
| Agent 6 (Presenter) | Презентации, отчёты, экспорт | Все AGENT_*/, Confluence, PROJECT_CONTEXT | AGENT_6_PRESENTER/*; не пишет в Confluence | Формат и аудитория | Публикация в Confluence (делегирует Agent 7) |
| Agent 7 (Publisher) | Публикация/обновление ФМ в Confluence, XHTML | PAGE_ID, контент от 0–5, PROJECT_CONTEXT | Confluence (PUT/POST), AGENT_7_PUBLISHER/*, обновление PROJECT_CONTEXT (URL) | GET перед PUT, комментарий версии | Создание страницы в другом space без подтверждения |
| Agent 8 (BPMN Designer) | BPMN 2.0, drawio, публикация в Confluence | Confluence (ФМ), AGENT_1/2/7, bpmn-processes/*.json | scripts/bpmn-processes/, scripts/output/, вложения Confluence | Нотация и разметка BPMN | Изменение текста ФМ на странице |

**Пересечения/пробелы:** Агенты 1, 2, 4, 5 пересекаются по праву записи в Confluence при /apply. Нет явного владельца «тела страницы ФМ». Agent 3 вызывается по запросу (бизнес-замечания); в пайплайне полного цикла не участвует последовательно.

---

## 2) FINDINGS

### AG-01 — Скрипты интервью агентов (ИСПРАВЛЕНО)
- **Severity:** было High.
- **Evidence:** В `scripts/` присутствуют `agent0_new.sh` … `agent5_architect.sh`; `orchestrate.sh` их вызывает (строки 147, 163, 172, 180, 188, 196).
- **Статус:** Реализованы; пункты 2–7 меню не падают по отсутствию файла.

### AG-02 — Два конкурирующих источника истины по ФМ (СМЯГЧЕНО)
- **Severity:** было High.
- **Evidence:** как выше.
- **Исправление:** `quality_gate.sh`: FM_DOCUMENTS и «ФМ не найдена» — check_warn (допустимо Confluence-only). `orchestrate.sh`: при отсутствии FM_PATH передаётся «Confluence (PAGE_ID из проекта)», полный цикл не падает.
- **Остаётся:** Явно зафиксировать в документации два режима (Confluence-only vs legacy Word) при желании.

### AG-03 — Множественная запись в одну Confluence-страницу (ИСПРАВЛЕНО)
- **Severity:** было High.
- **Исправление:** В агентах 1, 2, 3, 4, 5 секция «ПОСЛЕ /apply» заменена на: «Передать изменения Agent 7 для обновления в Confluence (единственный писатель тела страницы — Agent 7); верификация: GET страницы или Agent 7 /verify».

### AG-04 — Контекст интервью в одном глобальном файле (ИСПРАВЛЕНО)
- **Severity:** было Med.
- **Исправление:** `common.sh`: введён `get_context_file()` → `.interview_context_${PROJECT:-global}.txt`; `save_context`/`load_context` используют его. В `orchestrate.sh` перед вызовом agent-скриптов выполняется `export PROJECT`.

### AG-05 — Два места PROJECT_CONTEXT (СМЯГЧЕНО)
- **Severity:** было Med.
- **Исправление:** В CLAUDE.md (автосохранение) зафиксирован канон: контекст проекта — `PROJECT_[NAME]/PROJECT_CONTEXT.md`; агенты читают/обновляют только его; `docs/PROJECT_CONTEXT.md` — системный/архивный.

### AG-06 — Папка CHANGES не используется по правилу (СМЯГЧЕНО)
- **Severity:** было Med.
- **Исправление:** `new_project.sh` создаёт папку `CHANGES/`. В CLAUDE.md указано: сохранять в `PROJECT_[NAME]/CHANGES/`; при отсутствии папки допустимо FM_DOCUMENTS/. quality_gate проверяет наличие CHANGES/ (warn при отсутствии).

### AG-07 — Quality Gate проверяет открытые замечания по тексту (СМЯГЧЕНО)
- **Severity:** было Low.
- **Исправление:** В quality_gate.sh grep расширен: `CRITICAL.*(Открыт|Open)`, `HIGH.*(Открыт|Open)` — учёт обоих вариантов статуса.

### AG-08 — CONFLUENCE_PAGE_ID без единого источника (СМЯГЧЕНО)
- **Severity:** было Med.
- **Исправление:** `new_project.sh` создаёт файл `CONFLUENCE_PAGE_ID` в корне проекта (placeholder «заполнить при первой публикации»). Скрипты по-прежнему могут использовать env; чтение из файла проекта — следующий шаг при необходимости.

### AG-09 — Workflow и Agent 8 (ИСПРАВЛЕНО)
- **Severity:** было Low.
- **Evidence:** `workflows/fm-workflows.md`: Agent 8 (BPMN), «BPMN в Confluence (drawio)», команды /publish, /bpmn. Соответствует `agents/AGENT_8_BPMN_DESIGNER.md`.
- **Статус:** Workflow приведён к BPMN/Confluence.

### AG-10 — Верификация после /apply не закреплена в агентах 1–5 (ИСПРАВЛЕНО)
- **Severity:** было Med.
- **Исправление:** В инструкциях агентов 1–5 в блоке «ПОСЛЕ /apply» добавлено: «Верификация: GET страницы или Agent 7 /verify».

### AG-11 — quality_gate: имена папок агентов 7/8 vs имена файлов (ИСПРАВЛЕНО)
- **Severity:** было Low.
- **Исправление:** `new_project.sh` создаёт папки `AGENT_7_PUBLISHER`, `AGENT_8_BPMN_DESIGNER`. `quality_gate.sh` проверяет оба варианта: при отсутствии PUBLISHER — смотрит MIGRATOR, при отсутствии BPMN_DESIGNER — EPC_DESIGNER (обратная совместимость со старыми проектами).

---

## 3) LOGIC_GAPS

- **Циклы без выхода:** Бизнес-согласование (ЭТАП 4): цикл Agent 3 → Agent 0 → Agent 7 /sync до снятия замечаний. Критерий «все замечания сняты» не формализован (нет машинного статуса или гейта).
- **Шаги без единственного владельца:** Запись тела страницы ФМ в Confluence (AG-03). Обновление PROJECT_CONTEXT — несколько агентов «дополняют», место и формат размыты (AG-05).
- **Решения без критериев:** Выбор «какие замечания применить» при /apply — на пользователя; при /auto критерий не зафиксирован в спецификации.
- **Состояния без проверяемости:** Статусы Draft/Review/Approved в workflow и Confluence; quality_gate и скрипты их не проверяют; нет контракта «согласование завершено, если …».

---

## 4) STRUCTURE_RISKS

- **Single source of truth:** ФМ — заявлен Confluence, но FM_DOCUMENTS и get_latest_fm/quality_gate опираются на файлы (AG-02). Контекст — раздвоение docs/PROJECT_CONTEXT.md и projects/…/PROJECT_CONTEXT.md (AG-05).
- **Write-collisions:** Одна Confluence-страница ФМ — потенциальные писатели 0, 1, 2, 3, 4, 5, 7 (AG-03). Один .interview_context.txt (AG-04).
- **Missing specs:** Нет явного протокола «кто когда пишет в Confluence» и «кто верифицирует после записи». Файл CONFLUENCE_PAGE_ID в проекте не создаётся по умолчанию (AG-08).

---

## 5) TOP10_RISKS (Impact × Likelihood)

1. Рассинхрон Confluence vs FM_DOCUMENTS — высокий impact, высокая вероятность.
2. Потеря правок при нескольких /apply в Confluence — высокий impact, средняя вероятность.
3. Неверный PAGE_ID при смене проекта — высокий impact, средняя вероятность.
4. Рассинхрон контекста (docs vs project PROJECT_CONTEXT) — средний impact, высокая вероятность.
5. Перезапись .interview_context.txt при двух сессиях — средний impact, средняя вероятность.
6. Отсутствие верификации после PUT у агентов 1–5 — средний impact, средняя вероятность.
7. Цикл бизнес-согласования без критерия выхода — средний impact, низкая вероятность.
8. Quality Gate на свободном тексте (CRITICAL/HIGH) — низкий impact, средняя вероятность.
9. Путаница имён папок агентов 7/8 (MIGRATOR/EPC_DESIGNER vs PUBLISHER/BPMN) — низкий impact.
10. CHANGES/ не создаётся, правило не соблюдается — низкий impact.

---

## 6) HUMAN_IN_LOOP

- **Выбор объёма применяемых правок:** Agent 1/2/4 при /apply должны спрашивать «все / только критические / номера». Решение — за человеком.
- **Подтверждение записи в Confluence:** Перед первым PUT новой страницы или смены PAGE_ID — dry-run и подтверждение.
- **Бизнес-согласование:** Переход в Approved и «отправка на согласование» — решение человека.
- **Создание проекта и назначение CONFLUENCE_PAGE_ID:** За человеком или чётким контрактом с подтверждением.
- **Разрешение конфликтов:** При расхождении Confluence и локальных артефактов — «какая версия верная» решает человек.

---

## 7) RECOMMENDATIONS (без внедрения)

1. Формализовать единственный источник ФМ: Confluence — тогда убрать обязательность FM_DOCUMENTS в quality_gate и перевести get_latest_fm на PAGE_ID/API; либо два явных режима.
2. Ввести единственного писателя тела страницы ФМ в Confluence: только Agent 7 выполняет PUT; агенты 0–5 при /apply отдают изменения Agent 7 или в очередь; в инструкциях 0–5 заменить «Обновление ФМ → Confluence (PUT API)» на передачу изменений Agent 7.
3. Унифицировать контекст проекта: один канон — projects/…/PROJECT_CONTEXT.md с обязательным обновлением; docs — архив/глобальный лог или явная привязка по проекту.
4. Контекст интервью на проект или сессию: .interview_context_${PROJECT}.txt или передача только в промпте.
5. Единый источник CONFLUENCE_PAGE_ID на проект: файл PROJECT_[NAME]/CONFLUENCE_PAGE_ID; скрипты читают его; убрать дефолт 83951683 при работе с произвольным проектом.
6. Гейт выхода из цикла согласования: критерий «согласование завершено» (например Approved + нет открытых комментариев) и при необходимости проверка в quality_gate.
7. Верификация после изменения Confluence: после каждого PUT — GET и проверка; в инструкциях 1–5 закрепить делегирование Agent 7 /verify или явный шаг самопроверки.
8. Расположение CHANGES: либо FM-*-CHANGES.md в PROJECT_[NAME]/CHANGES/, либо зафиксировать в правиле хранение в FM_DOCUMENTS.
9. Машиночитаемый статус findings для quality_gate: единый формат статуса замечаний, парсинг по нему вместо grep по тексту.
10. Явный dry-run перед первой публикацией в Agent 7 при создании страницы или смене PAGE_ID.
11. (Опционально) Имена папок агентов 7/8: привести к AGENT_7_PUBLISHER, AGENT_8_BPMN_DESIGNER в new_project.sh и quality_gate для единообразия с именами файлов агентов.

---

## FINAL CHECK

**Можно ли доверить автономную работу без человека?**  
**Нет.**

**Условия для допустимой автономии:**

1. Единственный источник ФМ (Confluence); quality_gate и get_latest_fm не опираются на FM_DOCUMENTS без явного режима.
2. Единственный писатель тела страницы ФМ (Agent 7); агенты 1–5 не выполняют PUT сами, а передают изменения Agent 7.
3. Единый контекст на проект (один PROJECT_CONTEXT) и контекст интервью не глобальный.
4. Обязательная верификация после каждой записи в Confluence (GET + проверка).
5. Критерий выхода из цикла бизнес-согласования и при необходимости проверка в гейте.
6. Решение «какие правки применить» после аудита/симуляции/тестов за человеком или явно формализовано в спецификации.

Без этого автономный запуск с записью в Confluence несёт риски потери правок, записи в неверную страницу и работы с рассинхронизированными артефактами.

---

## 8) ФИНАЛЬНЫЙ АУДИТ И АРХИТЕКТУРА

**Подробный финальный аудит и мнение по архитектуре:** см. [docs/FINAL_AUDIT_AND_ARCHITECTURE.md](FINAL_AUDIT_AND_ARCHITECTURE.md).

**Кратко:**
- После исправлений система согласована: один писатель (Agent 7), контекст по проекту, гейт допускает Confluence-only. Готовность к использованию — да.
- Дополнительно: два режима ФМ и PAGE_ID документированы в README; скрипты читают PAGE_ID из файла проекта (PROJECT или путь к doc); критерий завершения согласования зафиксирован в workflows и CLAUDE; README обновлён; BPMN = generate-bpmn.js + publish-bpmn.py — штатная цепочка, документирована.
- Архитектура и выбор инструментов (Claude как агенты, Bash/gum, Confluence, Python, BPMN/drawio) соответствуют цели полного цикла ФМ для 1С.
