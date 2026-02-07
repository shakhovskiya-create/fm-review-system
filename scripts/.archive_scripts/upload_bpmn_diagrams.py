#!/usr/bin/env python3
"""
Upload BPMN diagrams to Confluence as a comparison section.
Adds H2 "Альтернатива: BPMN-нотация" after the ePC diagrams.
"""

import urllib.request
import urllib.parse
import json
import ssl
import re
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

BPMN_DIAGRAMS = [
    "bpmn_main_flow.drawio",
    "bpmn_approval.drawio",
    "bpmn_emergency.drawio",
]


def upload_attachment(filename, filepath):
    """Upload file as attachment."""
    print(f"  Uploading {filename}...")

    with open(filepath, 'rb') as f:
        content = f.read()

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
                print(f"    Updating: {att_id}")
    except:
        pass

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
                print(f"    OK: {results[0].get('id')}")
                return True
    except urllib.error.HTTPError as e:
        print(f"    ERROR: {e.code}")

    return False


def get_bpmn_section():
    """Generate BPMN section HTML."""
    return '''
<h2>Альтернатива: BPMN-нотация (для сравнения)</h2>

<ac:structured-macro ac:name="info">
  <ac:rich-text-body>
    <p>Ниже представлены те же процессы в нотации BPMN со swimlanes (дорожками по ролям). Сравните с ePC выше и выберите, какой формат понятнее.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h3>BPMN 1: Основной поток</h3>
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">bpmn_main_flow.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<h3>BPMN 2: Процесс согласования</h3>
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">bpmn_approval.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<h3>BPMN 3: Экстренное согласование</h3>
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">bpmn_emergency.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">BPMN vs ePC: ключевые отличия</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #f4f5f7;">Аспект</th>
          <th class="confluenceTh" style="background-color: #f4f5f7;">ePC</th>
          <th class="confluenceTh" style="background-color: #f4f5f7;">BPMN</th>
        </tr>
        <tr>
          <td class="confluenceTd"><strong>События</strong></td>
          <td class="confluenceTd">Шестиугольники (много)</td>
          <td class="confluenceTd">Круги (start/end/intermediate)</td>
        </tr>
        <tr>
          <td class="confluenceTd"><strong>Роли</strong></td>
          <td class="confluenceTd">Овалы рядом с функциями</td>
          <td class="confluenceTd">Swimlanes (горизонтальные дорожки)</td>
        </tr>
        <tr>
          <td class="confluenceTd"><strong>Читаемость</strong></td>
          <td class="confluenceTd">Компактнее, вертикальный поток</td>
          <td class="confluenceTd">Шире, видно кто что делает</td>
        </tr>
        <tr>
          <td class="confluenceTd"><strong>Применение</strong></td>
          <td class="confluenceTd">SAP, ERP-системы</td>
          <td class="confluenceTd">Широко распространен</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>

'''


def add_bpmn_section():
    """Add BPMN section after ePC diagrams (before legend expand)."""
    print("\n[2] Adding BPMN section to page...")

    url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")

    with urllib.request.urlopen(req) as resp:
        page = json.loads(resp.read())

    body = page.get("body", {}).get("storage", {}).get("value", "")
    title = page.get("title", "")
    version = page.get("version", {}).get("number", 0)

    # Check if BPMN section already exists
    if "Альтернатива: BPMN-нотация" in body:
        print("  BPMN section already exists, removing old...")
        # Remove existing BPMN section
        body = re.sub(
            r'<h2>Альтернатива: BPMN-нотация.*?(?=<h1|$)',
            '',
            body,
            flags=re.DOTALL
        )

    # Find the position after the ePC legend (expand macro with "Легенда ePC")
    # or after the last diagram table before H1 Технические ограничения
    tobe_match = re.search(
        r'(<h1[^>]*><strong>Общая схема процесса \(TO-BE\)</strong></h1>)(.*?)(<h1[^>]*><strong>Технические)',
        body, re.DOTALL
    )

    if not tobe_match:
        print("  ERROR: TO-BE section not found")
        return False

    tobe_start = tobe_match.start()
    tobe_content = tobe_match.group(2)
    next_h1 = tobe_match.group(3)
    next_h1_pos = tobe_match.start(3)

    # Insert BPMN section right before "Технические ограничения"
    bpmn_content = get_bpmn_section()

    new_body = body[:next_h1_pos] + bpmn_content + "\n\n" + body[next_h1_pos:]

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
            print(f"  SUCCESS: Version {new_version}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} - {e.read().decode()[:500]}")
        return False


def main():
    print("=" * 60)
    print("Upload BPMN Diagrams for Comparison")
    print("=" * 60)

    # Step 1: Upload BPMN diagrams
    print("\n[1] Uploading BPMN diagrams...")
    for filename in BPMN_DIAGRAMS:
        filepath = DIAGRAMS_DIR / filename
        if filepath.exists():
            upload_attachment(filename, filepath)
        else:
            print(f"  WARNING: {filename} not found")

    # Step 2: Add BPMN section
    if add_bpmn_section():
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
        print("\nBPMN diagrams added for comparison with ePC!")


if __name__ == "__main__":
    main()
