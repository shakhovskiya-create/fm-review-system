#!/usr/bin/env python3
"""
Embed ePC diagrams from Miro into Confluence FM page.
Uses widget macro (iframe) to embed Miro board directly.
"""

import urllib.request
import urllib.parse
import json
import ssl
import re
import sys
import os

# Disable SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

# === CONFIG ===
# Set CONFLUENCE_TOKEN environment variable before running
CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_PAGE_ID = os.environ.get("CONFLUENCE_PAGE_ID", "83951683")
CONFLUENCE_TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")

MIRO_BOARD_ID = os.environ.get("MIRO_BOARD_ID", "uXjVGFq_knA=")
MIRO_BOARD_URL = f"https://miro.com/app/board/{MIRO_BOARD_ID}"
MIRO_EMBED_URL = f"https://miro.com/app/live-embed/{MIRO_BOARD_ID}/?autoplay=yep"

if not CONFLUENCE_TOKEN:
    print("ERROR: CONFLUENCE_TOKEN environment variable not set")
    sys.exit(1)


def api_request(url, method="GET", data=None):
    """Make API request to Confluence."""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    if data:
        req.data = json.dumps(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  ERROR {e.code}: {e.read().decode('utf-8')[:300]}")
        return None


def get_page():
    """Get current page content."""
    print("[1] Getting current Confluence page...")
    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}?expand=body.storage,version"
    data = api_request(url)
    if data:
        print(f"  Title: {data.get('title')}")
        print(f"  Version: {data.get('version', {}).get('number')}")
        return data
    return None


def create_epc_xhtml():
    """Create ePC section XHTML - TO-BE process diagram section."""
    return f'''
<h2><strong>Общая схема процесса (TO-BE)</strong></h2>

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

<ac:structured-macro ac:name="info">
  <ac:rich-text-body>
    <p><strong>Интерактивные ePC-диаграммы:</strong> <a href="{MIRO_BOARD_URL}">Открыть в Miro</a></p>
    <p>Диаграммы содержат полное описание процесса с ролями, системами, событиями и точками принятия решений.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7;"><strong>Диаграмма</strong></th>
      <th class="confluenceTh" style="background-color: #f4f5f7;"><strong>Описание</strong></th>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>1. Основной поток</strong></td>
      <td class="confluenceTd">Заказ клиента - проверка НПСС - расчет рентабельности - автосогласование (отклонение &lt; 1 п.п.) или ручное согласование - резерв - передача на склад</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>2. Процесс согласования</strong></td>
      <td class="confluenceTd">Определение уровня согласования по отклонению (РБЮ: 1-15 п.п., ДП: 15-25 п.п., ГД: &gt;25 п.п.) - SLA на каждый уровень - автоэскалация при превышении - автоотклонение ГД через 48ч</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>3. Экстренное согласование</strong></td>
      <td class="confluenceTd">Срочный заказ - устное разрешение (телефон/мессенджер) - фиксация факта со скриншотом - постфактум согласование в 1С:ДО (24 раб. часа) - регистрация инцидента при отклонении</td>
    </tr>
  </tbody>
</table>

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда ePC-нотации</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #C8E6C9; width: 140px;">Зеленый (шестиугольник)</th>
          <td class="confluenceTd">Начальное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFE0B2;">Оранжевый (шестиугольник)</th>
          <td class="confluenceTd">Промежуточное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFCDD2;">Красный (шестиугольник)</th>
          <td class="confluenceTd">Конечное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #B2EBF2;">Голубой (скругленный)</th>
          <td class="confluenceTd">Функция (действие)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFF9C4;">Желтый (ромб)</th>
          <td class="confluenceTd">XOR - исключающий выбор</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFECB3;">Светло-желтый (овал)</th>
          <td class="confluenceTd">Организационная единица / роль</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #E0E0E0;">Серый (прямоугольник)</th>
          <td class="confluenceTd">Информационная система (1С:УТ, 1С:ДО)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #D1C4E9;">Фиолетовый (скругленный, пунктир)</th>
          <td class="confluenceTd">Ссылка на другую диаграмму</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>
'''


