#!/usr/bin/env python3
"""
Fix diagram location - move from Технические ограничения to TO-BE section.
"""

import urllib.request
import json
import ssl
import re
import sys
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

print("=== Fixing Diagram Location ===\n")

# Step 1: Get page
print("[1] Getting page...")
url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Accept", "application/json")

with urllib.request.urlopen(req) as resp:
    page = json.loads(resp.read())

body = page.get("body", {}).get("storage", {}).get("value", "")
title = page.get("title", "")
version = page.get("version", {}).get("number", 0)
print(f"  Version: {version}")

# Step 2: Find and extract the wrongly placed content
print("\n[2] Finding wrongly placed diagrams...")

# The diagrams are after "Технические ограничения" H1, inside H2 "Проблема фактической себестоимости"
# Find the pattern: after H2 Проблема... there's <p>Визуализация... and diagrams

# Pattern: Find the diagram content block (from "Визуализация" to end of legend)
diagram_pattern = r'(<p>Визуализация целевого бизнес-процесса.*?</ac:structured-macro>\s*)'

# Find all matches
matches = list(re.finditer(diagram_pattern, body, re.DOTALL))
print(f"  Found {len(matches)} diagram block(s)")

if not matches:
    print("  ERROR: No diagram blocks found")
    sys.exit(1)

# The wrong one is the one AFTER "Технические ограничения"
tech_pos = body.find("Технические ограничения")
print(f"  'Технические ограничения' at position {tech_pos}")

wrong_block = None
wrong_match = None
for m in matches:
    if m.start() > tech_pos:
        wrong_block = m.group(1)
        wrong_match = m
        print(f"  Found wrong block at position {m.start()} (length: {len(wrong_block)})")
        break

if not wrong_block:
    print("  ERROR: Could not find wrong diagram block")
    sys.exit(1)

# Step 3: Remove the wrong block
print("\n[3] Removing wrong block...")
body = body[:wrong_match.start()] + body[wrong_match.end():]
print(f"  Removed {len(wrong_block)} chars")

# Step 4: Find correct H1 TO-BE section
print("\n[4] Finding correct TO-BE section...")

# H1 TO-BE is before "Пилотный период"
tobe_h1_pattern = r'(<h1[^>]*><strong>Общая схема процесса \(TO-BE\)</strong></h1>)(.*?)(<h1[^>]*>)'
tobe_match = re.search(tobe_h1_pattern, body, re.DOTALL)

if not tobe_match:
    # Try alternative pattern
    tobe_h1_pattern = r'(<h1[^>]*>.*?Общая схема процесса.*?TO-BE.*?</h1>)(.*?)(<h1[^>]*>)'
    tobe_match = re.search(tobe_h1_pattern, body, re.DOTALL)

if not tobe_match:
    print("  ERROR: H1 TO-BE section not found")
    sys.exit(1)

h1_heading = tobe_match.group(1)
old_content = tobe_match.group(2)
next_h1 = tobe_match.group(3)

print(f"  Found H1 TO-BE at position {tobe_match.start()}")
print(f"  Current content length: {len(old_content)}")

# Step 5: Create new content for TO-BE section
print("\n[5] Creating new content...")

new_tobe_content = '''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

<h2>Диаграмма 1: Основной поток</h2>
<p>Заказ клиента → Проверка НПСС → Расчет рентабельности → Автосогласование/Ручное согласование → Резерв → Отгрузка</p>
<p>
  <ac:image ac:width="900">
    <ri:attachment ri:filename="epc_1_main_flow.png"/>
  </ac:image>
</p>

<h2>Диаграмма 2: Процесс согласования</h2>
<p>Определение уровня (РБЮ/ДП/ГД) → SLA → Ожидание решения → Эскалация при таймауте → Автоотклонение ГД 48ч</p>
<p>
  <ac:image ac:width="900">
    <ri:attachment ri:filename="epc_2_approval.png"/>
  </ac:image>
</p>

<h2>Диаграмма 3: Экстренное согласование</h2>
<p>Срочная отгрузка → Устное разрешение → Фиксация в 1С → Постфактум согласование 24ч → Инцидент при отклонении</p>
<p>
  <ac:image ac:width="900">
    <ri:attachment ri:filename="epc_3_emergency.png"/>
  </ac:image>
</p>

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
          <th class="confluenceTh" style="background-color: #B2EBF2;">Голубой скругленный прямоугольник</th>
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
          <th class="confluenceTh" style="background-color: #E1BEE7;">Фиолетовый пунктирный прямоугольник</th>
          <td class="confluenceTd">Ссылка на подпроцесс (другую диаграмму)</td>
        </tr>
      </tbody>
    </table>
  </ac:rich-text-body>
</ac:structured-macro>

'''

# Step 6: Replace TO-BE content
print("\n[6] Replacing TO-BE content...")
new_body = body[:tobe_match.start()] + h1_heading + new_tobe_content + next_h1 + body[tobe_match.end():]
print(f"  New content length: {len(new_tobe_content)}")

# Step 7: Update page
print("\n[7] Updating Confluence page...")

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
except urllib.error.HTTPError as e:
    print(f"  ERROR: {e.code} - {e.read().decode()[:500]}")
    sys.exit(1)

# Step 8: Verify
print("\n[8] Verifying...")
url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {TOKEN}")

with urllib.request.urlopen(req) as resp:
    page = json.loads(resp.read())

body = page.get("body", {}).get("storage", {}).get("value", "")

# Check diagrams are in TO-BE, not in Технические ограничения
tobe_pos = body.find("Общая схема процесса (TO-BE)")
tech_pos = body.find("Технические ограничения")

diagram_positions = [body.find("epc_1_main_flow.png"), body.find("epc_2_approval.png"), body.find("epc_3_emergency.png")]

print(f"  TO-BE section at: {tobe_pos}")
print(f"  Технические ограничения at: {tech_pos}")
print(f"  Diagram positions: {diagram_positions}")

all_in_tobe = all(tobe_pos < pos < tech_pos for pos in diagram_positions if pos > 0)
print(f"  All diagrams in TO-BE section: {all_in_tobe}")

if all_in_tobe:
    print("\n" + "=" * 50)
    print("SUCCESS! Diagrams moved to correct TO-BE section.")
    print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
else:
    print("\n  WARNING: Diagram positions may not be correct")
