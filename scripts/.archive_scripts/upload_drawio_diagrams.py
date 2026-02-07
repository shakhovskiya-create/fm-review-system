#!/usr/bin/env python3
"""
Upload draw.io diagrams to Confluence and embed them in TO-BE section.
"""

import urllib.request
import urllib.parse
import json
import ssl
import re
import sys
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"
DIAGRAMS_DIR = SCRIPT_DIR / "diagrams"

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

# Diagrams to upload
DIAGRAMS = [
    ("epc_main_flow.drawio", "Диаграмма 1: Основной поток"),
    # Will add more later
]


def upload_attachment(filename, filepath):
    """Upload file as attachment to Confluence page."""
    print(f"  Uploading {filename}...")

    with open(filepath, 'rb') as f:
        content = f.read()

    # Check if exists
    check_url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}/child/attachment?filename={urllib.parse.quote(filename)}"
    req = urllib.request.Request(check_url)
    req.add_header("Authorization", f"Bearer {TOKEN}")

    url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}/child/attachment"
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            if data.get("results"):
                att_id = data["results"][0]["id"]
                url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}/child/attachment/{att_id}/data"
                print(f"    Updating existing: {att_id}")
    except:
        pass

    # Upload
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/xml\r\n\r\n"
    ).encode('utf-8') + content + f"\r\n--{boundary}--\r\n".encode('utf-8')

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("X-Atlassian-Token", "nocheck")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            results = result.get("results", [result])
            if results:
                att_id = results[0].get("id")
                print(f"    SUCCESS: {att_id}")
                return att_id
    except urllib.error.HTTPError as e:
        print(f"    ERROR: {e.code} - {e.read().decode()[:200]}")

    return None


def create_drawio_macro(filename, title):
    """Create draw.io macro XHTML."""
    return f'''
<h2>{title}</h2>
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">{filename}</ac:parameter>
  <ac:parameter ac:name="pageSize">false</ac:parameter>
  <ac:parameter ac:name="attachment">{filename}</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>
'''


def update_tobe_section(diagrams_html):
    """Update TO-BE section with draw.io diagrams."""
    print("\n[3] Updating TO-BE section...")

    # Get current page
    url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")

    with urllib.request.urlopen(req) as resp:
        page = json.loads(resp.read())

    body = page.get("body", {}).get("storage", {}).get("value", "")
    title = page.get("title", "")
    version = page.get("version", {}).get("number", 0)

    # Find H1 TO-BE section
    tobe_match = re.search(
        r'(<h1[^>]*><strong>Общая схема процесса \(TO-BE\)</strong></h1>)(.*?)(<h1[^>]*>)',
        body, re.DOTALL
    )

    if not tobe_match:
        print("  ERROR: TO-BE section not found")
        return False

    h1_heading = tobe_match.group(1)
    old_content = tobe_match.group(2)
    next_h1 = tobe_match.group(3)

    # New content with draw.io diagrams
    new_content = f'''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

{diagrams_html}

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда ePC-нотации</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #C8E6C9; width: 200px;">Зеленый шестиугольник</th>
          <td class="confluenceTd">Начальное событие / положительный результат</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFE0B2;">Оранжевый шестиугольник</th>
          <td class="confluenceTd">Промежуточное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFCDD2;">Красный шестиугольник</th>
          <td class="confluenceTd">Конечное событие / отрицательный результат</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #B2EBF2;">Голубой скругленный</th>
          <td class="confluenceTd">Функция (действие)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFF9C4;">Желтый ромб (XOR)</th>
          <td class="confluenceTd">Исключающий выбор (только один путь)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #ECEFF1;">Серый прямоугольник</th>
          <td class="confluenceTd">Информационная система</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #E1BEE7;">Фиолетовый пунктир</th>
          <td class="confluenceTd">Ссылка на подпроцесс</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>

'''

    new_body = body[:tobe_match.start()] + h1_heading + new_content + next_h1 + body[tobe_match.end():]

    print(f"  Old content: {len(old_content)} chars")
    print(f"  New content: {len(new_content)} chars")

    # Update page
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
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} - {e.read().decode()[:500]}")
        return False


def main():
    print("=" * 60)
    print("Upload draw.io Diagrams to Confluence")
    print("=" * 60)

    # Step 1: Upload diagrams
    print("\n[1] Checking draw.io files...")
    drawio_file = DIAGRAMS_DIR / "epc_main_flow.drawio"
    if not drawio_file.exists():
        print(f"  ERROR: {drawio_file} not found")
        sys.exit(1)
    print(f"  Found: {drawio_file}")

    # Step 2: Upload as attachment
    print("\n[2] Uploading to Confluence...")
    for filename, title in DIAGRAMS:
        filepath = DIAGRAMS_DIR / filename
        if filepath.exists():
            upload_attachment(filename, filepath)

    # Step 3: Create macros and update page
    diagrams_html = ""
    for filename, title in DIAGRAMS:
        diagrams_html += create_drawio_macro(filename, title)

    if update_tobe_section(diagrams_html):
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
        print("\nNote: Draw.io diagrams are editable directly in Confluence!")


if __name__ == "__main__":
    main()
