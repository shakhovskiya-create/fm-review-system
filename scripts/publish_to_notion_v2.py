#!/usr/bin/env python3
"""Enhanced FM-LS-PROFIT v1.2.1 publisher - extracts ALL 76 requirements"""
import json, urllib.request, ssl, time, re, docx, sys

ssl._create_default_https_context = ssl._create_unverified_context

# === CONFIG ===
TOKEN = "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"
with open("/Users/antonsahovskii/Documents/claude-agents/fm-review-system/docs/notion-config.json") as f:
    CFG = json.load(f)

FM_DB = CFG["fm_database"]
REQ_DB = CFG["requirements_database"]
GLO_DB = CFG["glossary_database"]
RISK_DB = CFG["risks_database"]
VER_DB = CFG["versions_database"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

DOC_PATH = "/Users/antonsahovskii/Documents/claude-agents/fm-review-system/projects/PROJECT_SHPMNT_PROFIT/FM_DOCUMENTS/FM-LS-PROFIT-v1.2.1.docx"

def api(method, path, data=None):
    url = f"https://api.notion.com/v1/{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"  API ERROR {e.code}: {err.get('message','?')[:200]}", file=sys.stderr)
        return None

def rich_text(text, max_len=2000):
    if not text:
        return []
    text = str(text)[:max_len]
    return [{"text": {"content": text}}]

def create_page_in_db(db_id, properties):
    return api("POST", "pages", {
        "parent": {"database_id": db_id},
        "properties": properties
    })

def query_db(db_id):
    pages = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = api("POST", f"databases/{db_id}/query", payload)
        if not r:
            break
        pages.extend(r.get("results", []))
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
        time.sleep(0.2)
    return pages

def archive_page(page_id):
    return api("PATCH", f"pages/{page_id}", {"archived": True})

# === LOAD DOCUMENT ===
print("=" * 60)
print("ENHANCED NOTION PUBLISHER v2")
print("=" * 60)
print("\n=== LOADING DOCUMENT ===")
doc = docx.Document(DOC_PATH)
title = "КОНТРОЛЬ РЕНТАБЕЛЬНОСТИ ОТГРУЗОК ПО ЛС"
print(f"  Title: {title}")
print(f"  Paragraphs: {len(doc.paragraphs)}")
print(f"  Tables: {len(doc.tables)}")

# === STEP 0: Clear existing data ===
print("\n=== STEP 0: Clear existing data ===")
total_cleared = 0
for name, db_id in [("FM", FM_DB), ("Requirements", REQ_DB), ("Glossary", GLO_DB), ("Risks", RISK_DB), ("Versions", VER_DB)]:
    pages = query_db(db_id)
    for p in pages:
        archive_page(p["id"])
        total_cleared += 1
        time.sleep(0.1)
    if pages:
        print(f"  Cleared {len(pages)} from {name}")
print(f"  Total cleared: {total_cleared}")

# === STEP 1: Create FM record ===
print("\n=== STEP 1: Create FM record ===")
fm_page = create_page_in_db(FM_DB, {
    "Код": {"title": rich_text("FM-LS-PROFIT")},
    "Название": {"rich_text": rich_text(title)},
    "Версия": {"rich_text": rich_text("1.2.1")},
    "Статус": {"select": {"name": "Draft"}},
    "Приоритет": {"select": {"name": "P1"}},
    "Область": {"multi_select": [{"name": "Продажи"}, {"name": "Логистика"}, {"name": "Финансы"}]},
    "Системы": {"multi_select": [{"name": "1С:УТ"}, {"name": "1С:ERP"}]}
})

if fm_page:
    fm_page_id = fm_page["id"]
    fm_page_url = fm_page["url"]
    print(f"  Created: {fm_page_id}")
    print(f"  URL: {fm_page_url}")
else:
    print("  FAILED to create FM page")
    sys.exit(1)

time.sleep(0.3)

# === STEP 2: Add content blocks ===
print("\n=== STEP 2: Add content blocks ===")

def add_blocks(page_id, blocks):
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i+100]
        r = api("PATCH", f"blocks/{page_id}/children", {"children": chunk})
        if r:
            print(f"  Added {len(chunk)} blocks (batch {i//100 + 1})")
        else:
            print(f"  FAILED batch {i//100 + 1}")
        time.sleep(0.5)

