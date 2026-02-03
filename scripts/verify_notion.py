#!/usr/bin/env python3
"""Verify Notion publication"""
import json, urllib.request, ssl, sys

ssl._create_default_https_context = ssl._create_unverified_context

TOKEN = "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"
with open("/Users/antonsahovskii/Documents/claude-agents/fm-review-system/docs/notion-config.json") as f:
    CFG = json.load(f)

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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR: {str(e)[:100]}", file=sys.stderr)
        return None

def query_db(db_id):
    pages = []
    r = api("POST", f"databases/{db_id}/query", {"page_size": 100})
    if r:
        pages = r.get("results", [])
    return pages

print("=" * 60)
print("NOTION PUBLICATION VERIFICATION")
print("=" * 60)

# Check FM
print("\n=== FM Database ===")
fm_pages = query_db(CFG["fm_database"])
if fm_pages:
    p = fm_pages[0]
    props = p.get("properties", {})
    code = props.get("Код", {}).get("title", [{}])[0].get("text", {}).get("content", "?") if props.get("Код", {}).get("title") else "?"
    version = props.get("Версия", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "?") if props.get("Версия", {}).get("rich_text") else "?"
    status = props.get("Статус", {}).get("select", {}).get("name", "?") if props.get("Статус", {}).get("select") else "?"
    print(f"  Code: {code}")
    print(f"  Version: {version}")
    print(f"  Status: {status}")
    print(f"  URL: {p.get('url', '?')}")

# Check Requirements
print("\n=== Requirements Database ===")
req_pages = query_db(CFG["requirements_database"])
print(f"  Total: {len(req_pages)} records")

# Count by type
type_counts = {}
linked_count = 0
for p in req_pages:
    props = p.get("properties", {})
    req_type = props.get("Тип", {}).get("select", {}).get("name", "?") if props.get("Тип", {}).get("select") else "?"
    type_counts[req_type] = type_counts.get(req_type, 0) + 1
    if props.get("ФМ", {}).get("relation"):
        linked_count += 1

for t in sorted(type_counts.keys()):
    print(f"    {t}: {type_counts[t]}")
print(f"  Linked to FM: {linked_count}/{len(req_pages)}")

# Check Glossary
print("\n=== Glossary Database ===")
glo_pages = query_db(CFG["glossary_database"])
print(f"  Total: {len(glo_pages)} records")
linked = sum(1 for p in glo_pages if p.get("properties", {}).get("ФМ", {}).get("relation"))
print(f"  Linked to FM: {linked}/{len(glo_pages)}")

# Check Risks
print("\n=== Risks Database ===")
risk_pages = query_db(CFG["risks_database"])
print(f"  Total: {len(risk_pages)} records")
linked = sum(1 for p in risk_pages if p.get("properties", {}).get("ФМ", {}).get("relation"))
print(f"  Linked to FM: {linked}/{len(risk_pages)}")

# Check Versions
print("\n=== Versions Database ===")
ver_pages = query_db(CFG["versions_database"])
print(f"  Total: {len(ver_pages)} records")
for p in ver_pages:
    props = p.get("properties", {})
    ver = props.get("Версия", {}).get("title", [{}])[0].get("text", {}).get("content", "?") if props.get("Версия", {}).get("title") else "?"
    date = props.get("Дата", {}).get("date", {}).get("start", "?") if props.get("Дата", {}).get("date") else "?"
    print(f"    {ver} ({date})")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
