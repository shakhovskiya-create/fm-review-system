#!/usr/bin/env python3
"""Create 5 Notion databases for FM Review System"""
import json, urllib.request, time, sys, ssl
ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = "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"
PARENT_PAGE = "2fc4009c-5fe7-80e6-9a80-edf4c0c26310"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def api(method, path, data=None):
    url = f"https://api.notion.com/v1/{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"  ERROR {e.code}: {err.get('message','?')}", file=sys.stderr)
        return None

def create_db(title, icon, props):
    r = api("POST", "databases", {
        "parent": {"page_id": PARENT_PAGE},
        "icon": {"type": "emoji", "emoji": icon},
        "title": [{"text": {"content": title}}],
        "properties": props
    })
    if r:
        print(f"  ✅ {title} → {r['id']}")
        return r["id"]
    print(f"  ❌ {title} FAILED")
    return None

print("=== STEP 1: Create 5 databases ===")

fm_id = create_db("📄 Функциональные модели", "📄", {
    "Код": {"title": {}},
    "Название": {"rich_text": {}},
    "Версия": {"rich_text": {}},
    "Статус": {"select": {"options": [
        {"name": "Draft", "color": "gray"},
        {"name": "Review", "color": "yellow"},
        {"name": "Approved", "color": "green"},
        {"name": "Archived", "color": "brown"}
    ]}},
    "Приоритет": {"select": {"options": [
        {"name": "P0", "color": "red"}, {"name": "P1", "color": "orange"},
        {"name": "P2", "color": "yellow"}, {"name": "P3", "color": "gray"}
    ]}},
    "Область": {"multi_select": {"options": [
        {"name": "Продажи", "color": "blue"}, {"name": "Логистика", "color": "green"},
        {"name": "Финансы", "color": "purple"}, {"name": "IT", "color": "gray"},
        {"name": "Закупки", "color": "orange"}
    ]}},
    "Системы": {"multi_select": {"options": [
        {"name": "1С:УТ", "color": "yellow"}, {"name": "1С:ДО", "color": "orange"},
        {"name": "1С:ERP", "color": "red"}, {"name": "WMS", "color": "green"},
        {"name": "CRM", "color": "blue"}, {"name": "BI", "color": "purple"}
    ]}},
    "Miro Board": {"url": {}},
    "Дата создания": {"created_time": {}},
    "Дата обновления": {"last_edited_time": {}}
})
time.sleep(0.4)

req_id = create_db("📋 Требования", "📋", {
    "Код": {"title": {}},
    "Название": {"rich_text": {}},
    "Тип": {"select": {"options": [
        {"name": "BR", "color": "blue"}, {"name": "FR", "color": "green"},
        {"name": "WF", "color": "yellow"}, {"name": "RPT", "color": "purple"},
        {"name": "NFR", "color": "gray"}, {"name": "INT", "color": "orange"},
        {"name": "SEC", "color": "red"}
    ]}},
    "Приоритет": {"select": {"options": [
        {"name": "P1 (MVP)", "color": "red"},
        {"name": "P2 (Phase 2)", "color": "yellow"},
        {"name": "P3 (Backlog)", "color": "gray"}
    ]}},
    "Статус": {"select": {"options": [
        {"name": "New", "color": "gray"}, {"name": "InProgress", "color": "blue"},
        {"name": "Done", "color": "green"}, {"name": "Blocked", "color": "red"},
        {"name": "Cancelled", "color": "brown"}
    ]}},
    "Сложность": {"select": {"options": [
        {"name": "XS", "color": "gray"}, {"name": "S", "color": "green"},
        {"name": "M", "color": "yellow"}, {"name": "L", "color": "orange"},
        {"name": "XL", "color": "red"}
    ]}},
    "Deadline": {"date": {}},
    "Создано": {"created_time": {}},
    "Обновлено": {"last_edited_time": {}}
})
time.sleep(0.4)

glo_id = create_db("📖 Глоссарий", "📖", {
    "Термин": {"title": {}},
    "Определение": {"rich_text": {}},
    "Аббревиатура": {"rich_text": {}},
    "Синонимы": {"rich_text": {}},
    "Категория": {"select": {"options": [
        {"name": "Бизнес", "color": "blue"}, {"name": "Технический", "color": "gray"},
        {"name": "Юридический", "color": "purple"}, {"name": "Финансовый", "color": "green"}
    ]}},
    "Создано": {"created_time": {}}
})
time.sleep(0.4)