def make_heading(level, text):
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": rich_text(text)}}

def make_paragraph(text):
    if not text or not text.strip():
        return None
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text(text)}}

def make_bullet(text):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_text(text)}}

def make_callout(text, emoji="💡"):
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji}
        }
    }

def make_divider():
    return {"object": "block", "type": "divider", "divider": {}}

blocks = []
blocks.append(make_heading(1, title))
blocks.append(make_paragraph("Версия: 1.2.1 | Дата: 29.01.2026 | Статус: Draft"))
blocks.append(make_divider())

for p in doc.paragraphs[2:]:
    text = p.text.strip()
    if not text:
        continue

    style = p.style.name if p.style else "Normal"

    # Special callouts for warnings
    if text.startswith("⚠️") or text.startswith("⛔"):
        emoji = "⚠️" if text.startswith("⚠️") else "🚫"
        blocks.append(make_callout(text, emoji))
    elif style == "Heading 1":
        blocks.append(make_heading(1, text))
    elif style == "Heading 2":
        blocks.append(make_heading(2, text))
    elif style == "Heading 3":
        blocks.append(make_heading(3, text))
    elif style == "List Paragraph" or text.startswith("•") or text.startswith("-"):
        blocks.append(make_bullet(text.lstrip("•- ")))
    else:
        block = make_paragraph(text)
        if block:
            blocks.append(block)

blocks = [b for b in blocks if b]
print(f"  Parsed {len(blocks)} blocks")
add_blocks(fm_page_id, blocks)

# === STEP 3: Extract ALL requirements (76) ===
print("\n=== STEP 3: Extract ALL requirements ===")
req_pattern = re.compile(r'(LS-(?:BR|FR|WF|RPT|NFR|INT|SEC)-\d{3}[a-z]?)')

# Collect all text with requirement codes
all_texts = []
for p in doc.paragraphs:
    all_texts.append(p.text)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            all_texts.append(cell.text)

full_text = "\n".join(all_texts)

# Find all unique codes
all_matches = req_pattern.findall(full_text)
found_codes = sorted(set(all_matches), key=lambda x: (x.split('-')[1], int(re.search(r'\d+', x).group())))
print(f"  Found {len(found_codes)} unique requirement codes")

# For each code, find its context
requirements = {}
for code in found_codes:
    # Find paragraph containing this code
    for text in all_texts:
        if code in text:
            # Get description - text after the code
            idx = text.find(code)
            desc = text[idx + len(code):].strip(" :.-–")
            if len(desc) > 10:
                requirements[code] = {
                    "code": code,
                    "type": code.split("-")[1],
                    "desc": desc[:500]
                }
                break

    if code not in requirements:
        requirements[code] = {
            "code": code,
            "type": code.split("-")[1],
            "desc": f"Требование {code}"
        }

# Type descriptions
type_names = {
    "BR": "Бизнес-правило",
    "FR": "Функциональное требование",
    "WF": "Процесс/Согласование",
    "RPT": "Отчет/Аналитика",
    "NFR": "Нефункциональное требование",
    "INT": "Интеграция",
    "SEC": "Безопасность"
}

# Create requirements in Notion
req_ids = []
for code, req in sorted(requirements.items()):
    type_code = req["type"]
    name = f"{type_names.get(type_code, type_code)}: {req['desc'][:150]}"

    r = create_page_in_db(REQ_DB, {
        "Код": {"title": rich_text(req["code"])},
        "Название": {"rich_text": rich_text(name)},
        "Тип": {"select": {"name": type_code}},
        "Статус": {"select": {"name": "New"}},
        "Приоритет": {"select": {"name": "P1 (MVP)"}}
    })
    if r:
        req_ids.append(r["id"])
    time.sleep(0.12)

print(f"  Created {len(req_ids)} requirements")

