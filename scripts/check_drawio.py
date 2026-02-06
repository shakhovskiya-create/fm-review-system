#!/usr/bin/env python3
"""Check if draw.io plugin is available on Confluence."""

import urllib.request
import json
import ssl
import sys
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"

def load_env():
    if not ENV_FILE.exists():
        sys.exit(1)
    config = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

CONFIG = load_env()
CONFLUENCE_URL = CONFIG.get("CONFLUENCE_URL")
TOKEN = CONFIG.get("CONFLUENCE_TOKEN")
PAGE_ID = CONFIG.get("CONFLUENCE_PAGE_ID")

def api_get(endpoint):
    url = f"{CONFLUENCE_URL}/rest/api/{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "reason": e.reason}
    except Exception as e:
        return {"error": str(e)}

print("=== Checking Draw.io/Diagrams.net on Confluence ===\n")

# Method 1: Check content type restrictions (if drawio is allowed)
print("[1] Checking content types...")
result = api_get(f"content/{PAGE_ID}/child/attachment")
if "error" not in result:
    attachments = result.get("results", [])
    print(f"  Attachments on page: {len(attachments)}")
    for att in attachments[:5]:
        print(f"    - {att.get('title')} ({att.get('mediaType', 'unknown')})")

# Method 2: Try to get draw.io macro info
print("\n[2] Searching for draw.io in page content...")
page = api_get(f"content/{PAGE_ID}?expand=body.storage")
if "error" not in page:
    body = page.get("body", {}).get("storage", {}).get("value", "")
    drawio_indicators = ['drawio', 'diagram', 'gliffy', 'lucid']
    for ind in drawio_indicators:
        if ind in body.lower():
            print(f"  Found: {ind}")
    if not any(ind in body.lower() for ind in drawio_indicators):
        print("  No diagram macros found in current content")

# Method 3: Check if we can use drawio macro
print("\n[3] Testing draw.io macro syntax...")
test_drawio_xhtml = '''
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="baseUrl">https://app.diagrams.net</ac:parameter>
  <ac:parameter ac:name="diagramName">test</ac:parameter>
  <ac:plain-text-body><![CDATA[]]></ac:plain-text-body>
</ac:structured-macro>
'''
print("  Draw.io macro syntax prepared")
print("  (Would need to test by actually updating page)")

# Method 4: Check for alternative - iframe with draw.io viewer
print("\n[4] Alternative: SVG inline or PNG attachment")
print("  - Can upload PNG as attachment")
print("  - Can embed via ac:image macro")
print("  - This is the most reliable method")

# Method 5: Check Scroll Documents
print("\n[5] Checking Scroll Documents...")
scroll_check = api_get("content/83951683?expand=extensions.scroll-documents")
if "error" not in scroll_check:
    ext = scroll_check.get("extensions", {})
    print(f"  Extensions: {list(ext.keys()) if ext else 'none'}")
else:
    print(f"  Error: {scroll_check}")

print("\n=== RECOMMENDATION ===")
print("Most reliable approach for your Confluence Server:")
print("1. Generate ePC diagrams as PNG/SVG locally")
print("2. Upload as attachments to Confluence page")
print("3. Embed using <ac:image ri:filename='diagram.png'/> macro")
print("\nThis works on ALL Confluence installations without plugins.")
