# todos - журнал правок ФМ (append-only)

Правила:
- Не затирать файл и не перегенерировать "с нуля".
- Каждая правка фиксируется в новой записи (в конце файла).
- Чекбоксы можно помечать выполненными точечным редактированием строки.
- Каждая запись обязана содержать: План -> Действие -> Проверка -> Изменения (что было/стало).
- **ОБЯЗАТЕЛЬНО**: После завершения работ - push в remote и merge в main (https://github.com/shakhovskiya-create).

---

## SESSION 2026-02-05 19:00 - Исправление Confluence публикации

### Контекст
- Документ: FM-LS-PROFIT-v1.2.1.docx
- Цель: publish_to_confluence.py -> Confluence страница 83951683
- Основание: замечания пользователя (дата, история версий, система кодов, заливка ⚠️/⛔)

### Сканирование документа (факты)
- Мета-таблица (table 0): Версия="", Дата=29.01.2026, Статус=Разработка, Автор=Шаховский А.С.
- История версий (table 1, 8x4): 3 реальных записи (1.0, 1.2.0, 1.1.0) + 5 пустых строк
- Система кодов (table 24, 77x3): заголовки Код/Наименование/Описание, 76 строк данных
- 1x1 таблицы-панели: 2 шт.
  - table 4: ⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ, цвет=FAE2D5
  - table 9: ⚠ ИСКЛЮЧЕНИЕ: НЕЛИКВИДНЫЙ ТОВАР, цвет=FAE2D5
- ⚠️ в параграфах: 21 шт. (обычный текст, не в таблицах, без заливки)

### План (чек-лист)
- [x] STEP-01: Мета-таблица - дата автоматом (datetime.now), не из Word
- [x] STEP-02: История версий - оставить только 1 запись "1.0.0 | текущая дата | Первая публикация"
- [x] STEP-03: Система кодов 77x3 - убедиться что рендерится как таблица, убрать дубли-текст
- [x] STEP-04: ⚠️ параграфы (21 шт.) - заливка светло-желтым, ⛔ таблица - note панель (красная)

### Лог выполнения (добавлять после каждого шага)

#### STEP-01 - Мета-таблица: дата автоматом
План: Подменить дату в мета-таблице (table 0, 4x2) на datetime.now()
Действие: Добавил функцию `is_meta_table()` и `meta_table_to_html()` в publish_to_confluence.py:193-218. При рендере таблицы с Версия/Дата/Статус/Автор подменяет Дата на текущую и Версия на FM_VERSION.
Проверка: `re.search(r'05\.02\.2026', content)` -> True, дата в meta-секции = 05.02.2026
Изменения:
- Было: Дата = 29.01.2026 (захардкожена в Word)
- Стало: Дата = 05.02.2026 (datetime.now при каждой публикации)
Статус: DONE

---

#### STEP-02 - История версий: обнулить
План: Оставить в таблице истории (table 1, 8x4) только 1 запись "1.0.0"
Действие: Добавил `history_table_to_html()` (строка 220-234). Баг: `is_history_table` искал 'версия' в "Номер верси**и** документа" - не находил. Исправил на 'верси' (ловит и версия, и версии).
Проверка: '1.2.0' NOT in content = True, '1.1.0' NOT in content = True, '1.0.0' in content = True
Изменения:
- Было: 3 записи (1.0, 1.2.0, 1.1.0) + 5 пустых строк
- Стало: 1 запись (1.0.0 | 05.02.2026 | Шаховский А.С. | Первая публикация)
Статус: DONE

---

#### STEP-03 - Система кодов: таблица 77x3
План: Убедиться что таблица 24 (77x3, Код/Наименование/Описание) рендерится как таблица, не текст. Убрать дубли-параграфы.
Действие: Таблица уже конвертировалась корректно (table_to_html). Добавил установку `skip_code_system_descriptions = True` после обнаружения таблицы с Код+Наименование (строка 400-403). SKIP_AFTER_CODE_SYSTEM фильтрует "Маршруты согласования", "Дашборды и аналитика" и т.д.
Проверка: 'LS-BR-001' in content = True, в контексте таблицы. 'Маршруты согласования' not in content (как отдельный параграф) = True.
Изменения:
- Было: Таблица 77x3 + дублирующиеся параграфы-описания после нее
- Стало: Только таблица 77x3, параграфы-дубли отфильтрованы
Статус: DONE

---

#### STEP-04 - Заливка: ⚠️ желтым, ⛔ красным
План: 21 параграф с ⚠️ -> warning panel (желтая). 1x1 таблица с ⛔ -> note panel (красная). 1x1 таблица с ⚠ -> warning panel (желтая).
Действие:
- Параграфы: Добавлена проверка `text.startswith('⚠')` перед обработкой списков (строка 348-357). Оборачивает в `ac:structured-macro ac:name="warning"`.
- Таблица 4 (⛔): `is_warning_table()` определяет 'критич' -> return 'note'. Рендерится через `ac:name="note"` (красная панель).
- Таблица 9 (⚠): `is_warning_table()` определяет 'исключение' -> return 'warning'. Рендерится через `ac:name="warning"` (желтая панель).
Проверка: warning панелей = 22 (21 параграф + 1 таблица ⚠ ИСКЛЮЧЕНИЕ), note = 1 (⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ), info = 0 (нет синих)
Изменения:
- Было: ⚠️ параграфы = обычный текст без заливки. ⛔ таблица = info panel (синяя) или обычная таблица. ⚠ таблица = info panel (синяя).
- Стало: 22 warning panels (светло-желтые), 1 note panel (светло-красная), 0 info panels
Статус: DONE

---

### Финальная проверка (автоматическая верификация)

| Критерий | Результат | Метод проверки |
|----------|-----------|----------------|
| Дата = текущая (05.02.2026) | OK | `re.search('05.02.2026', content)` |
| История = только 1.0.0 | OK | `'1.2.0' not in content AND '1.1.0' not in content` |
| Система кодов = таблица | OK | `'LS-BR-001' in content` в контексте `<table>` |
| ⚠️ = warning panels (22) | OK | `content.count('ac:name="warning"') == 22` |
| ⛔ = note panel (1) | OK | `content.count('ac:name="note"') == 1` |
| info panels (синие) = 0 | OK | `content.count('ac:name="info"') == 0` |
| Дубли текста = нет | OK | 'Маршруты согласования' не в content как отдельный параграф |

Confluence page version: 5
URL: https://confluence.ekf.su/pages/viewpage.action?pageId=83951683

---

## SESSION 2026-02-05 (продолжение) - Исправления v6

### Контекст
- Замечания: система кодов текстом, ⛔ не красная, ⚠️ не желтая, эмодзи не убраны
- Причина: макросы Confluence Server были перепутаны (note=жёлтая, warning=красная)

### План (чек-лист)
- [x] STEP-05: Система кодов типов (LS-BR-XXX и т.д.) - собрать параграфы в таблицу
- [x] STEP-06: ⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ - warning macro (красная панель)
- [x] STEP-07: ⚠️ параграфы - note macro (жёлтая панель), убрать эмодзи из текста

### Лог выполнения

#### STEP-05 - Система кодов типов: параграфы -> таблица
План: 7 параграфов вида "• LS-XX-XXX - Описание" + 7 строк-описаний собрать в таблицу 7x2 (Код | Описание)
Действие: Добавил `in_code_system_section` + `code_system_items` коллектор (строки 344-385). При обнаружении заголовка "Система кодов" включается сбор. Regex `^[•\-]\s*(LS-\w+-XXX)\s*[-–]\s*(.+)` парсит код и описание. При следующем Heading генерируется таблица.
Проверка:
- LS-BR-XXX в `<td>` = True
- LS-FR-XXX в `<td>` = True
- LS-WF-XXX в `<td>` = True (включая "Маршруты согласования" как описание)
- LS-RPT-XXX, LS-NFR-XXX, LS-INT-XXX, LS-SEC-XXX в `<td>` = True
- Все 7 кодов в таблице, 0 как `<p>` параграфы
Изменения:
- Было: 7 типов кодов отображались как текстовые параграфы (буллеты)
- Стало: Таблица 7x2 (Код | Описание) с жирным кодом в первой колонке
Статус: DONE

---

#### STEP-06 - ⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ: warning macro (КРАСНАЯ)
План: Перепутаны макросы. В Confluence Server: note=жёлтая, warning=красная. Нужно: ⛔ -> warning (красная)
Действие: Исправил `is_warning_table()`: критические ключевые слова ('критич', 'зависимость') -> return 'warning'. В `table_to_html()`: panel_type='warning' -> `ac:name="warning"`. Эмодзи ⛔ убирается из текста.
Проверка: warning macro = 1 шт, содержимое = "КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ..."
Изменения:
- Было: `is_warning_table` возвращал 'note' для критических -> жёлтая панель
- Стало: Возвращает 'warning' -> красная панель в Confluence
Статус: DONE

---

#### STEP-07 - ⚠️ параграфы: note macro (ЖЁЛТАЯ), без эмодзи
План: ⚠️ параграфы -> note macro (жёлтая в Confluence Server). Убрать эмодзи из текста панели.
Действие:
- Параграфы: `text.startswith('⚠')` -> `ac:name="note"` (было "warning")
- Таблица ⚠ ИСКЛЮЧЕНИЕ: `is_warning_table` -> return 'note' (жёлтая)
- Эмодзи: `re.sub(r'^[⚠️\ufe0f]+\s*', '', text)` убирает ⚠️ из начала
Проверка:
- note macro = 22 шт (21 параграф + 1 таблица ⚠ ИСКЛЮЧЕНИЕ)
- warning macro = 1 шт (⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ)
- info macro = 0 шт
- Эмодзи ⚠ в панелях = 0, эмодзи ⛔ в панелях = 0
Изменения:
- Было: ⚠️ параграфы -> ac:name="warning" (красная), эмодзи оставались в тексте
- Стало: ⚠️ параграфы -> ac:name="note" (жёлтая), эмодзи убраны
Статус: DONE

---

### Финальная проверка v6

| Критерий | Результат | Метод проверки |
|----------|-----------|----------------|
| Дата = текущая (05.02.2026) | OK | 3 вхождения в content |
| История = только 1.0.0 | OK | '1.2.0' и '1.1.0' отсутствуют |
| Система кодов типов = таблица 7x2 | OK | Все 7 LS-XX-XXX в `<td>`, 0 в `<p>` |
| Система кодов (77x3) = таблица | OK | LS-BR-001 в контексте `<table>` |
| ⛔ = warning macro (красная) | OK | 1 шт, текст без эмодзи |
| ⚠️ = note macro (жёлтая) | OK | 22 шт, текст без эмодзи |
| info panels = 0 | OK | 0 синих панелей |
| Дубли = нет | OK | "Маршруты согласования" только в `<td>` |

Confluence page version: 6
URL: https://confluence.ekf.su/pages/viewpage.action?pageId=83951683

---

## SESSION 2026-02-05 (вечер) - Миграция на Confluence + аудит системы

### Контекст
- Решение: полностью отказаться от Notion, ориентир только на Confluence
- Задачи: шаблон Confluence, оглавление (toc), аудит агентов, удаление Notion артефактов, настройка Miro
- Правило: todos.md = append-only журнал

### Сканирование (факты)
- Файлов с упоминанием Notion: 29
- Агентов: 9 (AGENT_0..AGENT_8), все упоминают Notion
- Notion-скрипты: publish_to_notion.py, setup_notion.py, verify_notion.py
- Notion-конфиг: docs/notion-config.json
- Notion-шаблоны: templates/fm-notion-page.md, templates/fm-notion-template-structure.md
- Notion-схемы: schemas/notion-databases.md
- CLAUDE.md: 47 упоминаний Notion
- Miro: упоминается в AGENT_8, CLAUDE.md, но MCP не настроен

### План (чек-лист)
- [x] STEP-11: Создать шаблон Confluence публикации (docs/CONFLUENCE_TEMPLATE.md)
- [x] STEP-12: Добавить оглавление (toc macro) в скрипт публикации + опубликовать
- [x] STEP-13: Аудит 9 агентов - логика, совместимость, ошибки
- [x] STEP-14: Переориентация CLAUDE.md на Confluence (убрать Notion)
- [x] STEP-15: Переориентация агентов на Confluence (убрать Notion)
- [x] STEP-16: Удалить/архивировать Notion скрипты и конфиги
- [x] STEP-17: Обновить workflows, templates, schemas для Confluence
- [x] STEP-18: Настроить Miro для ePC диаграмм

### Лог выполнения

#### STEP-11 - Шаблон Confluence публикации
План: Создать эталонный шаблон docs/CONFLUENCE_TEMPLATE.md с XHTML компонентами для Confluence.
Действие: Создан файл docs/CONFLUENCE_TEMPLATE.md. Содержит: структуру страницы (мета-блок, оглавление, мета-таблица, история версий, система кодов, панели warning/note, таблица требований), XHTML шаблоны компонентов (toc macro, таблицы, панели, заголовки), параметры Confluence API.
Проверка: Файл создан, все XHTML шаблоны валидны, соответствуют Confluence Server макросам.
Изменения:
- Было: Нет шаблона, скрипт publish_to_confluence.py - единственный источник правды
- Стало: docs/CONFLUENCE_TEMPLATE.md - эталонная структура + XHTML шаблоны
Статус: DONE

---

#### STEP-12 - Оглавление (toc macro) + публикация v7
План: Добавить `<ac:structured-macro ac:name="toc">` в скрипт publish_to_confluence.py после мета-блока.
Действие: Добавил toc macro в header секцию (строка 322-326 publish_to_confluence.py). Макрос генерирует автооглавление из H1-H3. Опубликовал страницу.
Проверка: Confluence page version = 7, toc macro присутствует в content, оглавление отображается на странице.
Изменения:
- Было: Страница без оглавления, навигация затруднена
- Стало: Автоматическое оглавление (toc macro, maxLevel=3)
Статус: DONE

---

#### STEP-13 - Аудит 9 агентов
План: Проверить все агенты на: совместную работу, логические ошибки, совместимость, упоминания Notion.
Действие: Запустил 4 параллельных Explore-агента для сканирования всех 9 агентов. Результаты:
- Agent 0: 3 Notion -> Confluence
- Agent 1: 3 Notion -> Confluence
- Agent 2: 3 Notion -> Confluence
- Agent 3: 2 Notion -> Confluence
- Agent 4: 2 Notion -> Confluence
- Agent 5: 3 Notion -> Confluence
- Agent 6: 11 Notion -> Confluence
- Agent 7: 98 Notion (полная переработка, см. STEP-15)
- Agent 8: 5 Notion -> Confluence
- CLAUDE.md: 47 Notion (см. STEP-14)
Проверка: Все агенты 0-6, 8 обновлены, 0 Notion упоминаний в каждом.
Изменения:
- Было: Все 9 агентов ориентированы на Notion
- Стало: Все 9 агентов ориентированы на Confluence
Статус: DONE

---

#### STEP-14 - CLAUDE.md: Notion -> Confluence
План: Убрать все 47 упоминаний Notion из CLAUDE.md, заменить на Confluence.
Действие: 6 критических секций переписаны:
1. Описание системы: "миграция в Notion" -> "публикация в Confluence"
2. Описание Agent 7: "миграция Word -> Notion" -> "публикация Word -> Confluence"
3. Router: "Мигрируй в Notion" -> "Опубликуй в Confluence"
4. Pipeline: полная переработка с NOTION-FIRST на CONFLUENCE-FIRST
5. MCP секция: убран Notion MCP, добавлен Confluence API
6. Business approval: все Notion -> Confluence
Проверка: grep -c "Notion" CLAUDE.md = 0 (кроме archive ссылок)
Изменения:
- Было: 47 упоминаний Notion
- Стало: 0 упоминаний Notion, полный ориентир на Confluence
Статус: DONE

---

#### STEP-15 - Agent 7: полная переработка
План: Переписать Agent 7 с "Migrator Word -> Notion" на "Publisher Word -> Confluence" (98 упоминаний Notion).
Действие: Полная переработка файла agents/AGENT_7_MIGRATOR.md:
- Роль: Migrator -> Publisher
- Команды: /migrate -> /publish, /sync -> /update, /validate -> /verify
- Инструменты: Notion MCP tools -> Confluence REST API
- 5 БД Notion -> единая Confluence страница с встроенным версионированием
- Notion relations -> Confluence макросы и метки
Проверка: grep -c "Notion" AGENT_7_MIGRATOR.md = 0
Изменения:
- Было: 98 упоминаний Notion, полностью Notion-ориентированный агент
- Стало: 0 Notion, Confluence REST API, XHTML storage format
Статус: DONE

---

#### STEP-16 - Удаление Notion артефактов
План: Перенести Notion-специфичные файлы в .archive_notion/, очистить ссылки.
Действие: 7 файлов перемещены в .archive_notion/:
- scripts/publish_to_notion.py
- scripts/setup_notion.py
- scripts/verify_notion.py
- docs/notion-config.json
- schemas/notion-databases.md
- templates/fm-notion-page.md
- templates/fm-notion-template-structure.md
Проверка: Файлы существуют в .archive_notion/, отсутствуют в исходных директориях.
Изменения:
- Было: 7 Notion-специфичных файлов в рабочих директориях
- Стало: 7 файлов в .archive_notion/ (не удалены, архивированы)
Статус: DONE

---

#### STEP-17 - Обновление документации и скриптов
План: Обновить все оставшиеся файлы: README, PROMPTS, workflows, scripts.
Действие: Массовые замены Notion -> Confluence:
- README.md: 9 правок
- docs/PROMPTS.md: 14 правок
- workflows/fm-workflows.md: 29 правок
- scripts/orchestrate.sh: 8 правок
- scripts/new_project.sh: 1 правка
- scripts/quality_gate.sh: 5 правок
- templates/requirement-template.md: 1 правка
Проверка: grep -r "Notion" по всем обновленным файлам = 0 (кроме .archive_notion/)
Изменения:
- Было: ~67 упоминаний Notion в 7 файлах
- Стало: 0 упоминаний, все ориентировано на Confluence
Статус: DONE

---

#### STEP-18 - Настройка Miro MCP
План: Подключить Miro MCP для Agent 8 (ePC диаграммы).
Действие: Выполнил `claude mcp add --transport http miro https://mcp.miro.com`. MCP сервер добавлен в конфигурацию проекта. Обновил CLAUDE.md (секция настройки Miro) с актуальной командой.
Проверка: `claude mcp list` показывает: figma - Connected, miro - Needs authentication. OAuth аутентификация произойдет при первом использовании.
Изменения:
- Было: Только Figma MCP настроен, Miro отсутствует
- Стало: Figma + Miro MCP настроены. Miro требует OAuth при первом запуске.
Статус: DONE

---

### Финальная проверка (вечерняя сессия)

| Критерий | Результат | Метод проверки |
|----------|-----------|----------------|
| Шаблон Confluence создан | OK | docs/CONFLUENCE_TEMPLATE.md существует |
| TOC macro добавлен | OK | Confluence page v7, toc в content |
| Агенты 0-8: 0 Notion | OK | grep -r "Notion" agents/ = 0 |
| CLAUDE.md: 0 Notion | OK | grep -c "Notion" CLAUDE.md = 0 |
| Notion файлы архивированы | OK | 7 файлов в .archive_notion/ |
| Документация обновлена | OK | README, PROMPTS, workflows, scripts |
| Miro MCP настроен | OK | claude mcp list -> miro: Needs auth |

---

## SESSION 2026-02-05 (поздний вечер) - Убрать TOC

### Контекст
- Замечание: toc macro смотрится плохо (inline блок в теле страницы)
- Вопрос: можно ли боковую навигацию как в Word?
- Ответ: Confluence Server не поддерживает side-TOC по заголовкам (только сторонние плагины)
- Решение: убрать toc, не использовать

### План (чек-лист)
- [x] STEP-20: Убрать toc macro из скрипта и опубликовать

### Лог выполнения

#### STEP-20 - Убрать toc macro
План: Удалить `ac:structured-macro ac:name="toc"` из publish_to_confluence.py, обновить шаблон и requirements.
Действие: Убрал 3 строки toc macro из header в publish_to_confluence.py. Убрал блок "Оглавление" из CONFLUENCE_TEMPLATE.md. Обновил CONFLUENCE_REQUIREMENTS.md (требование 13 -> УБРАНО, удален toc из автополей). Опубликовал.
Проверка: Confluence page version = 8, toc macro отсутствует в content.
Изменения:
- Было: toc macro в header -> inline оглавление на странице
- Стало: Без оглавления, чистая страница
Статус: DONE

---

## SESSION 2026-02-05 (поздний вечер, продолжение) - Экспорт из Confluence

### Контекст
- Проблема: встроенный экспорт Confluence ломает шрифты (PDF) и формат (Word)
- Решение: собственный скрипт export_from_confluence.py
- Инструменты: WeasyPrint (PDF), python-docx (Word), BeautifulSoup (парсинг XHTML)

### План (чек-лист)
- [x] STEP-21: Создать export_from_confluence.py (PDF + Word)

### Лог выполнения

#### STEP-21 - Скрипт экспорта из Confluence
План: Создать скрипт, который забирает XHTML через REST API и генерирует PDF (WeasyPrint) и Word (python-docx) с контролем шрифтов и форматирования.
Действие: Создан scripts/export_from_confluence.py:
- Забирает страницу через GET /rest/api/content/{PAGE_ID}?expand=body.storage,version
- Конвертирует Confluence макросы (warning/note/info) в стилизованные div
- PDF: WeasyPrint с CSS (A4, шрифт Segoe UI, колонтитулы, нумерация страниц, цветные панели)
- Word: python-docx с таблицами, заголовками, форматированием, цветными панелями через shading
- macOS: авто-реексек с DYLD_LIBRARY_PATH=/opt/homebrew/lib для WeasyPrint
- Аргументы: --pdf, --docx, --both (default), --page=ID
Проверка:
- PDF: 166 KB, генерируется успешно
- Word: 83 KB, генерируется успешно
- Оба файла в exports/FM-LS-PROFIT_v8_*.{pdf,docx}
Изменения:
- Было: Только встроенный экспорт Confluence (ломает шрифты и формат)
- Стало: Собственный скрипт с полным контролем (WeasyPrint + python-docx)
Статус: DONE

---

## STEP-10: Confluence = единственный источник ФМ (убрать Word как источник)
Дата: 05.02.2026
Задача: Сделать Confluence единственным источником истины для ВСЕХ агентов. Убрать все ссылки на Word/DOCX как источник данных.

План:
- [x] Сканировать все файлы на упоминания Word/DOCX как источника
- [x] Исправить CLAUDE.md (секции 3.1, 5, 6, 7, 8, 10, pipeline, кросс-агенты)
- [x] Полностью переписать AGENT_7_MIGRATOR.md (Word->Confluence -> Confluence-only)
- [x] Исправить AGENT_0_CREATOR.md (убрать FM_DOCUMENTS, /export docx)
- [x] Исправить AGENT_1_ARCHITECT.md (FM_DOCUMENTS -> Confluence REST API)
- [x] Исправить AGENT_2,3,4,5,6,8 (FM_DOCUMENTS -> Confluence REST API)
- [x] Исправить workflows/fm-workflows.md (workflow 2 полностью переписан)
- [x] Исправить docs/PROMPTS.md (убрать .docx пути)
- [x] Исправить README.md (Word->Confluence -> Confluence-only)
- [x] Исправить docs/CONFLUENCE_TEMPLATE.md (убрать python-docx)
- [x] DOCX_EDIT_SKILL.md -> deprecated (переименован)
- [x] Финальная проверка grep: 0 активных ссылок на Word как источник

Действие:
- CLAUDE.md: секция 3.1 полностью переписана (130 строк .NET OpenXML SDK -> Confluence REST API)
- AGENT_7: полный rewrite 555 строк -> 478 строк Confluence-only
- Все агенты 0-6, 8: FM_DOCUMENTS/FM-*-v*.docx -> Confluence REST API (PAGE_ID)
- Все агенты: "Новая версия ФМ -> FM_DOCUMENTS/" -> "Обновление ФМ -> Confluence (PUT API)"
- workflows: Workflow 2 "Публикация Word -> Confluence" -> "Управление ФМ в Confluence"
- PROMPTS: FM-SHPMNT-PROFIT-v2.5.3.docx -> Confluence PAGE_ID 83951683
- README: Word -> Confluence -> Confluence-only, FM_DOCUMENTS -> CONFLUENCE_PAGE_ID

Проверка:
- grep по активным файлам (agents/, CLAUDE.md, workflows/, README.md, docs/PROMPTS.md):
  - 0 ссылок на FM_DOCUMENTS как источник (кроме запретов "ЗАПРЕЩЕНО")
  - 0 ссылок на .docx как источник (кроме запретов и закомментированного legacy-импорта)
  - 0 ссылок на python-docx или OpenXML (кроме запретов в AGENT_7)
- Исторические файлы (CHANGELOG, CHAT_CONTEXT, AUDIT_REPORT, PROJECT_CONTEXT) не изменены

Изменения:
- Было: Агенты читали ФМ из Word/DOCX файлов (FM_DOCUMENTS/*.docx), использовали python-docx и .NET OpenXML SDK
- Стало: Все агенты читают/пишут ФМ ТОЛЬКО через Confluence REST API (PAGE_ID). Word полностью исключен из источников.
Статус: DONE

---

## STEP-22: ePC-диаграммы в Miro + внедрение в Confluence
Дата: 05.02.2026
Задача: Создать ePC-диаграммы процесса контроля рентабельности в Miro, внедрить ссылки в ФМ на Confluence.

План:
- [x] Получить рабочий токен Miro API
- [x] Очистить доску от предыдущих попыток
- [x] Разбить процесс на 3 логические диаграммы
- [x] Создать ePC #1: Основной поток контроля рентабельности
- [x] Создать ePC #2: Процесс согласования (РБЮ/ДП/ГД + SLA + эскалация)
- [x] Создать ePC #3: Экстренное согласование
- [x] Сохранить бэкап ФМ v8 из Confluence
- [x] Внедрить блок ePC-диаграмм в страницу ФМ (Confluence v9)
- [x] Верифицировать структуру диаграмм
- [x] Верифицировать Confluence страницу

Действие:
- Miro API token: (рабочий, eu01 region)
- Board: https://miro.com/app/board/uXjVGFq_knA=
- Скрипт: scripts/create_epc_miro.py (3 диаграммы + легенда)
- Бэкап: backups/FM-LS-PROFIT_v8_20260205_200346.json (217KB)

Созданные элементы в Miro:
- Frames: 4 (D1, D2, D3, Легенда)
- Shapes: 102 (41 event, 26 function, 11 XOR, 9 org, 15 sys/doc/sla)
- Texts: 4 (заголовки диаграмм)
- Connectors: 93
- TOTAL: 203 элемента

Диаграмма 1 - Основной поток:
- Заказ создан → Проверка НПСС → [XOR: НПСС=0/OK]
- НПСС OK → Расчет рентабельности → Проверка отклонения
- [XOR: <1пп авто / >=1пп ручное]
- Автосогласование → Заказ согласован
- Ручное → [Ссылка на D2] → [XOR: одобрено/отклонено]
- → Резервирование → Передача на склад
- Роли: Менеджер, Финслужба
- Системы: 1С:УТ

Диаграмма 2 - Процесс согласования:
- Отклонение обнаружено → Определить уровень
- [XOR: 1-15пп РБЮ / 15-25пп ДП / >25пп ГД]
- SLA: 4ч (РБЮ), 8ч (ДП), 24ч (ГД)
- Ожидание → [XOR: Решение / Таймаут]
- Таймаут → Автоэскалация → loop back
- ГД: 48ч без ответа → Автоотказ
- [XOR: Одобрено / Отклонено] → Уведомление менеджера
- Роли: РБЮ, ДП, ГД
- Системы: 1С:ДО

Диаграмма 3 - Экстренное согласование:
- Срочный заказ → Запрос устного разрешения
- [XOR: Отказ → D2 / Разрешено]
- Фиксация (скриншот/журнал) → Заказ «Экстренно»
- Постфактум согласование в 1С:ДО (SLA 24ч)
- [XOR: Подтверждено / Отклонено постфактум → Инцидент]
- Лимиты: 3/мес на менеджера, 5/мес на контрагента
- Роли: Менеджер, Согласующий
- Системы: 1С:УТ, 1С:ДО

Внедрение в Confluence:
- Добавлен блок "Схемы процессов (ePC-диаграммы)" после "Описание решения"
- Таблица 3x3: Диаграмма | Описание | Содержание
- Ссылка на доску Miro
- Confluence версия: 8 → 9

Проверка:
| Критерий | Результат | Метод |
|----------|-----------|-------|
| 4 фрейма в Miro | OK | API count |
| Events >= 30 | OK (41) | hexagon count |
| Functions >= 20 | OK (26) | round_rectangle count |
| XOR >= 10 | OK (11) | rhombus count |
| Roles >= 6 | OK (9) | circle count |
| Connectors >= 80 | OK (93) | connector count |
| ePC блок в Confluence | OK | body search |
| Miro URL в Confluence | OK | body search |
| Бэкап сохранен | OK | file exists |

Изменения:
- Было: ФМ v8 без визуализации процессов
- Стало: ФМ v9 с блоком ePC-диаграмм, ссылка на Miro доску с 3 интерактивными диаграммами
Статус: DONE

---

## STEP-23: Исправление ePC раздела в Confluence (iframe -> TO-BE)
Дата: 06.02.2026
Задача: Исправить отображение ePC диаграмм - убрать неподдерживаемый iframe, переместить в раздел "Общая схема процесса (TO-BE)".

### Контекст
- Проблема: Confluence Server не поддерживает макрос `iframe` ("Неизвестный макрос: 'iframe'")
- Замечание: диаграммы должны быть в "Общая схема процесса (TO-BE)", не в отдельном разделе
- GitHub: https://github.com/shakhovskiya-create
- Добавлено правило: push/merge после завершения работ

### План
- [x] Убрать iframe макрос из скрипта embed_epc_confluence.py
- [x] Переименовать раздел "Схемы процессов (ePC-диаграммы)" -> "Общая схема процесса (TO-BE)"
- [x] Вставить раздел перед "Концепция" (после H1 "Описание решения")
- [x] Добавить правило push/merge в todos.md
- [x] Обновить Confluence страницу

### Действие
- Скрипт scripts/embed_epc_confluence.py обновлен:
  - Убран `<ac:structured-macro ac:name="iframe">` (не поддерживается)
  - Заголовок: "Схемы процессов" -> "Общая схема процесса (TO-BE)"
  - Info panel с ссылкой на Miro + таблица с описанием диаграмм + легенда
  - Точка вставки: перед H2 "Концепция"
- Confluence версия: 10 -> 11

### Проверка
| Критерий | Результат | Метод |
|----------|-----------|-------|
| TO-BE heading в body | OK | "Общая схема процесса (TO-BE)" in body |
| Miro URL присутствует | OK | BOARD_ID in body |
| Info panel (не iframe) | OK | 'ac:name="info"' in body |
| Нет iframe | OK | 'iframe' not in body.lower() |
| Легенда ePC | OK | "Легенда ePC" in body |
| 3 диаграммы описаны | OK | "Основной поток", "Процесс согласования", "Экстренное согласование" |

### Изменения
- Было: Confluence v10, раздел "Схемы процессов (ePC-диаграммы)" с неработающим iframe макросом
- Стало: Confluence v11, раздел "Общая схема процесса (TO-BE)" с info panel + ссылкой на Miro
- Добавлено правило push/merge в todos.md

Статус: DONE

---