def update_page(page_data, epc_xhtml):
    """Update page with ePC section."""
    print("\n[2] Updating Confluence page...")

    body = page_data.get("body", {}).get("storage", {}).get("value", "")
    title = page_data.get("title", "")
    version = page_data.get("version", {}).get("number", 0)

    # Remove old ePC/iframe sections if exist
    patterns_to_remove = [
        r'<h2><strong>Схемы процессов.*?(?=<h[12]>|$)',
        r'<h2>Схемы процессов.*?(?=<h[12]>|$)',
        r'<h2><strong>Общая схема процесса.*?(?=<h[12]>|$)',
        r'<h2>Общая схема процесса.*?(?=<h[12]>|$)',
    ]
    for pattern in patterns_to_remove:
        body = re.sub(pattern, '', body, flags=re.DOTALL | re.IGNORECASE)

    # Find "Описание решения" H1 and insert before "Концепция" H2
    # Structure: H1 Описание решения -> (insert here) -> H2 Концепция
    match = re.search(
        r'(<h1[^>]*>.*?Описание решения.*?</h1>)',
        body,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        pos = match.end()
        # Find "Концепция" heading
        koncept_match = re.search(r'(<h2[^>]*>.*?Концепция.*?</h2>)', body[pos:], re.DOTALL | re.IGNORECASE)
        if koncept_match:
            insert_pos = pos + koncept_match.start()
            body = body[:insert_pos] + epc_xhtml + body[insert_pos:]
            print("  Inserted before 'Концепция' (after 'Описание решения')")
        else:
            # Insert right after "Описание решения"
            body = body[:pos] + epc_xhtml + body[pos:]
            print("  Inserted after 'Описание решения'")
    else:
        # Fallback: append at end
        body = body + epc_xhtml
        print("  Appended at end (no 'Описание решения' found)")

    # Update page
    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}"
    data = {
        "id": CONFLUENCE_PAGE_ID,
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

    result = api_request(url, method="PUT", data=data)
    if result:
        new_version = result.get("version", {}).get("number")
        print(f"  SUCCESS: Updated to version {new_version}")
        return True
    return False


def verify_page():
    """Verify the ePC section is in the page."""
    print("\n[3] Verifying...")

    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}?expand=body.storage"
    data = api_request(url)

    if data:
        body = data.get("body", {}).get("storage", {}).get("value", "")

        checks = [
            ("TO-BE heading", "Общая схема процесса (TO-BE)" in body),
            ("Miro URL", MIRO_BOARD_ID in body),
            ("Info panel", 'ac:name="info"' in body),
            ("Legend", "Легенда ePC" in body),
            ("Diagram 1", "Основной поток" in body),
            ("Diagram 2", "Процесс согласования" in body),
            ("Diagram 3", "Экстренное согласование" in body),
            ("No iframe", "iframe" not in body.lower()),
        ]

        all_ok = True
        for name, ok in checks:
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {name}")
            if not ok:
                all_ok = False

        return all_ok
    return False


def main():
    print("=" * 60)
    print("ePC Miro Embed -> Confluence")
    print("=" * 60)
    print(f"Board: {MIRO_BOARD_URL}")
    print(f"Page ID: {CONFLUENCE_PAGE_ID}")
    print()

    # Get current page
    page_data = get_page()
    if not page_data:
        print("FATAL: Cannot get Confluence page")
        sys.exit(1)

    # Create ePC XHTML
    epc_xhtml = create_epc_xhtml()

    # Update page
    if not update_page(page_data, epc_xhtml):
        print("FATAL: Failed to update page")
        sys.exit(1)

    # Verify
    if verify_page():
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={CONFLUENCE_PAGE_ID}")
        print(f"Miro: {MIRO_BOARD_URL}")
    else:
        print("\nWARNING: Verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
