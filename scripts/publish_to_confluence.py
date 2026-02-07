#!/usr/bin/env python3
"""
FM Publisher for Confluence v2.0
- Word -> Confluence XHTML
- Таблицы с цветами
- Жирные заголовки разделов
- Warning/Note панели
- Фильтрация дубликатов
"""
import json, urllib.request, ssl, re, sys, os
from datetime import datetime
import docx
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

ssl._create_default_https_context = ssl._create_unverified_context

# Config - set CONFLUENCE_TOKEN environment variable before running
CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "https://confluence.ekf.su")
TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")


def _get_page_id(project_name=None):
    """PAGE_ID: 1) файл projects/PROJECT/CONFLUENCE_PAGE_ID, 2) env CONFLUENCE_PAGE_ID, 3) fallback только для совместимости."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_name:
        path = os.path.join(root, "projects", project_name, "CONFLUENCE_PAGE_ID")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and line.isdigit():
                        return line
    pid = os.environ.get("CONFLUENCE_PAGE_ID")
    if pid:
        return pid
    # Fallback только для одного известного проекта (совместимость)
    return "83951683"


if not TOKEN:
    print("ERROR: CONFLUENCE_TOKEN environment variable not set")
    print("Run: export CONFLUENCE_TOKEN='your-token-here'")
    sys.exit(1)

# Текст который нужно пропустить (описания компонентов системы кодов - уже в таблице)
SKIP_AFTER_CODE_SYSTEM = [
    "Маршруты согласования",
    "Дашборды и аналитика",
    "Интеграции",
    "Расчетные правила",
    "Уведомления",
    "Документы",
    "Автоматические проверки",
]

# Document path and project (for PAGE_ID from file)
if len(sys.argv) > 1:
    DOC_PATH = sys.argv[1]
else:
    print("Usage: python3 publish_to_confluence.py <path-to-docx>")
    print("Example: python3 publish_to_confluence.py projects/PROJECT_SHPMNT_PROFIT/FM_DOCUMENTS/FM-LS-PROFIT-v1.2.1.docx")
    sys.exit(1)

# PAGE_ID: из файла проекта (по пути к doc или env PROJECT) или из env CONFLUENCE_PAGE_ID
_project_from_path = None
_norm = os.path.normpath(DOC_PATH)
if os.sep + "projects" + os.sep in _norm or _norm.startswith("projects" + os.sep):
    parts = _norm.replace(os.sep, "/").split("projects/")
    if len(parts) > 1:
        _project_from_path = parts[1].split("/")[0]
PAGE_ID = _get_page_id(_project_from_path or os.environ.get("PROJECT"))

print("=" * 60)
print("FM PUBLISHER - CONFLUENCE v2.0")
print("=" * 60)

# Load document
doc = docx.Document(DOC_PATH)
print(f"Документ: {DOC_PATH.split('/')[-1]}")

# Extract metadata from filename
filename = os.path.basename(DOC_PATH)
match = re.match(r'(FM-[A-Z-]+)-v(\d+\.\d+\.\d+)\.docx', filename)
if match:
    FM_CODE = match.group(1)
    FM_VERSION = "1.0.0"  # Всегда начинаем с 1.0.0 в Confluence
else:
    FM_CODE = "FM-UNKNOWN"
    FM_VERSION = "1.0.0"

# Get title from first paragraph
FM_NAME = ""
for para in doc.paragraphs[:5]:
    if para.style and 'Title' in para.style.name:
        FM_NAME = para.text.strip()
        break
if not FM_NAME:
    FM_NAME = FM_CODE

print(f"Код: {FM_CODE}, Версия: {FM_VERSION}")
print(f"Название: {FM_NAME[:50]}...")

# === Color mapping ===
def hex_to_confluence_color(hex_color):
    """Map Word cell color to Confluence background"""
    if not hex_color or hex_color in ('auto', 'none'):
        return None
    hex_color = hex_color.upper()

    COLOR_MAP = {
        'FFDD00': '#fffae6',  # Yellow header
        'DCFCE7': '#e3fcef',  # Green
        'FEF3C7': '#fffae6',  # Amber/Yellow - для warning
        'FED7AA': '#fffae6',  # Orange - для warning (светло-желтый!)
        'FAE2D5': '#ffebe6',  # Peach/Salmon - для note (светло-красный!)
        'FECACA': '#ffebe6',  # Red - для note
        'FEE2E2': '#ffebe6',  # Light red
        'DBEAFE': '#deebff',  # Blue
        'F3F4F6': '#f4f5f7',  # Gray
        'E5E7EB': '#ebecf0',  # Gray darker
    }

    if hex_color in COLOR_MAP:
        return COLOR_MAP[hex_color]

    # Analyze RGB
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        if r > 200 and g > 200 and b < 150:
            return '#fffae6'  # Yellow
        if g > 200 and r < 200:
            return '#e3fcef'  # Green
        if r > 200 and g < 200:
            return '#ffebe6'  # Red/Orange
        if b > 200 and r < 200:
            return '#deebff'  # Blue
    except:
        pass

    return None

def get_cell_color(cell):
    """Extract fill color from Word cell"""
    tc = cell._tc
    tcPr = tc.find(qn('w:tcPr'))
    if tcPr is not None:
        shd = tcPr.find(qn('w:shd'))
        if shd is not None:
            return shd.get(qn('w:fill'))
    return None

# === Convert to XHTML ===
def escape_html(text):
    """Escape HTML special characters"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def para_to_html(para, make_bold=False):
    """Convert paragraph to Confluence XHTML"""
    text = para.text.strip()
    if not text:
        return ""

    text = escape_html(text)
    style = para.style.name if para.style else "Normal"

    # Заголовки - жирным
    if style == "Title":
        return f'<h1><strong>{text}</strong></h1>'
    elif style == "Heading 1":
        return f'<h1><strong>{text}</strong></h1>'
    elif style == "Heading 2":
        return f'<h2><strong>{text}</strong></h2>'
    elif style == "Heading 3":
        return f'<h3><strong>{text}</strong></h3>'
    elif "List" in style or text.startswith("*") or text.startswith("-"):
        # Clean bullet
        text = re.sub(r'^[*\-]\s*', '', text)
        return f'<li>{text}</li>'
    else:
        # Обычный параграф
        if make_bold:
            return f'<p><strong>{text}</strong></p>'
        return f'<p>{text}</p>'