# === STEP 4: Create Glossary ===
print("\n=== STEP 4: Create Glossary ===")
glossary_items = [
    ("LS-BR-XXX", "Бизнес-правила (Business Rules)", "Расчеты, лимиты, контроль рентабельности, пороговые значения", "BR"),
    ("LS-FR-XXX", "Функциональные требования (Functional Requirements)", "Формы, статусы, поля, UI-элементы, интерфейс пользователя", "FR"),
    ("LS-WF-XXX", "Процессы и согласования (Workflow)", "Маршруты согласования, SLA, эскалации, уведомления", "WF"),
    ("LS-RPT-XXX", "Отчеты и аналитика (Reports)", "Дашборды, выгрузки, KPI, аналитические формы", "RPT"),
    ("LS-NFR-XXX", "Нефункциональные требования", "Производительность, надежность, масштабируемость", "NFR"),
    ("LS-INT-XXX", "Интеграции", "Внешние системы, API, обмен данными", "INT"),
    ("LS-SEC-XXX", "Безопасность", "Права доступа, аудит, защита данных", "SEC"),
    ("НПСС", "Накопленная Полная Себестоимость", "Полная себестоимость закупки товара у поставщика с учетом всех дополнительных расходов", ""),
    ("ЛС", "Логистическая Спецификация", "Документ-заявка клиента на поставку товаров с указанием количества и условий", ""),
    ("Рентабельность", "Показатель эффективности", "Рентабельность = (Цена - НПСС) / Цена * 100%. Целевое значение >= 0%", ""),
    ("РБЮ", "Руководитель Бизнес-Юнита", "Ответственный за согласование сделок с отклонением рентабельности 1-15%", ""),
    ("Cherry-picking", "Выбор выгодных позиций", "Риск: клиент выбирает только низкомаржинальные позиции, оставляя высокомаржинальные", ""),
    ("Cream-skimming", "Снятие сливок", "Риск: клиент сначала забирает высокомаржинальные позиции, затем отказывается от остатка", ""),
    ("SLA", "Service Level Agreement", "Соглашение об уровне сервиса. Определяет сроки реакции и эскалации при согласовании", ""),
]

glo_ids = []
for term, name, desc, abbr in glossary_items:
    cat = "Технический" if abbr else "Бизнес"
    r = create_page_in_db(GLO_DB, {
        "Термин": {"title": rich_text(term)},
        "Определение": {"rich_text": rich_text(f"{name}. {desc}")},
        "Аббревиатура": {"rich_text": rich_text(abbr)},
        "Категория": {"select": {"name": cat}}
    })
    if r:
        glo_ids.append(r["id"])
    time.sleep(0.15)

print(f"  Created {len(glo_ids)} glossary entries")

# === STEP 5: Create Risks ===
print("\n=== STEP 5: Create Risks ===")
risks = [
    ("Cherry-picking: выбор низкомаржинальных позиций", "Клиент может выбрать только позиции с низкой маржой, оставив высокомаржинальные позиции невыкупленными", "Технический", "Средняя", "Высокое", "Контроль на уровне ЛС: рентабельность проверяется по всей спецификации, а не по отдельным позициям"),
    ("Cream-skimming: снятие сливок", "Клиент сначала забирает высокомаржинальные позиции, затем отказывается от низкомаржинального остатка", "Технический", "Средняя", "Высокое", "Блокировка отгрузки при превышении 80% лимита НПСС и автоэскалация"),
    ("Манипулирование очередностью отгрузок", "Клиент или менеджер может манипулировать порядком отгрузки для искусственного улучшения показателей", "Организационный", "Низкая", "Среднее", "Автоматический расчет позиций для отгрузки по алгоритму рентабельности"),
    ("Конфликт параллельных операций", "Одновременное создание нескольких заявок на отгрузку может привести к некорректному расчету остатков", "Технический", "Низкая", "Высокое", "Блокировка ЛС на время формирования отгрузки, транзакционный контроль"),
    ("Превышение SLA согласования", "Задержка согласования может заблокировать продажи и ухудшить отношения с клиентом", "Организационный", "Средняя", "Высокое", "Трехуровневая автоэскалация: РБЮ 4ч -> ДП 8ч -> ГД 24ч"),
    ("Молчание согласующего", "Согласующий не реагирует на запрос, блокируя процесс", "Организационный", "Средняя", "Среднее", "Автосогласование для положительной рентабельности, эскалация для отрицательной"),
    ("Невыкуп остатков ЛС", "Клиент может не выкупить оставшиеся позиции после частичных отгрузок", "Внешний", "Высокая", "Критическое", "Санкции за невыкуп: снижение лимита, требование предоплаты, эскалация"),
    ("Конкурентный анализ (splitting)", "Клиент сравнивает цены позиционно с конкурентами и забирает только выгодные позиции", "Внешний", "Высокая", "Высокое", "Информирование менеджера о риске при отклонении от типовой структуры заказа"),
    ("Потеря пакетной скидки", "При частичных отгрузках может быть потеряна скидка, рассчитанная на весь объем", "Технический", "Средняя", "Высокое", "Контроль остатка перед применением скидки, пересчет при изменении объема"),
    ("Отсутствие заместителя согласующего", "При отсутствии согласующего процесс может остановиться", "Организационный", "Низкая", "Среднее", "Автоматическая эскалация на следующий уровень при отсутствии заместителя"),
]

