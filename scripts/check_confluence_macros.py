#!/usr/bin/env python3
"""Check available macros on Confluence Server."""

import urllib.request
import json
import ssl
import sys
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

# Load config
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"

def load_env():
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found")
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
CONFLUENCE_URL = CONFIG.get("CONFLUENCE_URL", "https://confluence.ekf.su")
TOKEN = CONFIG.get("CONFLUENCE_TOKEN", "")

def api_get(endpoint):
    url = f"{CONFLUENCE_URL}/rest/api/{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Error: {e}")
        return None

# Check content macros
print("=== Checking Confluence Macros ===\n")

# Get page content to see what macros are used
page = api_get("content/83951683?expand=body.storage")
if page:
    body = page.get("body", {}).get("storage", {}).get("value", "")

    # Find all macro names
    import re
    macros = re.findall(r'ac:name="([^"]+)"', body)
    unique_macros = sorted(set(macros))

    print("Macros currently used on page:")
    for m in unique_macros:
        print(f"  - {m}")

print("\n=== Checking Draw.io / Diagrams ===")
# Try to access draw.io macro endpoint
drawio_check = api_get("contentbody/convert/storage?expand=webresource,embeddedContent")
print(f"Draw.io check: {drawio_check}")

print("\n=== Checking Macro Browser ===")
# Get all available macros via plugins API
try:
    url = f"{CONFLUENCE_URL}/rest/api/content/83951683/history"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        history = json.loads(resp.read())
        print(f"Page history accessible: {bool(history)}")
except Exception as e:
    print(f"History error: {e}")

# Try plugins API
print("\n=== Installed Plugins (search for diagram-related) ===")
try:
    # This endpoint may require admin rights
    url = f"{CONFLUENCE_URL}/rest/plugins/1.0/"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        plugins = json.loads(resp.read())
        if isinstance(plugins, dict) and 'plugins' in plugins:
            for p in plugins.get('plugins', []):
                name = p.get('name', '').lower()
                key = p.get('key', '').lower()
                if any(x in name or x in key for x in ['draw', 'diagram', 'mermaid', 'plant', 'gliffy', 'lucid', 'scroll']):
                    print(f"  - {p.get('name')} ({p.get('key')})")
except urllib.error.HTTPError as e:
    print(f"Plugins API not accessible (need admin): {e.code}")
except Exception as e:
    print(f"Plugins error: {e}")

print("\n=== Testing Scroll Documents macro ===")
# Check if scroll-document macro exists by looking at page macros
if page:
    body = page.get("body", {}).get("storage", {}).get("value", "")
    if 'scroll' in body.lower():
        print("Scroll-related content found in page")
        scroll_macros = re.findall(r'ac:name="(scroll[^"]*)"', body, re.IGNORECASE)
        print(f"Scroll macros: {scroll_macros}")
    else:
        print("No scroll macros currently on page")

print("\n=== Summary ===")
print("To embed diagrams, options are:")
print("1. drawio macro - if Draw.io is installed")
print("2. plantuml macro - if PlantUML is installed")
print("3. mermaid macro - if Mermaid plugin is installed")
print("4. Upload PNG/SVG as attachment and use ac:image")
print("5. Use HTML table-based process visualization (current)")