def is_warning_table(table):
    """Check if table is a warning/note callout - only for real warnings with keywords"""
    if len(table.rows) == 1 and len(table.rows[0].cells) == 1:
        text = table.rows[0].cells[0].text.strip().lower()
        color = get_cell_color(table.rows[0].cells[0])

        # Keywords for critical (warning = КРАСНАЯ панель в Confluence Server)
        critical_keywords = ['критич', 'зависимость', 'critical']
        # Keywords for info/note (note = ЖЁЛТАЯ панель в Confluence Server)
        note_keywords = ['исключение', 'важно', 'внимание', '⚠']

        is_critical = any(kw in text for kw in critical_keywords)
        is_note = any(kw in text for kw in note_keywords)

        if not is_critical and not is_note:
            return None  # Обычная 1x1 таблица - не панель!

        # Критические = warning (КРАСНАЯ панель в Confluence)
        if is_critical:
            return 'warning'

        # Предупреждения = note (ЖЁЛТАЯ панель в Confluence)
        if is_note:
            return 'note'

    return None

def is_history_table(table):
    """Check if this is version history table"""
    if len(table.rows) > 0:
        first_cell = table.rows[0].cells[0].text.strip().lower()
        # 'верси' ловит и 'версия' и 'версии' и 'версий'
        if 'верси' in first_cell or 'version' in first_cell or 'история' in first_cell:
            return True
    return False

