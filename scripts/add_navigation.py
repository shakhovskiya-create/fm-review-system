#!/usr/bin/env python3
"""
Добавление навигации в начало страницы Confluence.

Использует expandable TOC (таблицу содержимого) в начале страницы,
которая сворачивается по умолчанию и не мешает чтению.

Требует .env.local с:
  CONFLUENCE_URL=https://confluence.example.com
  CONFLUENCE_TOKEN=your_token
  CONFLUENCE_PAGE_ID=12345678
"""

import urllib.request
import urllib.parse
import json
import ssl
import sys
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"


def load_env():
    """Load environment from .env.local"""
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


def get_page(config):
    """Get current page content"""
    url = f"{config['CONFLUENCE_URL']}/rest/api/content/{config['CONFLUENCE_PAGE_ID']}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {config['CONFLUENCE_TOKEN']}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def update_page(config, title, body, version):
    """Update page with new content"""
    url = f"{config['CONFLUENCE_URL']}/rest/api/content/{config['CONFLUENCE_PAGE_ID']}"

    data = {
        "id": config['CONFLUENCE_PAGE_ID'],
        "type": "page",
        "title": title,
        "version": {"number": version + 1},
        "body": {
            "storage": {
                "value": body,
                "representation": "storage"
            }
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        method="PUT"
    )
    req.add_header("Authorization", f"Bearer {config['CONFLUENCE_TOKEN']}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Atlassian-Token", "nocheck")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("version", {}).get("number")
    except urllib.error.HTTPError as e:
        print(f"ERROR: {e.code} - {e.read().decode()[:500]}")
        return None


def generate_navigation():
    """Generate navigation block with expandable TOC"""
    return '''
<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">📑 Навигация по документу</ac:parameter>
  <ac:rich-text-body>
    <p><strong>Содержание:</strong></p>
    <ac:structured-macro ac:name="toc">
      <ac:parameter ac:name="maxLevel">3</ac:parameter>
      <ac:parameter ac:name="printable">false</ac:parameter>
      <ac:parameter ac:name="class">rm-contents</ac:parameter>
    </ac:structured-macro>
    <hr/>
    <p><em>Версионирование: используйте Scroll Documents → Сохранить версию</em></p>
  </ac:rich-text-body>
</ac:structured-macro>
'''


def main():
    config = load_env()

    print("=" * 60)
    print("Adding Navigation to Confluence Page")
    print("=" * 60)
    print(f"Confluence: {config['CONFLUENCE_URL']}")
    print(f"Page ID: {config['CONFLUENCE_PAGE_ID']}")

    # Get current page
    print("\n[1] Getting current page...")
    page = get_page(config)
    title = page.get("title", "")
    body = page.get("body", {}).get("storage", {}).get("value", "")
    version = page.get("version", {}).get("number", 0)

    print(f"  Title: {title}")
    print(f"  Version: {version}")
    print(f"  Body length: {len(body)} chars")

    # Check if navigation already exists
    if 'Навигация по документу' in body:
        print("\n[!] Navigation already exists, skipping...")
        return

    # Generate navigation
    print("\n[2] Adding navigation block...")
    navigation = generate_navigation()

    # Insert at the very beginning
    new_body = navigation + body

    # Update page
    print("\n[3] Updating page...")
    new_version = update_page(config, title, new_body, version)

    if new_version:
        print(f"\n  SUCCESS: Page updated to version {new_version}")
        print(f"\nView: {config['CONFLUENCE_URL']}/pages/viewpage.action?pageId={config['CONFLUENCE_PAGE_ID']}")
    else:
        print("\n  FAILED: Could not update page")


if __name__ == "__main__":
    main()
