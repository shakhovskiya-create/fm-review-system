#!/usr/bin/env python3
"""
Публикация BPMN-диаграмм (drawio) в Confluence.

Использование:
  python3 publish-bpmn.py [--all] [--update-page] [file1.drawio file2.drawio ...]

Примеры:
  python3 publish-bpmn.py output/process-1-rentability.drawio
  python3 publish-bpmn.py --all  # все файлы из output/
  python3 publish-bpmn.py --all --update-page  # загрузить + обновить страницу

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
import re
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"
OUTPUT_DIR = SCRIPT_DIR / "output"
BPMN_PROCESSES_DIR = SCRIPT_DIR / "bpmn-processes"


def load_env():
    """Load environment from .env.local"""
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found")
        print("Create .env.local with CONFLUENCE_URL, CONFLUENCE_TOKEN, CONFLUENCE_PAGE_ID")
        sys.exit(1)

    config = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def upload_attachment(filename: str, filepath: Path, config: dict) -> dict:
    """Upload drawio file as attachment to Confluence page."""
    confluence_url = config["CONFLUENCE_URL"]
    page_id = config["CONFLUENCE_PAGE_ID"]
    token = config["CONFLUENCE_TOKEN"]

    print(f"  Uploading {filename}...")

    with open(filepath, 'rb') as f:
        content = f.read()

    # Check if attachment already exists
    check_url = f"{confluence_url}/rest/api/content/{page_id}/child/attachment?filename={urllib.parse.quote(filename)}"
    req = urllib.request.Request(check_url)
    req.add_header("Authorization", f"Bearer {token}")

    url = f"{confluence_url}/rest/api/content/{page_id}/child/attachment"
    attachment_id = None

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            if data.get("results"):
                attachment_id = data["results"][0]["id"]
                url = f"{confluence_url}/rest/api/content/{page_id}/child/attachment/{attachment_id}/data"
                print(f"    Updating existing: {attachment_id}")
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
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("X-Atlassian-Token", "nocheck")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            results = result.get("results", [result])
            if results:
                att_id = results[0].get('id')
                print(f"    OK: attachment ID = {att_id}")
                return {"id": att_id, "filename": filename, "success": True}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:200]
        print(f"    ERROR: {e.code} - {error_body}")

    return {"filename": filename, "success": False}


def load_process_metadata(drawio_filename: str) -> dict:
    """Try to load metadata from corresponding JSON file."""
    json_name = drawio_filename.replace('.drawio', '.json')
    json_path = BPMN_PROCESSES_DIR / json_name

    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return {}


def generate_diagram_section(filename: str, metadata: dict) -> str:
    """Generate Confluence XHTML for a diagram."""
    name = metadata.get("name", filename.replace('.drawio', '').replace('-', ' ').title())
    description = metadata.get("description", "")

    return f'''
<h2>{name}</h2>
{"<p>" + description + "</p>" if description else ""}
<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">{filename}</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>
'''


def generate_bpmn_legend() -> str:
    """Generate BPMN legend (expandable)."""
    return '''
<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда BPMN-нотации</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #67AB9F; width: 200px; color: white;">Зеленый круг</th>
          <td class="confluenceTd">Начальное / конечное событие (успех)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #f8cecc;">Красный круг</th>
          <td class="confluenceTd">Конечное событие (ошибка / отклонение)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #fff2cc;">Желтый прямоугольник</th>
          <td class="confluenceTd">Задача (действие)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #fff2cc;">Желтый ромб с X</th>
          <td class="confluenceTd">XOR-шлюз (исключающий выбор)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #e1d5e7;">Фиолетовый пунктир</th>
          <td class="confluenceTd">Подпроцесс (ссылка на другую диаграмму)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #dae8fc;">Голубая дорожка</th>
          <td class="confluenceTd">Swimlane - зона ответственности роли</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #d5e8d4;">Зеленая дорожка</th>
          <td class="confluenceTd">Swimlane - система / автоматизация</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>
'''


def update_tobe_section(uploaded_files: list, config: dict) -> bool:
    """Update TO-BE section with uploaded BPMN diagrams."""
    confluence_url = config["CONFLUENCE_URL"]
    page_id = config["CONFLUENCE_PAGE_ID"]
    token = config["CONFLUENCE_TOKEN"]

    print("\n[2] Updating TO-BE section...")

    # Get current page
    url = f"{confluence_url}/rest/api/content/{page_id}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req) as resp:
        page = json.loads(resp.read())

    body = page.get("body", {}).get("storage", {}).get("value", "")
    title = page.get("title", "")
    version = page.get("version", {}).get("number", 0)

    # Find H1 TO-BE section
    tobe_match = re.search(
        r'(<h1[^>]*>.*?Общая схема процесса \(TO-BE\).*?</h1>)(.*?)(<h1[^>]*>)',
        body, re.DOTALL | re.IGNORECASE
    )

    if not tobe_match:
        print("  WARNING: TO-BE section not found, will append at end")
        # Append before last </body> or at end
        insert_pos = len(body)
        h1_heading = '<h1><strong>Общая схема процесса (TO-BE)</strong></h1>'
        next_h1 = ''
    else:
        h1_heading = tobe_match.group(1)
        next_h1 = tobe_match.group(3)
        insert_pos = tobe_match.start()

    # Build content from uploaded files
    diagrams_content = "\n<p>Визуализация бизнес-процесса в нотации BPMN.</p>\n"

    for file_info in uploaded_files:
        if file_info.get("success"):
            filename = file_info["filename"]
            metadata = load_process_metadata(filename)
            diagrams_content += generate_diagram_section(filename, metadata)

    diagrams_content += generate_bpmn_legend()

    if tobe_match:
        new_body = body[:tobe_match.start()] + h1_heading + diagrams_content + next_h1 + body[tobe_match.end():]
    else:
        new_body = body + h1_heading + diagrams_content

    # Update page
    update_url = f"{confluence_url}/rest/api/content/{page_id}"
    update_data = {
        "id": page_id,
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
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            new_version = result.get("version", {}).get("number")
            print(f"  SUCCESS: Page updated to version {new_version}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} - {e.read().decode()[:500]}")
        return False


def main():
    args = sys.argv[1:]

    if not args or '-h' in args or '--help' in args:
        print(__doc__)
        sys.exit(0)

    upload_all = '--all' in args
    update_page = '--update-page' in args
    files = [a for a in args if not a.startswith('--')]

    config = load_env()

    print("=" * 60)
    print("Publish BPMN Diagrams to Confluence")
    print("=" * 60)
    print(f"Confluence: {config['CONFLUENCE_URL']}")
    print(f"Page ID: {config['CONFLUENCE_PAGE_ID']}")

    # Collect files to upload
    if upload_all:
        files = list(OUTPUT_DIR.glob("*.drawio"))
        if not files:
            print(f"\nNo .drawio files found in {OUTPUT_DIR}")
            sys.exit(1)
        files = [f.name for f in files]
    elif not files:
        print("\nNo files specified. Use --all or provide file paths.")
        sys.exit(1)

    # Upload files
    print(f"\n[1] Uploading {len(files)} diagram(s)...")
    uploaded = []

    for file_arg in files:
        # Resolve path
        if Path(file_arg).is_absolute():
            filepath = Path(file_arg)
        elif (OUTPUT_DIR / file_arg).exists():
            filepath = OUTPUT_DIR / file_arg
        elif Path(file_arg).exists():
            filepath = Path(file_arg)
        else:
            print(f"  WARNING: {file_arg} not found, skipping")
            continue

        filename = filepath.name
        result = upload_attachment(filename, filepath, config)
        uploaded.append(result)

    # Summary
    success_count = sum(1 for u in uploaded if u.get("success"))
    print(f"\nUploaded: {success_count}/{len(uploaded)}")

    # Update page if requested
    if update_page and success_count > 0:
        update_tobe_section(uploaded, config)

    print("\n" + "=" * 60)
    if success_count > 0:
        print("DONE!")
        print(f"View: {config['CONFLUENCE_URL']}/pages/viewpage.action?pageId={config['CONFLUENCE_PAGE_ID']}")
    else:
        print("No diagrams uploaded.")


if __name__ == "__main__":
    main()
