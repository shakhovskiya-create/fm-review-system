#!/usr/bin/env python3
"""
Generate ePC diagrams as PNG images using Graphviz.
Upload to Confluence and embed in TO-BE section.

ePC Notation:
- Event (hexagon, pink/red/green) - triggers/results
- Function (rounded rectangle, cyan) - activities
- XOR (diamond, yellow) - exclusive choice
- AND (diamond, orange) - parallel
- Org Unit (ellipse, light yellow) - roles
- System (rectangle, gray) - IT systems
"""

import graphviz
import urllib.request
import urllib.parse
import json
import ssl
import sys
import re
from pathlib import Path
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context

# Load config
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"
OUTPUT_DIR = SCRIPT_DIR / "diagrams"
OUTPUT_DIR.mkdir(exist_ok=True)

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
CONFLUENCE_URL = CONFIG.get("CONFLUENCE_URL")
PAGE_ID = CONFIG.get("CONFLUENCE_PAGE_ID")
TOKEN = CONFIG.get("CONFLUENCE_TOKEN")

# ePC Colors (EKF scheme)
COLORS = {
    'event_start': '#C8E6C9',    # Green - start event
    'event_mid': '#FFE0B2',      # Orange - intermediate event
    'event_end': '#FFCDD2',      # Red - end event
    'function': '#B2EBF2',       # Cyan - function/activity
    'xor': '#FFF9C4',            # Light yellow - XOR gateway
    'and': '#FFECB3',            # Amber - AND gateway
    'org': '#FFFDE7',            # Pale yellow - org unit
    'system': '#ECEFF1',         # Gray - IT system
    'doc': '#FFF8E1',            # Cream - document
}