risk_id = create_db("⚠️ Риски", "⚠️", {
    "Название": {"title": {}},
    "Описание": {"rich_text": {}},
    "Категория": {"select": {"options": [
        {"name": "Технический", "color": "gray"},
        {"name": "Организационный", "color": "yellow"},
        {"name": "Внешний", "color": "blue"}
    ]}},
    "Вероятность": {"select": {"options": [
        {"name": "Низкая", "color": "green"},
        {"name": "Средняя", "color": "yellow"},
        {"name": "Высокая", "color": "red"}
    ]}},
    "Влияние": {"select": {"options": [
        {"name": "Низкое", "color": "green"}, {"name": "Среднее", "color": "yellow"},
        {"name": "Высокое", "color": "orange"}, {"name": "Критическое", "color": "red"}
    ]}},
    "Статус": {"select": {"options": [
        {"name": "Открыт", "color": "red"}, {"name": "Митигирован", "color": "yellow"},
        {"name": "Закрыт", "color": "green"}, {"name": "Принят", "color": "gray"}
    ]}},
    "Митигация": {"rich_text": {}},
    "Создано": {"created_time": {}},
    "Обновлено": {"last_edited_time": {}}
})
time.sleep(0.4)

ver_id = create_db("📝 История версий", "📝", {
    "Версия": {"title": {}},
    "Дата": {"date": {}},
    "Изменения": {"rich_text": {}},
    "Тип": {"select": {"options": [
        {"name": "Major", "color": "red"},
        {"name": "Minor", "color": "yellow"},
        {"name": "Patch", "color": "gray"}
    ]}}
})
time.sleep(0.5)

# === STEP 2: Add relations ===
print("\n=== STEP 2: Add relations ===")
ids = {"fm": fm_id, "req": req_id, "glo": glo_id, "risk": risk_id, "ver": ver_id}
failed = [k for k,v in ids.items() if not v]
if failed:
    print(f"  ❌ Missing DBs: {failed}. Skipping relations.")
else:
    # FM → Требования
    api("PATCH", f"databases/{fm_id}", {"properties": {
        "Требования": {"relation": {"database_id": req_id, "single_property": {}}}
    }})
    print("  ✅ FM → Требования")
    time.sleep(0.3)

    # FM → Глоссарий
    api("PATCH", f"databases/{fm_id}", {"properties": {
        "Глоссарий": {"relation": {"database_id": glo_id, "single_property": {}}}
    }})
    print("  ✅ FM → Глоссарий")
    time.sleep(0.3)

    # FM → Риски
    api("PATCH", f"databases/{fm_id}", {"properties": {
        "Риски": {"relation": {"database_id": risk_id, "single_property": {}}}
    }})
    print("  ✅ FM → Риски")
    time.sleep(0.3)

    # Версии → FM
    api("PATCH", f"databases/{ver_id}", {"properties": {
        "ФМ": {"relation": {"database_id": fm_id, "single_property": {}}}
    }})
    print("  ✅ Версии → FM")
    time.sleep(0.3)

    # Требования → FM (reverse)
    api("PATCH", f"databases/{req_id}", {"properties": {
        "ФМ": {"relation": {"database_id": fm_id, "single_property": {}}}
    }})
    print("  ✅ Требования → FM")
    time.sleep(0.3)

    # Глоссарий → FM (reverse)
    api("PATCH", f"databases/{glo_id}", {"properties": {
        "ФМ": {"relation": {"database_id": fm_id, "single_property": {}}}
    }})
    print("  ✅ Глоссарий → FM")
    time.sleep(0.3)

    # Риски → FM (reverse)
    api("PATCH", f"databases/{risk_id}", {"properties": {
        "ФМ": {"relation": {"database_id": fm_id, "single_property": {}}}
    }})
    print("  ✅ Риски → FM")

# === OUTPUT ===
print("\n=== RESULT ===")
result = {
    "fm_database": fm_id,
    "requirements_database": req_id,
    "glossary_database": glo_id,
    "risks_database": risk_id,
    "versions_database": ver_id,
    "parent_page": PARENT_PAGE
}
print(json.dumps(result, indent=2))

# Save to file
with open("/Users/antonsahovskii/Documents/claude-agents/fm-review-system/docs/notion-config.json", "w") as f:
    json.dump(result, f, indent=2)
print("\n✅ Config saved to docs/notion-config.json")
