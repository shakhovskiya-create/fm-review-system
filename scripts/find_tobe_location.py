#!/usr/bin/env python3
"""Find the correct TO-BE section location in Confluence page."""

import urllib.request
import json
import ssl
import re
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

# Get page
url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")

with urllib.request.urlopen(req) as resp:
    page = json.loads(resp.read())

body = page.get("body", {}).get("storage", {}).get("value", "")

print("=== PAGE STRUCTURE ===\n")

# Find all headings
headings = re.findall(r'<h([123])[^>]*>(.*?)</h\1>', body, re.DOTALL)

for i, (level, text) in enumerate(headings):
    # Clean text
    clean_text = re.sub(r'<[^>]+>', '', text).strip()[:60]
    pos = body.find(text[:30])
    print(f"H{level} @{pos:6d}: {clean_text}")

print("\n=== SEARCHING FOR TO-BE SECTIONS ===\n")

# Find TO-BE occurrences
tobe_matches = list(re.finditer(r'(TO-BE|Общая схема процесса)', body, re.IGNORECASE))
for m in tobe_matches:
    start = max(0, m.start() - 50)
    end = min(len(body), m.end() + 50)
    context = body[start:end].replace('\n', ' ')
    print(f"@{m.start():6d}: ...{context}...")

print("\n=== SEARCHING FOR DIAGRAMS ===\n")

# Find diagram locations
diagram_matches = list(re.finditer(r'epc_[123]_\w+\.png', body))
for m in diagram_matches:
    start = max(0, m.start() - 100)
    end = min(len(body), m.end() + 50)
    context = body[start:end].replace('\n', ' ')
    print(f"@{m.start():6d}: {m.group()} in ...{context[:80]}...")

print("\n=== SEARCHING FOR ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===\n")

tech_match = re.search(r'(Технические ограничения|ехнические огранич)', body, re.IGNORECASE)
if tech_match:
    start = max(0, tech_match.start() - 50)
    end = min(len(body), tech_match.end() + 200)
    context = body[start:end].replace('\n', ' ')
    print(f"@{tech_match.start()}: {context[:200]}...")
else:
    print("Not found")
