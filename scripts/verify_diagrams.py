#!/usr/bin/env python3
"""Verify ePC diagrams are embedded in Confluence page."""

import urllib.request
import json
import ssl
import sys
import re
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
PAGE_ID = CONFIG.get("CONFLUENCE_PAGE_ID")
TOKEN = CONFIG.get("CONFLUENCE_TOKEN")

print("=== Verifying ePC Diagrams in Confluence ===\n")

# Get page
url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Accept", "application/json")

with urllib.request.urlopen(req) as resp:
    page = json.loads(resp.read())

body = page.get("body", {}).get("storage", {}).get("value", "")
version = page.get("version", {}).get("number", 0)

print(f"Page version: {version}")
print()

# Check for diagrams
checks = [
    ("TO-BE section", r'Общая схема процесса.*?TO-BE'),
    ("Diagram 1 (main_flow)", r'epc_1_main_flow\.png'),
    ("Diagram 2 (approval)", r'epc_2_approval\.png'),
    ("Diagram 3 (emergency)", r'epc_3_emergency\.png'),
    ("ac:image macro", r'<ac:image'),
    ("ri:attachment", r'<ri:attachment'),
    ("Legend section", r'Легенда ePC'),
    ("H3 Основной поток", r'<h3>Основной поток'),
    ("H3 Процесс согласования", r'<h3>Процесс согласования'),
    ("H3 Экстренное согласование", r'<h3>Экстренное согласование'),
]

print("Checks:")
all_ok = True
for name, pattern in checks:
    found = bool(re.search(pattern, body, re.IGNORECASE))
    status = "OK" if found else "FAIL"
    print(f"  [{status}] {name}")
    if not found:
        all_ok = False

# Check attachments
print("\n=== Attachments ===")
att_url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}/child/attachment"
req = urllib.request.Request(att_url)
req.add_header("Authorization", f"Bearer {TOKEN}")

with urllib.request.urlopen(req) as resp:
    att_data = json.loads(resp.read())

attachments = att_data.get("results", [])
png_count = 0
for att in attachments:
    title = att.get("title", "")
    if "epc_" in title and title.endswith(".png"):
        size = att.get("extensions", {}).get("fileSize", 0)
        print(f"  - {title} ({size} bytes)")
        png_count += 1

print(f"\nTotal ePC PNGs: {png_count}")

print("\n" + "=" * 50)
if all_ok and png_count == 3:
    print("SUCCESS: All diagrams embedded and visible!")
    print(f"\nPage: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
else:
    print("WARNING: Some checks failed")
    sys.exit(1)
