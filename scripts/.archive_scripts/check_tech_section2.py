#!/usr/bin/env python3
"""Check Технические ограничения section content - fixed version."""

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

print("=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ SECTION ===\n")

# Find exact position
tech_pos = body.find("<strong>Технические ограничения</strong>")
if tech_pos == -1:
    tech_pos = body.find("Технические ограничения")

if tech_pos == -1:
    print("Section not found!")
else:
    print(f"Found at position: {tech_pos}")

    # Extract content from that position to next H1 or end
    section_start = tech_pos - 10  # Include h1 tag
    remaining = body[tech_pos:]

    # Find next H1
    next_h1 = re.search(r'<h1[^>]*>', remaining[50:])  # Skip current h1
    if next_h1:
        section_end = tech_pos + 50 + next_h1.start()
        section = body[section_start:section_end]
    else:
        section = body[section_start:]

    # Clean for display
    clean = re.sub(r'<[^>]+>', ' ', section)
    clean = re.sub(r'\s+', ' ', clean).strip()

    print(f"Section length: {len(section)} chars")
    print(f"\nContent (cleaned, first 3000 chars):\n")
    print(clean[:3000])

    # Check for diagrams
    print("\n" + "=" * 50)
    if 'epc_' in section:
        print("WARNING: Diagrams in Технические ограничения!")
    else:
        print("OK: No diagrams in this section")

    # Check structure
    print("\n=== H2 SUBSECTIONS ===")
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', section, re.DOTALL)
    for h2 in h2s:
        clean_h2 = re.sub(r'<[^>]+>', '', h2).strip()[:80]
        print(f"  - {clean_h2}")
