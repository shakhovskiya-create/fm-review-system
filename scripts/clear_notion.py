#!/usr/bin/env python3
"""Clear all pages from Notion databases before fresh publish"""
import json, urllib.request, ssl, time, sys

ssl._create_default_https_context = ssl._create_unverified_context

# === CONFIG ===
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
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"  API ERROR {e.code}: {err.get('message','?')[:200]}", file=sys.stderr)
        return None

def query_db(db_id):
    """Get all pages from database"""
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
    """Archive (soft-delete) a page"""
    return api("PATCH", f"pages/{page_id}", {"archived": True})

# === MAIN ===
print("=" * 60)
print("CLEARING ALL NOTION DATABASES")
print("=" * 60)

databases = {
    "FM": CFG["fm_database"],
    "Requirements": CFG["requirements_database"],
    "Glossary": CFG["glossary_database"],
    "Risks": CFG["risks_database"],
    "Versions": CFG["versions_database"]
}

total_deleted = 0

for name, db_id in databases.items():
    print(f"\n=== {name} ===")
    pages = query_db(db_id)
    print(f"  Found {len(pages)} pages")

    for p in pages:
        pid = p["id"]
        title = ""
        props = p.get("properties", {})
        for key in ["Код", "Термин", "Название", "Версия"]:
            if key in props:
                arr = props[key].get("title", []) or props[key].get("rich_text", [])
                if arr:
                    title = arr[0].get("text", {}).get("content", "")[:50]
                    break

        r = archive_page(pid)
        if r:
            print(f"  ✅ Archived: {title or pid[:8]}")
            total_deleted += 1
        else:
            print(f"  ❌ Failed: {pid[:8]}")
        time.sleep(0.15)

print(f"\n{'=' * 60}")
print(f"✅ CLEARED {total_deleted} pages total")
print("=" * 60)