def create_main_flow_diagram():
    """Diagram 1: Main flow - Order to Shipment."""
    g = graphviz.Digraph('epc_main_flow', format='png')
    g.attr(rankdir='TB', splines='polyline', nodesep='0.5', ranksep='0.7')
    g.attr('node', fontname='Arial', fontsize='10')
    g.attr('edge', fontname='Arial', fontsize='9')

    # Start event
    g.node('E1', 'Заказ клиента\nсоздан', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='2')

    # Function: Check NPSS
    g.node('F1', 'Проверка НПСС\n(автоматически)', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.5')
    g.node('S1', '1С:ERP', shape='box', style='filled', fillcolor=COLORS['system'], width='1.2')

    # XOR: NPSS result
    g.node('X1', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # Event: NPSS passed
    g.node('E2', 'НПСС\nпройден', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')

    # Event: NPSS failed
    g.node('E3', 'НПСС\nне пройден', shape='hexagon', style='filled',
           fillcolor=COLORS['event_end'], width='1.8')

    # Function: Calculate profitability
    g.node('F2', 'Расчет\nрентабельности', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.2')

    # XOR: Profitability result
    g.node('X2', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # Event: Profit OK
    g.node('E4', 'Рентабельность\n>= 0%', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')

    # Event: Profit negative
    g.node('E5', 'Рентабельность\n< 0%', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')

    # Function: Auto-approve
    g.node('F3', 'Авто-\nсогласование', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')

    # Subprocess link
    g.node('P1', 'Процесс\nсогласования', shape='box', style='filled,dashed',
           fillcolor='#E1BEE7', width='2')

    # Function: Create reserve
    g.node('F4', 'Создание\nрезерва', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')
    g.node('O1', 'Менеджер', shape='ellipse', style='filled',
           fillcolor=COLORS['org'], width='1.5')

    # End events
    g.node('E6', 'Заказ\nсогласован', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')
    g.node('E7', 'Резерв\nсоздан', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='1.8')

    # Function: Shipment
    g.node('F5', 'Отгрузка\nтовара', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')
    g.node('O2', 'Склад', shape='ellipse', style='filled',
           fillcolor=COLORS['org'], width='1.5')

    # End event
    g.node('E8', 'Заказ\nотгружен', shape='hexagon', style='filled',
           fillcolor=COLORS['event_end'], width='1.8')

    # Edges
    g.edge('E1', 'F1')
    g.edge('F1', 'X1')
    g.edge('S1', 'F1', style='dashed', arrowhead='none')
    g.edge('X1', 'E2', label='да')
    g.edge('X1', 'E3', label='нет')
    g.edge('E2', 'F2')
    g.edge('F2', 'X2')
    g.edge('X2', 'E4', label='>= 0%')
    g.edge('X2', 'E5', label='< 0%')
    g.edge('E4', 'F3')
    g.edge('E5', 'P1')
    g.edge('F3', 'E6')
    g.edge('P1', 'E6', label='согласовано')
    g.edge('E6', 'F4')
    g.edge('O1', 'F4', style='dashed', arrowhead='none')
    g.edge('F4', 'E7')
    g.edge('E7', 'F5')
    g.edge('O2', 'F5', style='dashed', arrowhead='none')
    g.edge('F5', 'E8')

    return g


def create_approval_diagram():
    """Diagram 2: Approval process."""
    g = graphviz.Digraph('epc_approval', format='png')
    g.attr(rankdir='TB', splines='polyline', nodesep='0.5', ranksep='0.6')
    g.attr('node', fontname='Arial', fontsize='10')
    g.attr('edge', fontname='Arial', fontsize='9')

    # Start
    g.node('E1', 'Требуется\nсогласование', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='2')

    # Function: Determine level
    g.node('F1', 'Определение\nуровня согласования', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.5')
    g.node('S1', '1С:ERP', shape='box', style='filled', fillcolor=COLORS['system'], width='1.2')

    # XOR: Level
    g.node('X1', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # Levels
    g.node('E2', 'Уровень:\nРБЮ', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.5')
    g.node('E3', 'Уровень:\nДП', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.5')
    g.node('E4', 'Уровень:\nГД', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.5')

    # Approvers
    g.node('O1', 'РБЮ', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.2')
    g.node('O2', 'Дир. продаж', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.5')
    g.node('O3', 'Ген. директор', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.5')

    # Function: Wait for decision
    g.node('F2', 'Ожидание\nрешения (SLA)', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.2')

    # XOR: Decision
    g.node('X2', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # Results
    g.node('E5', 'Согласовано', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='1.8')
    g.node('E6', 'Отклонено', shape='hexagon', style='filled',
           fillcolor=COLORS['event_end'], width='1.8')
    g.node('E7', 'Таймаут\n(эскалация)', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')

    # Function: Escalation
    g.node('F3', 'Эскалация на\nследующий уровень', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.2')

    # Auto-reject (GD timeout)
    g.node('E8', 'ГД таймаут\n48ч', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')
    g.node('F4', 'Авто-отклонение', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')

    # Edges
    g.edge('E1', 'F1')
    g.edge('S1', 'F1', style='dashed', arrowhead='none')
    g.edge('F1', 'X1')
    g.edge('X1', 'E2', label='-5..0%')
    g.edge('X1', 'E3', label='-15..-5%')
    g.edge('X1', 'E4', label='< -15%')
    g.edge('E2', 'F2')
    g.edge('E3', 'F2')
    g.edge('E4', 'F2')
    g.edge('O1', 'E2', style='dashed', arrowhead='none')
    g.edge('O2', 'E3', style='dashed', arrowhead='none')
    g.edge('O3', 'E4', style='dashed', arrowhead='none')
    g.edge('F2', 'X2')
    g.edge('X2', 'E5', label='да')
    g.edge('X2', 'E6', label='нет')
    g.edge('X2', 'E7', label='таймаут')
    g.edge('E7', 'F3')
    g.edge('F3', 'X1', style='dashed', label='след. уровень')
    g.edge('E8', 'F4')
    g.edge('F4', 'E6')

    return g


def create_emergency_diagram():
    """Diagram 3: Emergency approval."""
    g = graphviz.Digraph('epc_emergency', format='png')
    g.attr(rankdir='TB', splines='polyline', nodesep='0.5', ranksep='0.6')
    g.attr('node', fontname='Arial', fontsize='10')
    g.attr('edge', fontname='Arial', fontsize='9')

    # Start
    g.node('E1', 'Срочная\nотгрузка', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='2')

    # Function: Request verbal approval
    g.node('F1', 'Запрос устного\nразрешения', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.2')
    g.node('O1', 'Менеджер', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.5')

    # XOR: Got approval?
    g.node('X1', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # Events
    g.node('E2', 'Устное\nразрешение', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')
    g.node('E3', 'Отказ', shape='hexagon', style='filled',
           fillcolor=COLORS['event_end'], width='1.5')

    # Function: Fix in system
    g.node('F2', 'Фиксация в 1С\n(комментарий)', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.2')
    g.node('S1', '1С:ERP', shape='box', style='filled', fillcolor=COLORS['system'], width='1.2')

    # Function: Shipment
    g.node('F3', 'Отгрузка\nтовара', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')
    g.node('O2', 'Склад', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.2')

    # Event: Shipped
    g.node('E4', 'Товар\nотгружен', shape='hexagon', style='filled',
           fillcolor=COLORS['event_mid'], width='1.8')

    # Function: Post-factum approval
    g.node('F4', 'Согласование\nпост-фактум (24ч)', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2.5')
    g.node('O3', 'Согласующий', shape='ellipse', style='filled', fillcolor=COLORS['org'], width='1.5')

    # XOR: Post-factum result
    g.node('X2', 'XOR', shape='diamond', style='filled', fillcolor=COLORS['xor'], width='0.8')

    # End events
    g.node('E5', 'Согласовано\nпост-фактум', shape='hexagon', style='filled',
           fillcolor=COLORS['event_start'], width='2')
    g.node('E6', 'Отклонено\n(инцидент)', shape='hexagon', style='filled',
           fillcolor=COLORS['event_end'], width='2')

    # Function: Incident
    g.node('F5', 'Регистрация\nинцидента', shape='box', style='filled,rounded',
           fillcolor=COLORS['function'], width='2')

    # Edges
    g.edge('E1', 'F1')
    g.edge('O1', 'F1', style='dashed', arrowhead='none')
    g.edge('F1', 'X1')
    g.edge('X1', 'E2', label='да')
    g.edge('X1', 'E3', label='нет')
    g.edge('E2', 'F2')
    g.edge('S1', 'F2', style='dashed', arrowhead='none')
    g.edge('F2', 'F3')
    g.edge('O2', 'F3', style='dashed', arrowhead='none')
    g.edge('F3', 'E4')
    g.edge('E4', 'F4')
    g.edge('O3', 'F4', style='dashed', arrowhead='none')
    g.edge('F4', 'X2')
    g.edge('X2', 'E5', label='да')
    g.edge('X2', 'E6', label='нет')
    g.edge('E6', 'F5')

    return g


def generate_all_diagrams():
    """Generate all 3 ePC diagrams."""
    print("=== Generating ePC Diagrams ===\n")

    diagrams = [
        ('epc_1_main_flow', create_main_flow_diagram(), 'Основной поток'),
        ('epc_2_approval', create_approval_diagram(), 'Процесс согласования'),
        ('epc_3_emergency', create_emergency_diagram(), 'Экстренное согласование'),
    ]

    files = []
    for filename, graph, title in diagrams:
        output_path = OUTPUT_DIR / filename
        graph.render(output_path, cleanup=True)
        png_file = f"{output_path}.png"
        print(f"  Created: {png_file}")
        files.append((f"{filename}.png", title, png_file))

    return files


def upload_to_confluence(filename, filepath):
    """Upload PNG file to Confluence as attachment."""
    print(f"\n  Uploading {filename}...")

    with open(filepath, 'rb') as f:
        content = f.read()

    # Check if attachment exists
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
                print(f"    Updating existing attachment {att_id}")
    except:
        pass

    # Upload
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: image/png\r\n\r\n"
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
                print(f"    SUCCESS: {results[0].get('id')}")
                return True
    except urllib.error.HTTPError as e:
        print(f"    ERROR: {e.code} - {e.read().decode()[:200]}")

    return False


def update_tobe_section(diagram_files):
    """Update TO-BE section with embedded diagrams."""
    print("\n=== Updating Confluence TO-BE Section ===")

    # Get current page
    url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req) as resp:
        page = json.loads(resp.read())

    body = page.get("body", {}).get("storage", {}).get("value", "")
    title = page.get("title", "")
    version = page.get("version", {}).get("number", 0)

    # Create new TO-BE content with embedded images
    diagrams_html = ""
    for filename, diagram_title, _ in diagram_files:
        diagrams_html += f'''
<h3>{diagram_title}</h3>
<p>
  <ac:image ac:width="800">
    <ri:attachment ri:filename="{filename}"/>
  </ac:image>
</p>
'''

    new_content = f'''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

{diagrams_html}

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда ePC-нотации (развернуть)</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #C8E6C9; width: 150px;">Зеленый шестиугольник</th>
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
          <th class="confluenceTh" style="background-color: #FFFDE7;">Бледно-желтый овал</th>
          <td class="confluenceTd">Роль / подразделение</td>
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

    # Find H2 TO-BE section and replace content
    pattern = r'(<h2[^>]*>.*?Общая схема процесса.*?TO-BE.*?</h2>)(.*?)(<h[12][^>]*>)'
    match = re.search(pattern, body, re.DOTALL | re.IGNORECASE)

    if match:
        heading = match.group(1)
        next_heading = match.group(3)
        new_body = body[:match.start()] + heading + new_content + next_heading + body[match.end():]
        print(f"  Found TO-BE section, replacing content")
    else:
        print("  ERROR: TO-BE section not found")
        return False

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
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            new_version = result.get("version", {}).get("number")
            print(f"  SUCCESS: Updated to version {new_version}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERROR: {e.code} - {e.read().decode()[:300]}")
        return False


def main():
    print("=" * 60)
    print("ePC Diagram Generator -> Confluence")
    print("=" * 60)

    # Step 1: Generate diagrams
    diagram_files = generate_all_diagrams()

    # Step 2: Upload to Confluence
    print("\n=== Uploading to Confluence ===")
    for filename, title, filepath in diagram_files:
        upload_to_confluence(filename, filepath)

    # Step 3: Update TO-BE section
    if update_tobe_section(diagram_files):
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
        print("=" * 60)
    else:
        print("\nFAILED to update page")
        sys.exit(1)


if __name__ == "__main__":
    main()
