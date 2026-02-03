#!/usr/bin/env python3
"""Parse FM-LS-PROFIT-v1.2.1.docx and publish to Notion databases"""
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
PARENT_PAGE = CFG["parent_page"]

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
    """Create rich_text array, splitting if needed"""
    if not text:
        return []
    text = text[:max_len]
    return [{"text": {"content": text}}]

def create_page_in_db(db_id, properties):
    return api("POST", "pages", {
        "parent": {"database_id": db_id},
        "properties": properties
    })

# === PARSE DOCUMENT ===
print("=== PARSING FM DOCUMENT ===")
doc = docx.Document(DOC_PATH)

# Extract title
title = ""
for p in doc.paragraphs[:5]:
    if p.style and p.style.name == "Title":
        title = p.text.strip()
        break
if not title:
    title = "КОНТРОЛЬ РЕНТАБЕЛЬНОСТИ ОТГРУЗОК ПО ЛС"
print(f"  Title: {title}")

# === STEP 1: Create FM record in FM database ===
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
    print(f"  ✅ FM page: {fm_page_id}")
    print(f"  URL: {fm_page_url}")
else:
    print("  ❌ Failed to create FM page")
    sys.exit(1)

time.sleep(0.3)

# === STEP 2: Add content blocks to FM page ===
print("\n=== STEP 2: Add content to FM page ===")

def add_blocks(page_id, blocks):
    """Add blocks to page, max 100 per request"""
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i+100]
        r = api("PATCH", f"blocks/{page_id}/children", {"children": chunk})
        if r:
            print(f"  Added {len(chunk)} blocks (batch {i//100 + 1})")
        else:
            print(f"  ❌ Failed batch {i//100 + 1}")
        time.sleep(0.5)

def make_heading(level, text):
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": rich_text(text)}}

def make_paragraph(text):
    if not text.strip():
        return None
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text(text)}}

def make_bullet(text):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_text(text)}}

def make_divider():
    return {"object": "block", "type": "divider", "divider": {}}

# Parse document into blocks
blocks = []
blocks.append(make_heading(1, title))
blocks.append(make_paragraph(f"Версия: 1.2.1 | Дата: 29.01.2026 | Статус: Draft"))
blocks.append(make_divider())

for p in doc.paragraphs[2:]:
    text = p.text.strip()
    if not text:
        continue
    
    style = p.style.name if p.style else "Normal"
    
    if style == "Heading 1":
        blocks.append(make_heading(1, text))
    elif style == "Heading 2":
        blocks.append(make_heading(2, text))
    elif style == "Heading 3":
        blocks.append(make_heading(3, text))
    elif style == "List Paragraph":
        blocks.append(make_bullet(text))
    else:
        block = make_paragraph(text)
        if block:
            blocks.append(block)

blocks = [b for b in blocks if b]
print(f"  Parsed {len(blocks)} blocks from document")

# Add blocks in batches
add_blocks(fm_page_id, blocks)

# === STEP 3: Extract and create GLOSSARY entries ===
print("\n=== STEP 3: Extract glossary ===")
glossary_items = []
in_glossary = False

for p in doc.paragraphs:
    if p.style and p.style.name == "Heading 1" and "ГЛОССАРИЙ" in p.text.upper():
        in_glossary = True
        continue
    if in_glossary and p.style and p.style.name == "Heading 1":
        break
    if in_glossary and p.text.strip():
        text = p.text.strip()
        # Try to parse "Term - Definition" or "Term: Definition"
        for sep in [" - ", " – ", ": "]:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2 and len(parts[0]) < 100:
                    glossary_items.append({"term": parts[0].strip(), "definition": parts[1].strip()})
                    break

# Also extract code system as glossary
code_types = {
    "LS-BR": ("Бизнес-правила", "Расчеты, лимиты, контроль рентабельности"),
    "LS-FR": ("Функциональные требования", "Формы, статусы, поля, UI-элементы"),
    "LS-WF": ("Процессы и согласования", "Маршруты согласования, SLA, эскалации"),
    "LS-RPT": ("Отчеты и аналитика", "Дашборды, выгрузки, KPI"),
    "LS-NFR": ("Нефункциональные требования", "Производительность, надежность"),
    "LS-INT": ("Интеграции", "Внешние системы, API, обмен данными"),
    "LS-SEC": ("Безопасность", "Права доступа, аудит, защита данных")
}
for code, (name, desc) in code_types.items():
    glossary_items.append({"term": code, "definition": f"{name}. {desc}", "abbr": code, "cat": "Технический"})

glo_ids = []
for item in glossary_items[:50]:  # Limit
    r = create_page_in_db(GLO_DB, {
        "Термин": {"title": rich_text(item["term"])},
        "Определение": {"rich_text": rich_text(item.get("definition", ""))},
        "Аббревиатура": {"rich_text": rich_text(item.get("abbr", ""))},
        "Категория": {"select": {"name": item.get("cat", "Бизнес")}}
    })
    if r:
        glo_ids.append(r["id"])
    time.sleep(0.2)
print(f"  ✅ Created {len(glo_ids)} glossary entries")

# === STEP 4: Extract REQUIREMENTS ===
print("\n=== STEP 4: Extract requirements ===")
requirements = []
full_text = "\n".join([p.text for p in doc.paragraphs])

# Find all requirement codes like LS-BR-001, LS-FR-010, etc
req_pattern = re.compile(r'(LS-(?:BR|FR|WF|RPT|NFR|INT|SEC)-\d{3}[a-z]?)')
found_codes = set(req_pattern.findall(full_text))
print(f"  Found {len(found_codes)} unique requirement codes")

