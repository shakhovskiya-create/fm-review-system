#!/usr/bin/env python3
"""
Upload all 3 draw.io diagrams to Confluence with process tables.
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

# All 3 diagrams
DIAGRAMS = [
    "epc_main_flow.drawio",
    "epc_approval.drawio",
    "epc_emergency.drawio",
]


def upload_attachment(filename, filepath):
    """Upload file as attachment."""
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


def get_diagram1_content():
    """Diagram 1: Main flow with table."""
    return '''
<h2>Диаграмма 1: Основной поток</h2>

<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">epc_main_flow.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 40px;">№</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 200px;">Этап</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Описание</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 100px;">Роль</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 80px;">Система</th>
    </tr>
    <tr>
      <td class="confluenceTd">1</td>
      <td class="confluenceTd"><strong>Заказ клиента создан</strong></td>
      <td class="confluenceTd">Менеджер создает Заказ клиента на основе ЛС</td>
      <td class="confluenceTd">Менеджер</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">2</td>
      <td class="confluenceTd"><strong>Проверка НПСС</strong></td>
      <td class="confluenceTd">Автоматическая проверка наличия актуальной НПСС для всех товаров</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">3</td>
      <td class="confluenceTd"><strong>Расчет рентабельности</strong></td>
      <td class="confluenceTd">Система рассчитывает отклонение от плановой рентабельности ЛС</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">4a</td>
      <td class="confluenceTd"><strong>Автосогласование</strong></td>
      <td class="confluenceTd">При рентабельности >= 0% заказ автоматически согласуется</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">4b</td>
      <td class="confluenceTd"><strong>Процесс согласования</strong></td>
      <td class="confluenceTd">При рентабельности &lt; 0% запускается ручное согласование (см. Диаграмму 2)</td>
      <td class="confluenceTd">Согласующий</td>
      <td class="confluenceTd">1С:ДО</td>
    </tr>
    <tr>
      <td class="confluenceTd">5</td>
      <td class="confluenceTd"><strong>Создание резерва</strong></td>
      <td class="confluenceTd">После согласования менеджер создает резерв товара</td>
      <td class="confluenceTd">Менеджер</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">6</td>
      <td class="confluenceTd"><strong>Отгрузка товара</strong></td>
      <td class="confluenceTd">Склад производит отгрузку зарезервированного товара</td>
      <td class="confluenceTd">Склад</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
  </tbody>
</table>
'''


def get_diagram2_content():
    """Diagram 2: Approval process with table."""
    return '''
<h2>Диаграмма 2: Процесс согласования</h2>

<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">epc_approval.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Уровень</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Отклонение</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Согласующий</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">SLA</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">При таймауте</th>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>1</strong></td>
      <td class="confluenceTd">от -5% до 0%</td>
      <td class="confluenceTd">РБЮ (Руководитель бизнес-юнита)</td>
      <td class="confluenceTd">4 часа</td>
      <td class="confluenceTd">Эскалация на ДП</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>2</strong></td>
      <td class="confluenceTd">от -15% до -5%</td>
      <td class="confluenceTd">ДП (Директор по продажам)</td>
      <td class="confluenceTd">8 часов</td>
      <td class="confluenceTd">Эскалация на ГД</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>3</strong></td>
      <td class="confluenceTd">менее -15%</td>
      <td class="confluenceTd">ГД (Генеральный директор)</td>
      <td class="confluenceTd">24 часа</td>
      <td class="confluenceTd">Автоотклонение через 48ч</td>
    </tr>
  </tbody>
</table>

<ac:structured-macro ac:name="note">
  <ac:rich-text-body>
    <p><strong>Важно:</strong> При истечении SLA без ответа происходит автоматическая эскалация на следующий уровень. На уровне ГД при отсутствии ответа в течение 48 часов - автоматическое отклонение.</p>
  </ac:rich-text-body>
</ac:structured-macro>
'''


def get_diagram3_content():
    """Diagram 3: Emergency with table."""
    return '''
<h2>Диаграмма 3: Экстренное согласование</h2>

<ac:structured-macro ac:name="drawio">
  <ac:parameter ac:name="diagramName">epc_emergency.drawio</ac:parameter>
  <ac:parameter ac:name="zoom">100</ac:parameter>
  <ac:parameter ac:name="border">true</ac:parameter>
</ac:structured-macro>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 40px;">№</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 200px;">Этап</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Описание</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 100px;">Роль</th>
    </tr>
    <tr>
      <td class="confluenceTd">1</td>
      <td class="confluenceTd"><strong>Срочная отгрузка</strong></td>
      <td class="confluenceTd">Клиент требует срочную отгрузку, стандартное согласование невозможно</td>
      <td class="confluenceTd">Менеджер</td>
    </tr>
    <tr>
      <td class="confluenceTd">2</td>
      <td class="confluenceTd"><strong>Запрос устного разрешения</strong></td>
      <td class="confluenceTd">Менеджер связывается с согласующим по телефону или лично</td>
      <td class="confluenceTd">Менеджер</td>
    </tr>
    <tr>
      <td class="confluenceTd">3</td>
      <td class="confluenceTd"><strong>Фиксация в 1С</strong></td>
      <td class="confluenceTd">Факт устного разрешения фиксируется в комментарии к заказу</td>
      <td class="confluenceTd">Менеджер</td>
    </tr>
    <tr>
      <td class="confluenceTd">4</td>
      <td class="confluenceTd"><strong>Отгрузка товара</strong></td>
      <td class="confluenceTd">Склад производит экстренную отгрузку</td>
      <td class="confluenceTd">Склад</td>
    </tr>
    <tr>
      <td class="confluenceTd">5</td>
      <td class="confluenceTd"><strong>Согласование пост-фактум</strong></td>
      <td class="confluenceTd">В течение 24 часов согласующий подтверждает решение в 1С:ДО</td>
      <td class="confluenceTd">Согласующий</td>
    </tr>
    <tr>
      <td class="confluenceTd">6</td>
      <td class="confluenceTd"><strong>Регистрация инцидента</strong></td>
      <td class="confluenceTd">При отклонении пост-фактум - инцидент + санкции к менеджеру</td>
      <td class="confluenceTd">Система</td>
    </tr>
  </tbody>
</table>

<ac:structured-macro ac:name="warning">
  <ac:rich-text-body>
    <p><strong>Лимиты экстренных согласований:</strong></p>
    <ul>
      <li>Не более 3 в месяц на одного менеджера</li>
      <li>Не более 5 в месяц на одного контрагента</li>
    </ul>
  </ac:rich-text-body>
</ac:structured-macro>
'''


def get_legend():
    """Legend section."""
    return '''
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
          <td class="confluenceTd">Исключающий выбор</td>
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


def update_tobe_section():
    """Update TO-BE section with all diagrams and tables."""
    print("\n[2] Updating TO-BE section...")

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
    next_h1 = tobe_match.group(3)

    # Build new content
    new_content = f'''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

{get_diagram1_content()}

{get_diagram2_content()}

{get_diagram3_content()}

{get_legend()}

'''

    new_body = body[:tobe_match.start()] + h1_heading + new_content + next_h1 + body[tobe_match.end():]

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
    print("Upload All draw.io Diagrams + Tables")
    print("=" * 60)

    # Step 1: Upload all diagrams
    print("\n[1] Uploading diagrams...")
    for filename in DIAGRAMS:
        filepath = DIAGRAMS_DIR / filename
        if filepath.exists():
            upload_attachment(filename, filepath)
        else:
            print(f"  WARNING: {filename} not found")

    # Step 2: Update page
    if update_tobe_section():
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
        print("\n3 draw.io diagrams with process tables added!")


if __name__ == "__main__":
    main()
