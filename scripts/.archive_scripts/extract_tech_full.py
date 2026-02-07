#!/usr/bin/env python3
"""Extract full Технические ограничения section."""

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

# Find positions of key sections
sections = [
    "Технические ограничения",
    "FAQ",
    "Типовые вопросы",
]

print("=== SECTION POSITIONS ===\n")
for s in sections:
    pos = body.find(s)
    if pos > 0:
        # Get context
        start = max(0, pos - 50)
        end = min(len(body), pos + 100)
        context = body[start:end].replace('\n', ' ')
        print(f"{s}: position {pos}")
        print(f"  Context: ...{context}...\n")

# Extract from Технические ограничения to FAQ
tech_pos = body.find("<strong>Технические ограничения</strong>")
faq_pos = body.find("FAQ")

if tech_pos > 0 and faq_pos > 0 and faq_pos > tech_pos:
    section = body[tech_pos:faq_pos]
    clean = re.sub(r'<[^>]+>', '\n', section)
    clean = re.sub(r'\n+', '\n', clean).strip()

    print("=" * 60)
    print(f"ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ to FAQ ({len(section)} chars):")
    print("=" * 60)
    print(clean[:5000])
else:
    print(f"Could not extract section: tech_pos={tech_pos}, faq_pos={faq_pos}")
