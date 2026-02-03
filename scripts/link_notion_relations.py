#!/usr/bin/env python3
"""Link all records to FM page in Notion"""
import json, urllib.request, ssl, time, sys

ssl._create_default_https_context = ssl._create_unverified_context

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

def api(method, path, data=None, timeout=30):
    url = f"https://api.notion.com/v1/{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR: {str(e)[:100]}", file=sys.stderr)
        return None

def query_db(db_id):
    pages = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = api("POST", f"databases/{db_id}/query", payload, timeout=60)
        if not r:
            break
        pages.extend(r.get("results", []))
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
        time.sleep(0.3)
    return pages

print("=" * 60)
print("LINKING NOTION RELATIONS")
print("=" * 60)

# Find FM page
print("\n=== Finding FM page ===")
fm_pages = query_db(FM_DB)
if not fm_pages:
    print("  ERROR: No FM pages found!")
    sys.exit(1)

fm_page_id = fm_pages[0]["id"]
fm_page_url = fm_pages[0]["url"]
print(f"  FM Page: {fm_page_id}")
print(f"  URL: {fm_page_url}")

# Link all records
databases = [
    ("Requirements", REQ_DB),
    ("Glossary", GLO_DB),
    ("Risks", RISK_DB),
    ("Versions", VER_DB)
]

for name, db_id in databases:
    print(f"\n=== Linking {name} ===")
    pages = query_db(db_id)
    linked = 0
    for p in pages:
        # Check if already linked
        fm_rel = p.get("properties", {}).get("ФМ", {}).get("relation", [])
        if fm_rel and any(r.get("id") == fm_page_id for r in fm_rel):
            continue  # Already linked

        r = api("PATCH", f"pages/{p['id']}", {
            "properties": {"ФМ": {"relation": [{"id": fm_page_id}]}}
        }, timeout=30)
        if r:
            linked += 1
        time.sleep(0.2)  # Rate limiting

    print(f"  Linked {linked} / {len(pages)}")

print("\n" + "=" * 60)
print("LINKING COMPLETE")
print(f"FM Page: {fm_page_url}")
print("=" * 60)
