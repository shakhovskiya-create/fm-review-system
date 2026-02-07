#!/usr/bin/env python3
"""
Export Miro ePC diagrams as images and embed into Confluence TO-BE section.

Steps:
1. Load config from .env.local
2. Export Miro board as PNG
3. Upload to Confluence as attachment
4. Update existing "Общая схема процесса (TO-BE)" section with embedded image
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import ssl
import re
import requests
from datetime import datetime
from pathlib import Path

# Disable SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

# Load config from .env.local
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"

def load_env():
    """Load environment from .env.local file."""
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found")
        print("Create it with CONFLUENCE_TOKEN and MIRO_TOKEN")
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

# Config
CONFLUENCE_URL = CONFIG.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_PAGE_ID = CONFIG.get("CONFLUENCE_PAGE_ID", "83951683")
CONFLUENCE_TOKEN = CONFIG.get("CONFLUENCE_TOKEN", "")
MIRO_TOKEN = CONFIG.get("MIRO_TOKEN", "")
MIRO_BOARD_ID = CONFIG.get("MIRO_BOARD_ID", "uXjVGFq_knA=")

if not CONFLUENCE_TOKEN or not MIRO_TOKEN:
    print("ERROR: Missing tokens in .env.local")
    sys.exit(1)

MIRO_HEADERS = {
    "Authorization": f"Bearer {MIRO_TOKEN}",
    "Accept": "application/json"
}


def export_miro_board_image():
    """Export Miro board as PNG image using export job API."""
    print("[1] Exporting Miro board as image...")

    # Try method 1: Create export job
    export_url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}/export"

    r = requests.post(export_url, headers=MIRO_HEADERS, json={"format": "png"})

    if r.status_code in (200, 201, 202):
        data = r.json()
        print(f"  Export job created: {data}")
        # Check if we have a direct URL
        image_url = data.get("imageUrl") or data.get("url") or data.get("downloadUrl")
        if image_url:
            img_response = requests.get(image_url)
            if img_response.status_code == 200:
                print(f"  Downloaded {len(img_response.content)} bytes")
                return img_response.content
    else:
        print(f"  Export job failed: {r.status_code} - {r.text[:200]}")

    # Try method 2: Get board thumbnail
    print("  Trying thumbnail method...")
    board_url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}"
    r = requests.get(board_url, headers=MIRO_HEADERS)

    if r.status_code == 200:
        data = r.json()
        picture = data.get("picture", {})
        image_url = picture.get("imageUrl") or picture.get("url")
        if image_url:
            print(f"  Found thumbnail URL")
            img_response = requests.get(image_url)
            if img_response.status_code == 200:
                print(f"  Downloaded {len(img_response.content)} bytes")
                return img_response.content

    # Try method 3: Export all frames individually and combine
    print("  Trying frame-by-frame export...")
    frames_url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}/frames"
    r = requests.get(frames_url, headers=MIRO_HEADERS)

    if r.status_code == 200:
        frames = r.json().get("data", [])
        if frames:
            # Get first frame as representative
            frame_id = frames[0].get("id")
            # Try to export frame
            item_export_url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}/items/{frame_id}"
            r = requests.get(item_export_url, headers=MIRO_HEADERS)
            if r.status_code == 200:
                frame_data = r.json()
                print(f"  Frame data: {json.dumps(frame_data, indent=2)[:500]}")

    print("  ERROR: Could not export board image via API")
    print("  Miro REST API v2 has limited export capabilities")
    print("  Manual screenshot or Miro app export required")

    return None


def export_miro_frames_as_images():
    """Export each frame from Miro as separate image using items export."""
    print("[1] Getting frames from Miro...")

    # Get frames
    url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}/frames"
    r = requests.get(url, headers=MIRO_HEADERS)

    if r.status_code != 200:
        print(f"  ERROR getting frames: {r.status_code}")
        return []

    frames = r.json().get("data", [])
    print(f"  Found {len(frames)} frames")

    images = []
    for frame in frames:
        title = frame.get("data", {}).get("title", "Untitled")
        frame_id = frame.get("id")
        print(f"  - {title} ({frame_id})")

        # Export frame as image using items export
        export_url = f"https://api.miro.com/v2/boards/{MIRO_BOARD_ID}/items/{frame_id}/export"

        # Try to export as PNG
        r = requests.post(export_url, headers=MIRO_HEADERS, json={"format": "png"})

        if r.status_code == 200:
            data = r.json()
            image_url = data.get("url") or data.get("imageUrl")
            if image_url:
                img_r = requests.get(image_url)
                if img_r.status_code == 200:
                    images.append({
                        "title": title,
                        "data": img_r.content,
                        "filename": f"epc_{title.replace(' ', '_').replace('.', '')}.png"
                    })
                    print(f"    Downloaded {len(img_r.content)} bytes")
        else:
            print(f"    Export failed: {r.status_code}")

    return images


def upload_to_confluence(filename, content, content_type="image/png"):
    """Upload attachment to Confluence page."""
    print(f"\n[2] Uploading '{filename}' to Confluence...")

    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}/child/attachment"

    # Check if attachment already exists
    check_url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}/child/attachment?filename={urllib.parse.quote(filename)}"
    req = urllib.request.Request(check_url)
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            if data.get("results"):
                # Update existing attachment
                att_id = data["results"][0]["id"]
                url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}/child/attachment/{att_id}/data"
                print(f"  Updating existing attachment {att_id}")
    except:
        pass  # New attachment

    # Upload
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode('utf-8') + content + f"\r\n--{boundary}--\r\n".encode('utf-8')

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("X-Atlassian-Token", "nocheck")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            results = result.get("results", [result])
            if results:
                att_id = results[0].get("id")
                print(f"  SUCCESS: Attachment ID {att_id}")
                return att_id
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} - {e.read().decode()[:300]}")

    return None


def get_confluence_page():
    """Get current page content."""
    print("\n[3] Getting Confluence page...")

    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        print(f"  Title: {data.get('title')}")
        print(f"  Version: {data.get('version', {}).get('number')}")
        return data


def update_tobe_section(page_data, attachment_filename):
    """Update existing TO-BE section with embedded image."""
    print("\n[4] Updating TO-BE section...")

    body = page_data.get("body", {}).get("storage", {}).get("value", "")
    title = page_data.get("title", "")
    version = page_data.get("version", {}).get("number", 0)

    # Find the existing TO-BE section
    # Pattern: <h2>...TO-BE...</h2> followed by content until next <h2>
    pattern = r'(<h2[^>]*>.*?Общая схема процесса.*?TO-BE.*?</h2>)(.*?)(<h2[^>]*>)'

    match = re.search(pattern, body, re.DOTALL | re.IGNORECASE)

    if not match:
        print("  ERROR: TO-BE section not found!")
        return False

    heading = match.group(1)
    old_content = match.group(2)
    next_heading = match.group(3)

    # New content for TO-BE section
    new_content = f'''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

<p><strong>Диаграмма включает 3 процесса:</strong></p>
<ol>
  <li><strong>Основной поток</strong> - Заказ клиента → проверка НПСС → расчет рентабельности → автосогласование/ручное → резерв → отгрузка</li>
  <li><strong>Процесс согласования</strong> - Определение уровня (РБЮ/ДП/ГД) → SLA → эскалация → автоотклонение ГД 48ч</li>
  <li><strong>Экстренное согласование</strong> - Устное разрешение → фиксация → постфактум → инцидент при отклонении</li>
</ol>

<p>
  <ac:image ac:width="100%">
    <ri:attachment ri:filename="{attachment_filename}"/>
  </ac:image>
</p>

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда ePC-нотации (развернуть)</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #C8E6C9; width: 150px;">Зеленый шестиугольник</th>
          <td class="confluenceTd">Начальное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFE0B2;">Оранжевый шестиугольник</th>
          <td class="confluenceTd">Промежуточное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFCDD2;">Красный шестиугольник</th>
          <td class="confluenceTd">Конечное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #B2EBF2;">Голубой скругленный</th>
          <td class="confluenceTd">Функция (действие)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFF9C4;">Желтый ромб</th>
          <td class="confluenceTd">XOR - исключающий выбор</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFECB3;">Светло-желтый овал</th>
          <td class="confluenceTd">Роль / подразделение</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #E0E0E0;">Серый прямоугольник</th>
          <td class="confluenceTd">Информационная система</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #D1C4E9;">Фиолетовый пунктир</th>
          <td class="confluenceTd">Ссылка на другую диаграмму</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>

'''

    # Replace old content with new
    new_body = body[:match.start()] + heading + new_content + next_heading + body[match.end():]

    # Also remove any duplicate "Общая схема процесса" sections I created earlier
    new_body = re.sub(
        r'<h2><strong>Общая схема процесса \(TO-BE\)</strong></h2>.*?(?=<h2>|$)',
        '',
        new_body,
        count=1,  # Remove only the first duplicate (the one I created)
        flags=re.DOTALL | re.IGNORECASE
    )

    # Update page
    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}"
    update_data = {
        "id": CONFLUENCE_PAGE_ID,
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
        url,
        data=json.dumps(update_data).encode('utf-8'),
        method="PUT"
    )
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

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
    print("Miro ePC -> Confluence (with embedded image)")
    print("=" * 60)
    print(f"Board: https://miro.com/app/board/{MIRO_BOARD_ID}")
    print(f"Page ID: {CONFLUENCE_PAGE_ID}")
    print()

    # Step 1: Export Miro board as image
    image_data = export_miro_board_image()

    if not image_data:
        print("\nFATAL: Failed to export Miro board")
        sys.exit(1)

    # Step 2: Upload to Confluence
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"epc_fm_ls_profit_{timestamp}.png"

    att_id = upload_to_confluence(filename, image_data)

    if not att_id:
        print("\nFATAL: Failed to upload image")
        sys.exit(1)

    # Step 3: Get current page
    page_data = get_confluence_page()

    # Step 4: Update TO-BE section
    if update_tobe_section(page_data, filename):
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={CONFLUENCE_PAGE_ID}")
        print(f"Image: {filename}")
    else:
        print("\nFAILED to update page")
        sys.exit(1)


if __name__ == "__main__":
    main()