def is_meta_table(table):
    """Check if this is the metadata table (Версия/Дата/Статус/Автор)"""
    if len(table.rows) >= 3 and len(table.rows[0].cells) == 2:
        first_cell = table.rows[0].cells[0].text.strip().lower()
        second_row = table.rows[1].cells[0].text.strip().lower()
        if first_cell == 'версия' and second_row == 'дата':
            return True
    return False

def meta_table_to_html(table):
    """Render meta-table with auto-date"""
    today = datetime.now().strftime("%d.%m.%Y")
    rows_data = []
    for row in table.rows:
        key = row.cells[0].text.strip()
        val = row.cells[1].text.strip()
        # Подмена даты на текущую
        if key.lower() == 'дата':
            val = today
        # Подмена версии
        if key.lower() == 'версия':
            val = FM_VERSION
        rows_data.append((key, val))

    html = '<table class="confluenceTable"><tbody>'
    for key, val in rows_data:
        html += f'<tr><td class="confluenceTd" style="background-color: #f4f5f7;"><strong>{escape_html(key)}</strong></td>'
        html += f'<td class="confluenceTd">{escape_html(val)}</td></tr>'
    html += '</tbody></table>'
    return html

def history_table_to_html(table):
    """Render history table with only one clean entry"""
    today = datetime.now().strftime("%d.%m.%Y")
    # Header row
    headers = [escape_html(c.text.strip()) for c in table.rows[0].cells]
    html = '<table class="confluenceTable"><tbody>'
    html += '<tr>'
    for h in headers:
        html += f'<th class="confluenceTh" style="background-color: #f4f5f7;"><strong>{h}</strong></th>'
    html += '</tr>'
    # Одна чистая запись
    html += f'<tr><td class="confluenceTd">1.0.0</td>'
    html += f'<td class="confluenceTd">{today}</td>'
    html += f'<td class="confluenceTd">Шаховский А.С.</td>'
    html += f'<td class="confluenceTd">Первая публикация в Confluence</td></tr>'
    html += '</tbody></table>'
    return html

def table_to_html(table, panel_type=None):
    """Convert Word table to Confluence XHTML table"""

    # Warning panel (КРАСНАЯ в Confluence Server) - для ⛔ критических
    if panel_type == 'warning':
        cell_text = escape_html(table.rows[0].cells[0].text.strip())
        # Убираем эмодзи ⛔ - Confluence panel уже имеет свою иконку
        cell_text = re.sub(r'^⛔\s*', '', cell_text)
        return f'''<ac:structured-macro ac:name="warning">
<ac:rich-text-body><p>{cell_text}</p></ac:rich-text-body>
</ac:structured-macro>'''

    # Note panel (ЖЁЛТАЯ в Confluence Server) - для ⚠ предупреждений
    if panel_type == 'note':
        cell_text = escape_html(table.rows[0].cells[0].text.strip())
        # Убираем эмодзи ⚠ - Confluence panel уже имеет свою иконку
        cell_text = re.sub(r'^[⚠️]+\s*', '', cell_text)
        return f'''<ac:structured-macro ac:name="note">
<ac:rich-text-body><p>{cell_text}</p></ac:rich-text-body>
</ac:structured-macro>'''

    # Regular table with styling
    html = '<table class="confluenceTable"><tbody>'
    for i, row in enumerate(table.rows):
        # Пропускаем пустые строки
        row_text = ''.join(c.text.strip() for c in row.cells)
        if not row_text and i > 0:
            continue

        html += '<tr>'
        for cell in row.cells:
            tag = 'th' if i == 0 else 'td'
            cell_class = 'confluenceTh' if i == 0 else 'confluenceTd'
            cell_text = escape_html(cell.text.strip())

            # Get background color
            color = get_cell_color(cell)
            bg = hex_to_confluence_color(color) if color else None

            # Header row - bold and gray background
            if i == 0:
                bg = bg or '#f4f5f7'
                html += f'<{tag} class="{cell_class}" style="background-color: {bg};"><strong>{cell_text}</strong></{tag}>'
            elif bg:
                html += f'<{tag} class="{cell_class}" style="background-color: {bg};">{cell_text}</{tag}>'
            else:
                html += f'<{tag} class="{cell_class}">{cell_text}</{tag}>'
        html += '</tr>'
    html += '</tbody></table>'
    return html

