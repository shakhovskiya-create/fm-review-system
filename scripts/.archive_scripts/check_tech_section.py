#!/usr/bin/env python3
"""Check Технические ограничения section content."""

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

# Find Технические ограничения section
tech_match = re.search(
    r'(<h1[^>]*>.*?Технические ограничения.*?</h1>)(.*?)(<h1[^>]*>|$)',
    body, re.DOTALL | re.IGNORECASE
)

if tech_match:
    heading = tech_match.group(1)
    content = tech_match.group(2)

    # Clean HTML for display
    clean = re.sub(r'<[^>]+>', ' ', content)
    clean = re.sub(r'\s+', ' ', clean).strip()

    print(f"Heading: {re.sub(r'<[^>]+>', '', heading)}")
    print(f"Content length: {len(content)} chars")
    print(f"\nFirst 2000 chars (cleaned):\n{clean[:2000]}")

    # Check for subsections
    h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.DOTALL)
    print(f"\n\nH2 subsections found: {len(h2_matches)}")
    for h2 in h2_matches:
        clean_h2 = re.sub(r'<[^>]+>', '', h2).strip()
        print(f"  - {clean_h2}")
else:
    print("Section not found!")

print("\n" + "=" * 50)
print("\n=== CHECKING FOR DIAGRAMS IN TECH SECTION ===")
if tech_match:
    content = tech_match.group(2)
    if 'epc_' in content or 'ac:image' in content:
        print("WARNING: Diagrams still in Технические ограничения!")
        matches = re.findall(r'epc_\d_\w+\.png', content)
        print(f"  Found: {matches}")
    else:
        print("OK: No diagrams in this section")
