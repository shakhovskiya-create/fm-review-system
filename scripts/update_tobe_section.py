#!/usr/bin/env python3
"""
Update existing "Общая схема процесса (TO-BE)" section in Confluence.
Removes duplicate section and updates the original with proper content.
"""

import os
import sys
import json
import urllib.request
import ssl
import re
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

# Load config from .env.local
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env.local"

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
CONFLUENCE_URL = CONFIG.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_PAGE_ID = CONFIG.get("CONFLUENCE_PAGE_ID", "83951683")
CONFLUENCE_TOKEN = CONFIG.get("CONFLUENCE_TOKEN", "")
MIRO_BOARD_ID = CONFIG.get("MIRO_BOARD_ID", "uXjVGFq_knA=")
MIRO_BOARD_URL = f"https://miro.com/app/board/{MIRO_BOARD_ID}"


def api_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {CONFLUENCE_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  ERROR {e.code}: {e.read().decode()[:500]}")
        return None


def get_tobe_content():
    """Generate the content for TO-BE section."""
    return f'''

<p>Визуализация целевого бизнес-процесса контроля рентабельности в нотации ePC (Event-driven Process Chain).</p>

<ac:structured-macro ac:name="info">
  <ac:rich-text-body>
    <p><strong>Интерактивные ePC-диаграммы:</strong> <a href="{MIRO_BOARD_URL}">Открыть в Miro</a></p>
    <p>На доске представлены 3 взаимосвязанные диаграммы процесса с роялми, системами и точками принятия решений.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<h3><strong>Диаграмма 1: Основной поток контроля рентабельности</strong></h3>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 150px;">Этап</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Описание</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 100px;">Роль</th>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 80px;">Система</th>
    </tr>
    <tr>
      <td class="confluenceTd">1. Создание заказа</td>
      <td class="confluenceTd">Менеджер создает Заказ клиента на основе ЛС</td>
      <td class="confluenceTd">Менеджер</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">2. Проверка НПСС</td>
      <td class="confluenceTd">Система проверяет наличие актуальной НПСС по позициям</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd" style="background-color: #ffebe6;">2а. НПСС = 0</td>
      <td class="confluenceTd" style="background-color: #ffebe6;">Позиция блокируется, уведомление финслужбе (SLA 24ч на исправление)</td>
      <td class="confluenceTd">Финслужба</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">3. Расчет рентабельности</td>
      <td class="confluenceTd">Автоматический расчет фактической рентабельности заказа по текущим ценам</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">4. Проверка отклонения</td>
      <td class="confluenceTd">Сравнение фактической рентабельности с плановой по ЛС</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd" style="background-color: #e3fcef;">4а. Отклонение &lt; 1 п.п.</td>
      <td class="confluenceTd" style="background-color: #e3fcef;">Автосогласование - заказ сразу переходит в статус "Согласован"</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd" style="background-color: #fffae6;">4б. Отклонение &gt;= 1 п.п.</td>
      <td class="confluenceTd" style="background-color: #fffae6;">Запуск процесса согласования (см. Диаграмму 2)</td>
      <td class="confluenceTd">РБЮ/ДП/ГД</td>
      <td class="confluenceTd">1С:ДО</td>
    </tr>
    <tr>
      <td class="confluenceTd">5. Резервирование</td>
      <td class="confluenceTd">После согласования - автоматическое резервирование товара</td>
      <td class="confluenceTd">-</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
    <tr>
      <td class="confluenceTd">6. Передача на склад</td>
      <td class="confluenceTd">Менеджер передает заказ на отгрузку (флаг "Передан на склад")</td>
      <td class="confluenceTd">Менеджер</td>
      <td class="confluenceTd">1С:УТ</td>
    </tr>
  </tbody>
</table>

<h3><strong>Диаграмма 2: Процесс согласования</strong></h3>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Уровень</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Отклонение от плана</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">SLA</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">При превышении SLA</th>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>РБЮ</strong> (Руководитель бизнес-юнита)</td>
      <td class="confluenceTd">1 - 15 п.п.</td>
      <td class="confluenceTd">4 часа</td>
      <td class="confluenceTd">Эскалация на ДП</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>ДП</strong> (Директор по продажам)</td>
      <td class="confluenceTd">15 - 25 п.п.</td>
      <td class="confluenceTd">8 часов</td>
      <td class="confluenceTd">Эскалация на ГД</td>
    </tr>
    <tr>
      <td class="confluenceTd"><strong>ГД</strong> (Генеральный директор)</td>
      <td class="confluenceTd">&gt; 25 п.п.</td>
      <td class="confluenceTd">24 часа</td>
      <td class="confluenceTd">Автоотклонение через 48ч</td>
    </tr>
  </tbody>
</table>

<p><strong>Результаты согласования:</strong></p>
<ul>
  <li><strong>Одобрено</strong> - заказ переходит в статус "Согласован", push + email менеджеру</li>
  <li><strong>Отклонено</strong> - заказ возвращается менеджеру на корректировку с причиной отказа</li>
</ul>

<h3><strong>Диаграмма 3: Экстренное согласование</strong></h3>

<p>Для срочных заказов, когда нет времени на стандартный процесс:</p>

<table class="confluenceTable">
  <tbody>
    <tr>
      <th class="confluenceTh" style="background-color: #f4f5f7; width: 30px;">#</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Шаг</th>
      <th class="confluenceTh" style="background-color: #f4f5f7;">Описание</th>
    </tr>
    <tr>
      <td class="confluenceTd">1</td>
      <td class="confluenceTd">Запрос разрешения</td>
      <td class="confluenceTd">Менеджер запрашивает устное разрешение у согласующего (телефон/мессенджер)</td>
    </tr>
    <tr>
      <td class="confluenceTd">2</td>
      <td class="confluenceTd">Фиксация факта</td>
      <td class="confluenceTd">Скриншот переписки или запись в журнале + ФИО согласующего из справочника</td>
    </tr>
    <tr>
      <td class="confluenceTd">3</td>
      <td class="confluenceTd">Согласование заказа</td>
      <td class="confluenceTd">Заказ переводится в "Согласован" с пометкой "Экстренно"</td>
    </tr>
    <tr>
      <td class="confluenceTd">4</td>
      <td class="confluenceTd">Постфактум</td>
      <td class="confluenceTd">Получение официального согласования в 1С:ДО (SLA 24 раб. часа)</td>
    </tr>
    <tr>
      <td class="confluenceTd" style="background-color: #ffebe6;">5</td>
      <td class="confluenceTd" style="background-color: #ffebe6;">При отклонении</td>
      <td class="confluenceTd" style="background-color: #ffebe6;">Регистрация инцидента, включение в отчет для руководства</td>
    </tr>
  </tbody>
</table>

<ac:structured-macro ac:name="note">
  <ac:rich-text-body>
    <p><strong>Лимиты экстренных согласований:</strong></p>
    <ul>
      <li>3 экстренных согласования в месяц на менеджера</li>
      <li>5 экстренных согласований в месяц на контрагента</li>
    </ul>
    <p>При превышении - автоматическое уведомление руководителю.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<ac:structured-macro ac:name="expand">
  <ac:parameter ac:name="title">Легенда ePC-нотации (для диаграмм в Miro)</ac:parameter>
  <ac:rich-text-body>
    <table class="confluenceTable">
      <tbody>
        <tr>
          <th class="confluenceTh" style="background-color: #C8E6C9; width: 180px;">Зеленый шестиугольник</th>
          <td class="confluenceTd">Начальное событие (триггер процесса)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFE0B2;">Оранжевый шестиугольник</th>
          <td class="confluenceTd">Промежуточное событие</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFCDD2;">Красный шестиугольник</th>
          <td class="confluenceTd">Конечное событие (завершение ветки)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #B2EBF2;">Голубой скругленный</th>
          <td class="confluenceTd">Функция (действие, операция)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFF9C4;">Желтый ромб XOR</th>
          <td class="confluenceTd">Исключающий выбор (только один путь)</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #FFECB3;">Светло-желтый овал</th>
          <td class="confluenceTd">Роль / организационная единица</td>
        </tr>
        <tr>
          <th class="confluenceTh" style="background-color: #E0E0E0;">Серый прямоугольник</th>
          <td class="confluenceTd">Информационная система (1С:УТ, 1С:ДО)</td>
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


def main():
    print("=" * 60)
    print("Update TO-BE Section in Confluence")
    print("=" * 60)

    # Get current page
    print("\n[1] Getting current page...")
    url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}?expand=body.storage,version"
    page_data = api_request(url)

    if not page_data:
        print("FATAL: Cannot get page")
        sys.exit(1)

    body = page_data.get("body", {}).get("storage", {}).get("value", "")
    title = page_data.get("title", "")
    version = page_data.get("version", {}).get("number", 0)
    print(f"  Title: {title}")
    print(f"  Version: {version}")

    # Step 1: Remove duplicate TO-BE section (the one I created with bold heading)
    print("\n[2] Removing duplicate TO-BE section...")
    original_len = len(body)

    # Pattern to match my duplicate section (with <strong> tags in heading)
    # My section has: <h2><strong>Общая схема процесса (TO-BE)</strong></h2>
    # Original has: <h2><strong>Общая схема процесса (TO-BE)</strong></h2> (same format but different position)

    # Find and remove the duplicate (second occurrence or any orphaned one after Концепция)
    # The duplicate is likely between "Описание решения" and "Концепция"
    duplicate_pattern = r'(<h2><strong>Общая схема процесса \(TO-BE\)</strong></h2>.*?)(<h2><strong>Концепция</strong></h2>)'

    match = re.search(duplicate_pattern, body, re.DOTALL | re.IGNORECASE)
    if match:
        # Check if this is a duplicate (should be between H1 Описание решения and H2 Концепция directly)
        # If there's content between them that looks like my inserted content, remove it
        content_between = match.group(1)
        if 'Интерактивные ePC-диаграммы' in content_between or 'live-embed' in content_between.lower():
            # This is my duplicate, remove it but keep Концепция
            body = body[:match.start()] + match.group(2) + body[match.end():]
            print(f"  Removed duplicate section ({len(content_between)} chars)")

    # Step 2: Find the H2 TO-BE section and update it (it's after "Описание решения")
    print("\n[3] Updating H2 TO-BE section...")

    # There are 2 TO-BE sections:
    # 1. H2 at ~14385 (inside "Описание решения") - UPDATE THIS ONE
    # 2. H1 at ~110914 (separate section at end) - KEEP AS IS

    # Find H2 TO-BE followed by content until next H2 or H1
    pattern = r'(<h2[^>]*><strong>Общая схема процесса \(TO-BE\)</strong></h2>)(.*?)(<h[12][^>]*>)'

    match = re.search(pattern, body, re.DOTALL | re.IGNORECASE)

    if match:
        heading = match.group(1)
        old_content = match.group(2)
        next_heading = match.group(3)

        new_content = get_tobe_content()
        new_body = body[:match.start()] + heading + new_content + next_heading + body[match.end():]

        print(f"  Original content: {len(old_content)} chars")
        print(f"  New content: {len(new_content)} chars")
    else:
        print("  ERROR: H2 TO-BE section not found")
        print("  Trying alternative pattern...")

        # Try without strong tags
        pattern2 = r'(<h2[^>]*>.*?Общая схема процесса.*?TO-BE.*?</h2>)(.*?)(<h[12][^>]*>)'
        match = re.search(pattern2, body, re.DOTALL | re.IGNORECASE)

        if match:
            heading = match.group(1)
            old_content = match.group(2)
            next_heading = match.group(3)
            new_content = get_tobe_content()
            new_body = body[:match.start()] + heading + new_content + next_heading + body[match.end():]
            print(f"  Found with alternative pattern")
            print(f"  Original: {len(old_content)} chars, New: {len(new_content)} chars")
        else:
            print("  FATAL: Cannot find H2 TO-BE section")
            sys.exit(1)

    # Step 3: Update page
    print("\n[4] Updating Confluence page...")

    update_url = f"{CONFLUENCE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}"
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

    result = api_request(update_url, method="PUT", data=update_data)

    if result:
        new_version = result.get("version", {}).get("number")
        print(f"  SUCCESS: Updated to version {new_version}")

        print("\n" + "=" * 60)
        print("DONE!")
        print(f"Page: {CONFLUENCE_URL}/pages/viewpage.action?pageId={CONFLUENCE_PAGE_ID}")
        print(f"Miro: {MIRO_BOARD_URL}")
    else:
        print("FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