# Extract requirements with their descriptions
for p in doc.paragraphs:
    text = p.text.strip()
    codes_in_text = req_pattern.findall(text)
    for code in codes_in_text:
        # Determine type from code
        type_map = {"BR": "BR", "FR": "FR", "WF": "WF", "RPT": "RPT", "NFR": "NFR", "INT": "INT", "SEC": "SEC"}
        code_type = code.split("-")[1]
        req_type = type_map.get(code_type, "FR")
        
        # Get text after code as description
        desc = text
        if code in desc:
            idx = desc.index(code)
            desc = desc[idx + len(code):].strip(" :.-–")
        
        if not any(r["code"] == code for r in requirements):
            requirements.append({
                "code": code,
                "type": req_type,
                "description": desc[:500] if desc else code
            })

req_ids = []
for req_item in requirements[:100]:  # Limit
    r = create_page_in_db(REQ_DB, {
        "Код": {"title": rich_text(req_item["code"])},
        "Название": {"rich_text": rich_text(req_item["description"][:200])},
        "Тип": {"select": {"name": req_item["type"]}},
        "Статус": {"select": {"name": "New"}},
        "Приоритет": {"select": {"name": "P1 (MVP)"}}
    })
    if r:
        req_ids.append(r["id"])
    time.sleep(0.15)
print(f"  ✅ Created {len(req_ids)} requirements")

# === STEP 5: Extract RISKS ===
print("\n=== STEP 5: Extract risks ===")
risks = []
in_risks = False
current_risk = None

for p in doc.paragraphs:
    text = p.text.strip()
    lower = text.lower()
    
    if "риск" in lower and p.style and "Heading" in (p.style.name or ""):
        in_risks = True
        if len(text) < 200:
            current_risk = {"name": text, "desc": "", "cat": "Технический"}
            risks.append(current_risk)
        continue
    
    if in_risks and current_risk and text:
        if p.style and "Heading" in (p.style.name or ""):
            if "риск" not in lower:
                in_risks = False
                current_risk = None
            else:
                current_risk = {"name": text, "desc": "", "cat": "Организационный"}
                risks.append(current_risk)
        elif current_risk:
            if len(current_risk["desc"]) < 500:
                current_risk["desc"] += text + " "

# Also parse risks table if exists
risk_keywords = ["манипулир", "cherry", "cream", "невыкуп", "SLA", "эскалац", "конкурент"]
for p in doc.paragraphs:
    text = p.text.strip()
    for kw in risk_keywords:
        if kw in text.lower() and len(text) > 30 and not any(r["name"] == text[:80] for r in risks):
            risks.append({"name": text[:80], "desc": text, "cat": "Технический"})
            break

risk_ids = []
for risk_item in risks[:30]:  # Limit
    r = create_page_in_db(RISK_DB, {
        "Название": {"title": rich_text(risk_item["name"][:200])},
        "Описание": {"rich_text": rich_text(risk_item.get("desc", "")[:2000])},
        "Категория": {"select": {"name": risk_item.get("cat", "Технический")}},
        "Вероятность": {"select": {"name": "Средняя"}},
        "Влияние": {"select": {"name": "Высокое"}},
        "Статус": {"select": {"name": "Открыт"}}
    })
    if r:
        risk_ids.append(r["id"])
    time.sleep(0.15)
print(f"  ✅ Created {len(risk_ids)} risks")

# === STEP 6: Create VERSION HISTORY entry ===
print("\n=== STEP 6: Create version history ===")
ver = create_page_in_db(VER_DB, {
    "Версия": {"title": rich_text("v1.2.1")},
    "Дата": {"date": {"start": "2026-01-29"}},
    "Изменения": {"rich_text": rich_text("Первая публикация в Notion. Полный документ ФМ с требованиями, глоссарием и рисками.")},
    "Тип": {"select": {"name": "Minor"}}
})
if ver:
    print(f"  ✅ Version entry created")

# === STEP 7: Link relations ===
print("\n=== STEP 7: Link FM to related records ===")
# Link glossary to FM
for gid in glo_ids[:50]:
    api("PATCH", f"pages/{gid}", {"properties": {
        "ФМ": {"relation": [{"id": fm_page_id}]}
    }})
    time.sleep(0.1)
print(f"  ✅ Linked {len(glo_ids)} glossary → FM")

# Link requirements to FM
for rid in req_ids[:100]:
    api("PATCH", f"pages/{rid}", {"properties": {
        "ФМ": {"relation": [{"id": fm_page_id}]}
    }})
    time.sleep(0.1)
print(f"  ✅ Linked {len(req_ids)} requirements → FM")

# Link risks to FM
for rkid in risk_ids[:30]:
    api("PATCH", f"pages/{rkid}", {"properties": {
        "ФМ": {"relation": [{"id": fm_page_id}]}
    }})
    time.sleep(0.1)
print(f"  ✅ Linked {len(risk_ids)} risks → FM")

# Link version to FM
if ver:
    api("PATCH", f"pages/{ver['id']}", {"properties": {
        "ФМ": {"relation": [{"id": fm_page_id}]}
    }})
    print(f"  ✅ Linked version → FM")

print(f"\n{'='*50}")
print(f"✅ PUBLISH COMPLETE")
print(f"  FM Page: {fm_page_url}")
print(f"  Glossary: {len(glo_ids)} entries")
print(f"  Requirements: {len(req_ids)} entries")
print(f"  Risks: {len(risk_ids)} entries")
print(f"  Version: v1.2.1")
print(f"{'='*50}")