risk_ids = []
for name, desc, cat, prob, impact, mitigation in risks:
    r = create_page_in_db(RISK_DB, {
        "Название": {"title": rich_text(name)},
        "Описание": {"rich_text": rich_text(desc)},
        "Категория": {"select": {"name": cat}},
        "Вероятность": {"select": {"name": prob}},
        "Влияние": {"select": {"name": impact}},
        "Статус": {"select": {"name": "Открыт"}},
        "Митигация": {"rich_text": rich_text(mitigation)}
    })
    if r:
        risk_ids.append(r["id"])
    time.sleep(0.15)

print(f"  Created {len(risk_ids)} risks")

# === STEP 6: Create Version History ===
print("\n=== STEP 6: Create Version History ===")
versions = [
    ("v1.0.0", "2025-12-15", "Первая версия ФМ. Базовый функционал контроля рентабельности.", "Major"),
    ("v1.1.0", "2026-01-15", "Добавлены правила частичных отгрузок, SLA согласования, эскалации.", "Minor"),
    ("v1.2.0", "2026-01-25", "Доработаны бизнес-правила, добавлены санкции за невыкуп.", "Minor"),
    ("v1.2.1", "2026-01-29", "Интеграция 31 исправления по результатам аудита: терминология, форматирование, уточнения бизнес-правил.", "Patch"),
]

ver_ids = []
for ver, date, changes, vtype in versions:
    r = create_page_in_db(VER_DB, {
        "Версия": {"title": rich_text(ver)},
        "Дата": {"date": {"start": date}},
        "Изменения": {"rich_text": rich_text(changes)},
        "Тип": {"select": {"name": vtype}}
    })
    if r:
        ver_ids.append(r["id"])
    time.sleep(0.15)

print(f"  Created {len(ver_ids)} version entries")

# === STEP 7: Link relations ===
print("\n=== STEP 7: Link relations ===")

# Link glossary to FM
for gid in glo_ids:
    api("PATCH", f"pages/{gid}", {"properties": {"ФМ": {"relation": [{"id": fm_page_id}]}}})
    time.sleep(0.08)
print(f"  Linked {len(glo_ids)} glossary -> FM")

# Link requirements to FM
for rid in req_ids:
    api("PATCH", f"pages/{rid}", {"properties": {"ФМ": {"relation": [{"id": fm_page_id}]}}})
    time.sleep(0.08)
print(f"  Linked {len(req_ids)} requirements -> FM")

# Link risks to FM
for rkid in risk_ids:
    api("PATCH", f"pages/{rkid}", {"properties": {"ФМ": {"relation": [{"id": fm_page_id}]}}})
    time.sleep(0.08)
print(f"  Linked {len(risk_ids)} risks -> FM")

# Link versions to FM
for vid in ver_ids:
    api("PATCH", f"pages/{vid}", {"properties": {"ФМ": {"relation": [{"id": fm_page_id}]}}})
    time.sleep(0.08)
print(f"  Linked {len(ver_ids)} versions -> FM")

# === SUMMARY ===
print("\n" + "=" * 60)
print("PUBLISH COMPLETE")
print("=" * 60)
print(f"  FM Page:      {fm_page_url}")
print(f"  Requirements: {len(req_ids)}")
print(f"  Glossary:     {len(glo_ids)}")
print(f"  Risks:        {len(risk_ids)}")
print(f"  Versions:     {len(ver_ids)}")
print("=" * 60)
