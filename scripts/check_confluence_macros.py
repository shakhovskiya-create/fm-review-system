#!/usr/bin/env python3
"""Check available macros on Confluence Server."""

import json
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

# Load config
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"


def load_env(env_file=None):
    """Load key=value config from an env file."""
    path = env_file or ENV_FILE
    if not Path(path).exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    config = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def _make_ssl_context():
    """Per-request SSL context for corporate self-signed certs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_get(endpoint, confluence_url, token):
    """Confluence REST API GET request."""
    url = f"{confluence_url}/rest/api/{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, context=_make_ssl_context()) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Error: {e}")
        return None


def find_macros(html_body):
    """Extract unique macro names from Confluence XHTML body."""
    macros = re.findall(r'ac:name="([^"]+)"', html_body)
    return sorted(set(macros))


def main():
    # SSL is handled per-request via _make_ssl_context()

    config = load_env()
    confluence_url = config.get("CONFLUENCE_URL", "https://confluence.ekf.su")
    token = config.get("CONFLUENCE_TOKEN", "")

    # Check content macros
    print("=== Checking Confluence Macros ===\n")

    page_id = config.get("CONFLUENCE_PAGE_ID") or os.environ.get("CONFLUENCE_PAGE_ID")
    if not page_id:
        print("ERROR: CONFLUENCE_PAGE_ID not set in env or .env.local")
        sys.exit(1)
    page = api_get(f"content/{page_id}?expand=body.storage", confluence_url, token)
    if page:
        body = page.get("body", {}).get("storage", {}).get("value", "")
        unique_macros = find_macros(body)

        print("Macros currently used on page:")
        for m in unique_macros:
            print(f"  - {m}")

    print("\n=== Checking Draw.io / Diagrams ===")
    drawio_check = api_get(
        "contentbody/convert/storage?expand=webresource,embeddedContent",
        confluence_url, token,
    )
    print(f"Draw.io check: {drawio_check}")

    print("\n=== Checking Macro Browser ===")
    try:
        url = f"{confluence_url}/rest/api/content/{page_id}/history"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, context=_make_ssl_context()) as resp:
            history = json.loads(resp.read())
            print(f"Page history accessible: {bool(history)}")
    except urllib.error.URLError as e:
        print(f"History error: {e}")

    # Try plugins API
    print("\n=== Installed Plugins (search for diagram-related) ===")
    try:
        url = f"{confluence_url}/rest/plugins/1.0/"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, context=_make_ssl_context()) as resp:
            plugins = json.loads(resp.read())
            if isinstance(plugins, dict) and 'plugins' in plugins:
                for p in plugins.get('plugins', []):
                    name = p.get('name', '').lower()
                    key = p.get('key', '').lower()
                    if any(x in name or x in key for x in ['draw', 'diagram', 'mermaid', 'plant', 'gliffy', 'lucid', 'scroll']):
                        print(f"  - {p.get('name')} ({p.get('key')})")
    except urllib.error.HTTPError as e:
        print(f"Plugins API not accessible (need admin): {e.code}")
    except urllib.error.URLError as e:
        print(f"Plugins error: {e}")

    print("\n=== Testing Scroll Documents macro ===")
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


if __name__ == "__main__":
    main()