def should_skip_paragraph(text, skip_mode):
    """Check if paragraph should be skipped"""
    if not skip_mode:
        return False

    text_lower = text.lower().strip()
    for pattern in SKIP_AFTER_CODE_SYSTEM:
        if text_lower.startswith(pattern.lower()):
            return True

    # Skip FM-REQ-XXX lines
    if re.match(r'^FM-REQ-\d+', text):
        return True

    return False

# === Build content ===
print("\n=== ПОСТРОЕНИЕ КОНТЕНТА ===")

html_parts = []
in_list = False
skip_code_system_descriptions = False
seen_code_system_table = False
in_code_system_section = False
code_system_items = []  # Собираем пары (код, описание)

# Add header with metadata
today = datetime.now().strftime("%d.%m.%Y")
header = f'''<p><strong>Код:</strong> {FM_CODE} | <strong>Версия:</strong> {FM_VERSION} | <strong>Дата:</strong> {today}</p>
<hr/>'''
html_parts.append(header)

# Iterate through document body in order
for element in doc.element.body:
    if isinstance(element, CT_P):
        para = Paragraph(element, doc)
        text = para.text.strip()

        if not text:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue

        # Skip date line
        if text.startswith("Дата последнего изменения"):
            continue

        style = para.style.name if para.style else "Normal"

        # === Система кодов: собираем в таблицу ===
        # Начало секции
        if "система кодов" in text.lower() and style in ["Heading 2", "Heading 3"]:
            in_code_system_section = True
            skip_code_system_descriptions = True
            html_parts.append(para_to_html(para))  # Заголовок
            continue

        # Конец секции - генерируем таблицу из собранных items
        if in_code_system_section and style in ["Heading 1", "Heading 2"] and "система кодов" not in text.lower():
            in_code_system_section = False
            skip_code_system_descriptions = False
            # Генерируем таблицу из собранных кодов
            if code_system_items:
                tbl = '<table class="confluenceTable"><tbody>'
                tbl += '<tr><th class="confluenceTh" style="background-color: #f4f5f7;"><strong>Код</strong></th>'
                tbl += '<th class="confluenceTh" style="background-color: #f4f5f7;"><strong>Описание</strong></th></tr>'
                for code_name, desc in code_system_items:
                    tbl += f'<tr><td class="confluenceTd"><strong>{escape_html(code_name)}</strong></td>'
                    tbl += f'<td class="confluenceTd">{escape_html(desc)}</td></tr>'
                tbl += '</tbody></table>'
                html_parts.append(tbl)
                code_system_items = []
            # Продолжаем обработку текущего заголовка (не continue!)

        # Внутри секции - собираем пары
        if in_code_system_section:
            # Пропускаем вводный текст "В документе используется..."
            if text.startswith('В документе') or text.startswith('в документе'):
                continue
            # Строка с кодом: "• LS-BR-XXX - Описание"
            code_match = re.match(r'^[•\-]\s*(LS-\w+-XXX)\s*[-–]\s*(.+)', text)
            if code_match:
                code_system_items.append((code_match.group(1), code_match.group(2)))
                continue
            # Строка с описанием (продолжение предыдущего кода)
            if code_system_items and not text.startswith('•'):
                # Добавляем к описанию последнего кода
                last_code, last_desc = code_system_items[-1]
                # Убираем двойную точку при конкатенации
                sep = ' ' if last_desc.rstrip().endswith('.') else '. '
                code_system_items[-1] = (last_code, last_desc.rstrip() + sep + text)
                continue
            continue  # Пропускаем остальное в этой секции

        # Skip descriptions that are already in code system table (after table 24)
        if skip_code_system_descriptions and should_skip_paragraph(text, skip_code_system_descriptions):
            continue

        # Reset skip mode on new major section
        if style in ["Heading 1", "Heading 2"] and not "система кодов" in text.lower():
            skip_code_system_descriptions = False

        # ⚠️ параграфы - оборачиваем в note panel (ЖЁЛТАЯ в Confluence)
        # Убираем эмодзи - Confluence note panel уже имеет иконку !
        if text.startswith('⚠') and style == 'Normal':
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            # Убираем ⚠️ из начала текста
            clean = re.sub(r'^[⚠️\ufe0f]+\s*', '', text)
            warning_text = escape_html(clean)
            html_parts.append(f'''<ac:structured-macro ac:name="note">
<ac:rich-text-body><p>{warning_text}</p></ac:rich-text-body>
</ac:structured-macro>''')
            continue

        # Handle lists
        if "List" in style or text.startswith("*") or text.startswith("-"):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            clean_text = re.sub(r'^[*\-]\s*', '', text)
            html_parts.append(f'<li>{escape_html(clean_text)}</li>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(para_to_html(para))

    elif isinstance(element, CT_Tbl):
        if in_list:
            html_parts.append('</ul>')
            in_list = False

        table = Table(element, doc)

        # 1) Мета-таблица (Версия/Дата/Статус/Автор) - подменяем дату
        if is_meta_table(table):
            html_parts.append(meta_table_to_html(table))
            continue

        # 2) История версий - обнуляем, оставляем 1 запись
        if is_history_table(table) and len(table.rows) > 2:
            html_parts.append(history_table_to_html(table))
            continue

        # 3) Warning/Note panel (1x1 colored)
        if len(table.rows) == 1 and len(table.rows[0].cells) == 1:
            panel_type = is_warning_table(table)
            if panel_type:
                html_parts.append(table_to_html(table, panel_type))
                continue

        # 4) Regular table
        html_parts.append(table_to_html(table))

        # Mark code system table
        first_row_text = ' '.join([c.text for c in table.rows[0].cells]).lower() if table.rows else ''
        if 'код' in first_row_text and ('наименование' in first_row_text or 'описание' in first_row_text):
            seen_code_system_table = True
            skip_code_system_descriptions = True

if in_list:
    html_parts.append('</ul>')

# Join all parts
content = '\n'.join(html_parts)
print(f"  Сгенерировано: {len(content)} символов HTML")

# === Update Confluence page ===
print("\n=== ОБНОВЛЕНИЕ CONFLUENCE ===")

def api_request(method, endpoint, data=None):
    """Make Confluence API request"""
    url = f"{CONFLUENCE_URL}/rest/api/{endpoint}"

    if data:
        data = json.dumps(data).encode('utf-8')

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {TOKEN}')
    req.add_header('Content-Type', 'application/json')

    try:
        response = urllib.request.urlopen(req, timeout=30)
        return json.load(response)
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code}")
        print(e.read().decode()[:500])
        return None

# Get current page version
page_info = api_request("GET", f"content/{PAGE_ID}?expand=version")
if not page_info:
    print("ОШИБКА: Не удалось получить информацию о странице")
    sys.exit(1)

current_version = page_info['version']['number']
page_title = page_info['title']
print(f"  Страница: {page_title}")
print(f"  Текущая версия: {current_version}")

# Update page
update_data = {
    "id": PAGE_ID,
    "type": "page",
    "title": FM_NAME,  # Без версии - используем встроенную версионность Confluence
    "body": {
        "storage": {
            "value": content,
            "representation": "storage"
        }
    },
    "version": {
        "number": current_version + 1
    }
}

result = api_request("PUT", f"content/{PAGE_ID}", update_data)
if result:
    print(f"  Новая версия: {result['version']['number']}")
    print(f"\n✅ ГОТОВО!")
    print(f"URL: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
else:
    print("❌ ОШИБКА обновления страницы")
    sys.exit(1)
