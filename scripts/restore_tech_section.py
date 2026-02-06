#!/usr/bin/env python3
"""
Restore Технические ограничения section from backup.
"""

import urllib.request
import json
import ssl
import re
import sys
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"

def load_env():
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

print("=== Restoring Технические ограничения Section ===\n")

# Step 1: Load backup
print("[1] Loading backup...")
with open("backups/FM-LS-PROFIT_v8_20260205_200346.json") as f:
    backup = json.load(f)

backup_body = backup.get("body_storage", "")
print(f"  Backup version: {backup.get('version')}")

# Step 2: Extract Технические ограничения content from backup
print("\n[2] Extracting section from backup...")

# Find the section - from H1 Технические ограничения to H1 FAQ
backup_tech_match = re.search(
    r'(<h1[^>]*><strong>Технические ограничения</strong></h1>)(.*?)(<h1[^>]*><strong>FAQ)',
    backup_body, re.DOTALL
)

if not backup_tech_match:
    print("  ERROR: Could not find section in backup")
    sys.exit(1)

backup_tech_heading = backup_tech_match.group(1)
backup_tech_content = backup_tech_match.group(2)
print(f"  Found section: {len(backup_tech_content)} chars")

# Step 3: Get current page
print("\n[3] Getting current page...")
url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")

with urllib.request.urlopen(req) as resp:
    page = json.loads(resp.read())

body = page.get("body", {}).get("storage", {}).get("value", "")
title = page.get("title", "")
version = page.get("version", {}).get("number", 0)
print(f"  Current version: {version}")

# Step 4: Find and replace Технические ограничения section
print("\n[4] Replacing section...")

# Find current section - it's empty, just heading + empty H2
current_tech_match = re.search(
    r'(<h1[^>]*><strong>Технические ограничения</strong></h1>)(.*?)(<h1[^>]*><strong>FAQ)',
    body, re.DOTALL
)

if not current_tech_match:
    print("  ERROR: Could not find section in current page")
    sys.exit(1)

current_heading = current_tech_match.group(1)
current_content = current_tech_match.group(2)
print(f"  Current content: {len(current_content)} chars")
print(f"  Will restore: {len(backup_tech_content)} chars")

# Replace - need to keep the full FAQ heading
faq_heading_match = re.search(r'<h1[^>]*><strong>FAQ', body[current_tech_match.start():])
if faq_heading_match:
    faq_start = current_tech_match.start() + faq_heading_match.start()
    new_body = body[:current_tech_match.start()] + backup_tech_heading + backup_tech_content + body[faq_start:]
else:
    print("  ERROR: Could not find FAQ heading")
    sys.exit(1)

# Verify change
if len(new_body) > len(body):
    print(f"  Content will grow by {len(new_body) - len(body)} chars")
else:
    print(f"  WARNING: New body is smaller!")

# Step 5: Update page
print("\n[5] Updating Confluence page...")

update_url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}"
update_data = {
    "id": PAGE_ID,
    "type": "page",
    "title": title,
    "version": {"number": version + 1},
    "body": {
        "storage": {
            "value": new_body,
            "representation": "storage"
        }
    }
}

req = urllib.request.Request(
    update_url,
    data=json.dumps(update_data).encode('utf-8'),
    method="PUT"
)
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        new_version = result.get("version", {}).get("number")
        print(f"  SUCCESS: Updated to version {new_version}")
except urllib.error.HTTPError as e:
    error_body = e.read().decode()
    print(f"  ERROR: {e.code}")
    print(f"  {error_body[:500]}")
    sys.exit(1)

print("\n" + "=" * 50)
print("Технические ограничения section restored from backup!")
