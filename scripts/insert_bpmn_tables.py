#!/usr/bin/env python3
"""
insert_bpmn_tables.py - Generate XHTML process tables and insert into Confluence.

Reads BPMN process JSONs, applies audit fixes, generates styled XHTML tables,
and inserts them INLINE in appropriate document sections.

Mode:
  - Remove all drawio BPMN diagrams
  - Section 4 (TO-BE): only BPMN 0 overview table
  - Other tables: inserted at the end of their corresponding section (3.x)

Usage:
    python3 scripts/insert_bpmn_tables.py              # dry-run (saves to /tmp)
    python3 scripts/insert_bpmn_tables.py --publish     # publish to Confluence
"""

import json
import os
import re
import sys
import ssl
import urllib.request
import urllib.error
from collections import defaultdict, deque
from html import escape
from pathlib import Path
from copy import deepcopy

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
BPMN_DIR = BASE_DIR / "scripts" / "bpmn-processes"
ENV_FILE = BASE_DIR / ".env"
PAGE_ID = "83951683"

# --- Load .env ---
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
CONFLUENCE_URL = ENV.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_TOKEN = ENV.get("CONFLUENCE_TOKEN", "")

# --- BPMN number to section heading mapping ---
# Maps BPMN number to the h2 heading where its table will be inserted
# These are the actual h2 headings in the Confluence page (sections 3.x)
BPMN_HEADING = {
    0: "4. Общая схема процесса (TO-BE)",      # stays in section 4
    1: "3.5. Критерии срабатывания контроля",
    2: "3.4. Уровни согласования",
    3: "3.7. Экстренное согласование Заказа",
    4: "3.11. Жизненный цикл Заказа клиента и статусы",
    5: "3.12. Жизненный цикл локальной сметы",
    6: "3.11. Жизненный цикл Заказа клиента и статусы",  # WMS goes after order lifecycle
    7: "3.14. Возврат товара от клиента",
    8: "3.12. Жизненный цикл локальной сметы",   # LS closing goes with LS lifecycle
    9: "3.9. Фиксация НПСС",
    10: "3.13. Изменение локальной сметы после частичной отгрузки",
    11: "3.17. Обеспечение наличием и санкции за невыкуп",
    12: "3.18. Санкции за невыкуп ЛС (ЭТАП 2 - внедрение после 3 месяцев пилота)",
}

# Short names for cross-reference link text
BPMN_SHORT_NAME = {
    0: "Общая схема",
    1: "Контроль рентабельности",
    2: "Согласование рентабельности",
    3: "Экстренное согласование",
    4: "Жизненный цикл Заказа",
    5: "Жизненный цикл ЛС",
    6: "Интеграция с WMS",
    7: "Возврат товара",
    8: "Закрытие ЛС",
    9: "Контроль НПСС",
    10: "Изменение рентабельности ЛС",
    11: "Фиксация потребности",
    12: "Санкции за невыкуп",
}

# Insertion order within the same section (lower = first)
BPMN_INSERT_ORDER = {
    4: 1, 6: 2,   # in 3.11: order lifecycle first, then WMS
    5: 1, 8: 2,   # in 3.12: LS lifecycle first, then closing
}

# Map drawio diagramName to JSON filename
def diagram_to_json(diagram_name):
    """process-5-ls-lifecycle.drawio -> process-5-ls-lifecycle.json"""
    return diagram_name.replace(".drawio", ".json")

# --- Audit fixes (7 critical fixes from audit) ---
def apply_audit_fixes(proc):
    """Apply the 7 critical audit fixes to process data."""
    p = deepcopy(proc)
    name = p.get("name", "")

    # Extract BPMN number from diagramName or name
    bpmn_num = None
    dn = p.get("diagramName", "")
    m = re.search(r"BPMN\s+(\d+)", dn)
    if m:
        bpmn_num = int(m.group(1))
    elif "Контроль рентабельности" == p.get("name", "") and "BPMN:" in dn:
        bpmn_num = 1  # special case: process-1 has no number in diagramName

    if bpmn_num == 0:
        # FIX 1: sub_emergency orphan - add edge from x2
        if not any(e["to"] == "sub_emergency" for e in p["edges"]):
            p["edges"].append({"from": "x2", "to": "sub_emergency", "label": "срочная отгрузка"})
        # FIX 2: sub_return disconnected - add edges
        if not any(e["to"] == "sub_return" for e in p["edges"]):
            p["edges"].append({"from": "x3", "to": "sub_return", "label": "возврат"})
        if not any(e["from"] == "sub_return" for e in p["edges"]):
            p["edges"].append({"from": "sub_return", "to": "x3"})

    elif bpmn_num == 3:
        # FIX 3: t3 dead-end - add end event e1 and edge
        if not any(n["id"] == "e1" for n in p["nodes"]):
            p["nodes"].append({
                "id": "e1", "type": "eventEnd",
                "label": "Стандартное\nсогласование", "lane": "result"
            })
            # Add 'result' lane if missing
            if not any(l["id"] == "result" for l in p["lanes"]):
                p["lanes"].append({"id": "result", "name": "Результат", "color": "#f5f5f5"})
        if not any(e["from"] == "t3" for e in p["edges"]):
            p["edges"].append({"from": "t3", "to": "e1"})

    elif bpmn_num == 4:
        # FIX 4: s_cancel orphan - add edge from s_draft
        if not any(e["to"] == "s_cancel" for e in p["edges"]):
            p["edges"].append({"from": "s_draft", "to": "s_cancel", "label": "отмена"})

    elif bpmn_num == 7:
        # FIX 5: t_storno orphan - add edge from x_ls
        if not any(e["to"] == "t_storno" for e in p["edges"]):
            p["edges"].append({"from": "x_ls", "to": "t_storno", "label": "сторно (товар на складе)"})

    elif bpmn_num == 8:
        # FIX 6: t_rejected dead-end - add end event and edge
        if not any(n["id"] == "end_rejected" for n in p["nodes"]):
            p["nodes"].append({
                "id": "end_rejected", "type": "eventEnd",
                "label": "Закрытие\nотклонено", "lane": "system"
            })
        if not any(e["from"] == "t_rejected" for e in p["edges"]):
            p["edges"].append({"from": "t_rejected", "to": "end_rejected"})

    elif bpmn_num == 9:
        # FIX 7: t_dp_temp orphan - add edge from x_rbu
        if not any(e["to"] == "t_dp_temp" for e in p["edges"]):
            p["edges"].append({"from": "x_rbu", "to": "t_dp_temp", "label": "эскалация ДП"})

    return p


# --- Fix BPMN cross-references (old numbering in source JSONs) ---
# Maps process name fragments to correct BPMN numbers
# IMPORTANT: ordered from most specific to least specific to avoid false matches
NAME_TO_BPMN = [
    ("Контроль возраста НПСС", 9),
    ("Экстренное согласование", 3),
    ("Интеграция с WMS", 6),
    ("Возврат товар", 7),
    ("Закрытие ЛС", 8),
    ("Фиксация потребности", 11),
    ("Изменение плановой", 10),
    ("Контроль рентабельности", 1),
    ("Жизненный цикл ЛС", 5),
    ("Жизненный цикл Заказа", 4),
    ("Заказы клиента", 4),
    ("Санкци", 12),
    ("Согласование", 2),
    ("Стандартный процесс", 2),
    ("НПСС", 9),
]


def fix_bpmn_references(proc, all_processes):
    """Fix incorrect BPMN reference numbers in node labels.

    Some JSON source files use old numbering scheme. This function
    detects mismatches between the referenced BPMN number and the
    actual process name, and corrects them.
    """
    p = deepcopy(proc)

    # Build name -> correct BPMN number map from loaded processes
    name_to_num = {}
    for num, pr in all_processes.items():
        name_to_num[pr["name"]] = num

    for node in p["nodes"]:
        label = node.get("label", "")
        ref_match = re.search(r"BPMN\s+(\d+)", label)
        if not ref_match:
            continue

        old_num = int(ref_match.group(1))
        # Try to determine correct number from node label context
        clean = label.replace("\n", " ")

        correct_num = None
        # Match by process name fragments (ordered most specific first)
        for fragment, num in NAME_TO_BPMN:
            if fragment.lower() in clean.lower() and "см." in clean.lower():
                correct_num = num
                break

        if correct_num is not None and correct_num != old_num:
            new_label = label.replace(f"BPMN {old_num}", f"BPMN {correct_num}")
            node["label"] = new_label

    return p


# --- Topological sort ---
def topo_sort(nodes, edges):
    """Topological sort via BFS (Kahn's algorithm). Returns ordered node IDs."""
    node_ids = [n["id"] for n in nodes]
    node_set = set(node_ids)

    # Build adjacency + in-degree
    adj = defaultdict(list)
    in_deg = defaultdict(int)
    for nid in node_ids:
        in_deg[nid] = 0
    for e in edges:
        if e["from"] in node_set and e["to"] in node_set:
            # Skip back-edges (to node already seen as source)
            adj[e["from"]].append(e["to"])
            in_deg[e["to"]] += 1

    # Find start nodes (in-degree 0)
    queue = deque()
    for nid in node_ids:
        if in_deg[nid] == 0:
            queue.append(nid)

    result = []
    visited = set()
    while queue:
        nid = queue.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        result.append(nid)
        for neighbor in adj[nid]:
            in_deg[neighbor] -= 1
            if in_deg[neighbor] <= 0 and neighbor not in visited:
                queue.append(neighbor)

    # Append any remaining (orphan / cycle members)
    for nid in node_ids:
        if nid not in visited:
            result.append(nid)

    return result


# --- XHTML generation helpers ---
def clean_label(label):
    """Replace newlines with spaces."""
    return label.replace("\n", " ").strip() if label else ""


TYPE_CONFIG = {
    "eventStart":   {"icon": "\u25CB", "color": "Green",  "label": "Начало"},
    "eventEnd":     {"icon": "\u25CF", "color": "Green",  "label": "Конец"},
    "eventEndError":{"icon": "\u2716", "color": "Red",    "label": "Ошибка"},
    "task":         {"icon": "\u25A1", "color": "Blue",   "label": "Задача"},
    "taskError":    {"icon": "\u26A0", "color": "Red",    "label": "Ошибка"},
    "subprocess":   {"icon": "\u29C9", "color": "Yellow", "label": "Подпроцесс"},
    "gateway":      {"icon": "\u25C7", "color": "Yellow", "label": "Развилка"},
}

LANE_STYLES = {
    "#dae8fc": {"bg": "#eff6ff", "border": "#93c5fd", "text": "#1e40af"},   # blue (Manager)
    "#d5e8d4": {"bg": "#f0fdf4", "border": "#86efac", "text": "#166534"},   # green (System)
    "#ffe6cc": {"bg": "#fef3c7", "border": "#fcd34d", "text": "#92400e"},   # orange (Approver)
    "#f5f5f5": {"bg": "#f8fafc", "border": "#cbd5e1", "text": "#475569"},   # gray (Result)
}

def lane_style(color):
    return LANE_STYLES.get(color, LANE_STYLES["#f5f5f5"])


def status_macro(colour, title):
    """Generate Confluence status lozenge macro."""
    return (
        f'<ac:structured-macro ac:name="status" ac:schema-version="1">'
        f'<ac:parameter ac:name="colour">{colour}</ac:parameter>'
        f'<ac:parameter ac:name="title">{escape(title)}</ac:parameter>'
        f'</ac:structured-macro>'
    )


def anchor_link(anchor_name, text):
    """Generate Confluence same-page anchor link."""
    return (
        f'<ac:link ac:anchor="{escape(anchor_name)}">'
        f'<ac:plain-text-link-body><![CDATA[{text}]]></ac:plain-text-link-body>'
        f'</ac:link>'
    )


def condition_color(label):
    """Determine condition badge color based on label text."""
    if not label:
        return "Grey"
    l = label.lower()
    if re.search(r"^да$|одобр|полн|все отгруж|не ухудш|без изменен|актуальн|^отгрузить$|повышение|рту проведен|90-100|0-30|есть остаток|^согласован$|поступил|^100%$|остаток = 0", l):
        return "Green"
    if re.search(r"отклон|^нет$|отмен|блок|устарел|инцидент|> ?90|ухудш|истек|0 отгруз|аннул", l):
        return "Red"
    if re.search(r"частично|ожид|нет товар|вручную|снижен|закрыть|^0%$|продлить|таймаут|сторно|эскалац", l):
        return "Yellow"
    return "Grey"


def extract_bpmn_ref(label):
    """Extract BPMN reference number from label like 'см. BPMN 7'."""
    if not label:
        return None
    m = re.search(r"(?:BPMN|bpmn)\s*(\d+)", label)
    return int(m.group(1)) if m else None


def generate_process_table(proc):
    """Generate XHTML table for a process."""
    nodes = proc["nodes"]
    edges = proc["edges"]
    lanes = {l["id"]: l for l in proc["lanes"]}

    # Build node lookup
    node_map = {n["id"]: n for n in nodes}

    # Build outgoing edges map
    outgoing = defaultdict(list)
    for e in edges:
        outgoing[e["from"]].append(e)

    # Topological sort
    order = topo_sort(nodes, edges)

    # Extract BPMN number (not used in table generation but kept for reference)

    # Header row
    html = '<table class="confluenceTable" style="width: 100%;">\n<tbody>\n'
    html += '<tr>\n'
    html += '<th class="confluenceTh" style="background-color: rgb(59,115,175); color: white; width: 30px; text-align: center;">#</th>\n'
    html += '<th class="confluenceTh" style="background-color: rgb(59,115,175); color: white; width: 90px;">Тип</th>\n'
    html += '<th class="confluenceTh" style="background-color: rgb(59,115,175); color: white;">Элемент</th>\n'
    html += '<th class="confluenceTh" style="background-color: rgb(59,115,175); color: white; width: 160px;">Дорожка</th>\n'
    html += '<th class="confluenceTh" style="background-color: rgb(59,115,175); color: white;">Переходы</th>\n'
    html += '</tr>\n'

    # Data rows
    for idx, nid in enumerate(order, 1):
        node = node_map.get(nid)
        if not node:
            continue

        ntype = node.get("type", "task")
        label = clean_label(node.get("label", ""))
        lane_id = node.get("lane", "")
        lane = lanes.get(lane_id, {"name": lane_id, "color": "#f5f5f5"})
        lane_name = lane.get("name", lane_id).replace("\n", " ")
        lane_color = lane.get("color", "#f5f5f5")

        tc = TYPE_CONFIG.get(ntype, TYPE_CONFIG["task"])
        ls = lane_style(lane_color)

        # Type cell: status lozenge
        type_cell = status_macro(tc["color"], f'{tc["icon"]} {tc["label"]}')

        # Element cell: label with subprocess link
        element_cell = escape(label)
        bpmn_ref = extract_bpmn_ref(node.get("label", ""))
        if bpmn_ref is not None and bpmn_ref in BPMN_HEADING:
            heading = BPMN_HEADING[bpmn_ref]
            short = BPMN_SHORT_NAME.get(bpmn_ref, heading)
            element_cell += '<br/>' + anchor_link(heading, f"\u2192 см. {short}")

        # Lane cell: colored badge
        lane_cell = (
            f'<span style="background-color: {ls["bg"]}; '
            f'border: 1px solid {ls["border"]}; '
            f'color: {ls["text"]}; '
            f'padding: 2px 8px; border-radius: 4px; font-size: 12px;">'
            f'{escape(lane_name)}</span>'
        )

        # Transitions cell
        trans_parts = []
        for e in outgoing.get(nid, []):
            target = node_map.get(e["to"])
            if not target:
                continue
            target_label = clean_label(target.get("label", ""))
            cond_label = e.get("label", "")

            part = "\u2192 "

            # Condition badge
            if cond_label:
                cc = condition_color(cond_label)
                part += status_macro(cc, escape(cond_label)) + " "

            # Target: check if it references another BPMN
            target_ref = extract_bpmn_ref(target.get("label", ""))
            if target_ref is not None and target_ref in BPMN_HEADING:
                heading = BPMN_HEADING[target_ref]
                short = BPMN_SHORT_NAME.get(target_ref, heading)
                part += anchor_link(heading, target_label if target_label else short)
            else:
                part += f'<strong>{escape(target_label)}</strong>' if target_label else f'<em>{escape(e["to"])}</em>'

            trans_parts.append(part)

        transitions_cell = "<br/>".join(trans_parts) if trans_parts else '<span style="color: #999;">\u2014</span>'

        # Row with left border color by type
        border_colors = {
            "eventStart": "#22c55e",
            "eventEnd": "#22c55e",
            "eventEndError": "#ef4444",
            "task": "#3b82f6",
            "taskError": "#ef4444",
            "subprocess": "#a855f7",
            "gateway": "#f59e0b",
        }
        border_color = border_colors.get(ntype, "#94a3b8")

        html += f'<tr>\n'
        html += f'<td class="confluenceTd" style="text-align: center; border-left: 4px solid {border_color}; font-weight: bold; color: #64748b;">{idx}</td>\n'
        html += f'<td class="confluenceTd" style="text-align: center;">{type_cell}</td>\n'
        html += f'<td class="confluenceTd">{element_cell}</td>\n'
        html += f'<td class="confluenceTd" style="text-align: center;">{lane_cell}</td>\n'
        html += f'<td class="confluenceTd">{transitions_cell}</td>\n'
        html += '</tr>\n'

    html += '</tbody>\n</table>\n'

    # Notes section
    notes = proc.get("notes", [])
    if notes:
        notes_text = "; ".join(n.get("text", "").replace("\n", " ") for n in notes)
        html += (
            '<ac:structured-macro ac:name="info" ac:schema-version="1">'
            '<ac:rich-text-body>'
            f'<p><strong>Примечание:</strong> {escape(notes_text)}</p>'
            '</ac:rich-text-body>'
            '</ac:structured-macro>\n'
        )

    # Lanes legend (compact)
    html += '<p style="margin-top: 8px; font-size: 12px; color: #64748b;"><strong>Дорожки:</strong> '
    lane_parts = []
    for l in proc["lanes"]:
        ls = lane_style(l.get("color", "#f5f5f5"))
        lname = l.get("name", l["id"]).replace("\n", " ")
        lane_parts.append(
            f'<span style="background-color: {ls["bg"]}; border: 1px solid {ls["border"]}; '
            f'color: {ls["text"]}; padding: 1px 6px; border-radius: 3px; font-size: 11px;">'
            f'{escape(lname)}</span>'
        )
    html += " ".join(lane_parts)
    html += '</p>\n'

    return html


def wrap_in_expand(bpmn_num, proc_name, content):
    """Wrap content in a Confluence expand (collapsible) macro."""
    import uuid
    macro_id = str(uuid.uuid4())
    title = f"Схема процесса: {proc_name}"
    return (
        f'<ac:structured-macro ac:name="expand" ac:schema-version="1" '
        f'ac:macro-id="{macro_id}">'
        f'<ac:parameter ac:name="title">{escape(title)}</ac:parameter>'
        f'<ac:rich-text-body>\n{content}\n</ac:rich-text-body>'
        f'</ac:structured-macro>\n'
    )


# --- Confluence API ---
def confluence_get(page_id):
    """GET page from Confluence."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=body.storage,version"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        "Accept": "application/json",
    })
    resp = urllib.request.urlopen(req, context=ssl_ctx)
    return json.loads(resp.read().decode("utf-8"))


def confluence_put(page_id, title, body, version, message=""):
    """PUT updated page to Confluence."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {
            "number": version + 1,
            "message": message,
        },
        "body": {
            "storage": {
                "value": body,
                "representation": "storage",
            }
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP Error {e.code}: {error_body[:1000]}")
        raise


# --- Main ---
def load_processes():
    """Load all process JSONs, apply audit fixes and cross-reference corrections."""
    print("Loading process JSONs...")
    processes = {}
    for json_file in sorted(BPMN_DIR.glob("process-*.json")):
        with open(json_file) as f:
            proc = json.load(f)
        bpmn_num = None
        m = re.search(r"BPMN\s+(\d+)", proc.get("diagramName", ""))
        if m:
            bpmn_num = int(m.group(1))
        else:
            fm = re.search(r"process-(\d+)", json_file.stem)
            if fm:
                bpmn_num = int(fm.group(1))
        if bpmn_num is not None:
            proc = apply_audit_fixes(proc)
            processes[bpmn_num] = proc
            print(f"  BPMN {bpmn_num}: {proc['name']} ({len(proc['nodes'])} nodes, {len(proc['edges'])} edges)")

    print(f"\nLoaded {len(processes)} processes")

    # Fix cross-references
    print("\nFixing cross-references...")
    for bpmn_num in list(processes.keys()):
        fixed = fix_bpmn_references(processes[bpmn_num], processes)
        for old_node, new_node in zip(processes[bpmn_num]["nodes"], fixed["nodes"]):
            if old_node.get("label") != new_node.get("label"):
                old_ref = re.search(r"BPMN\s+(\d+)", old_node["label"])
                new_ref = re.search(r"BPMN\s+(\d+)", new_node["label"])
                if old_ref and new_ref:
                    print(f"  BPMN {bpmn_num} node {old_node['id']}: BPMN {old_ref.group(1)} -> BPMN {new_ref.group(1)}")
        processes[bpmn_num] = fixed

    return processes


def find_headings(body):
    """Find all h1 and h2 headings with positions."""
    headings = []
    for m in re.finditer(r'<h([12])>(.*?)</h\1>', body, re.DOTALL):
        level = int(m.group(1))
        raw_text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        headings.append({
            "level": level,
            "text": raw_text,
            "start": m.start(),
            "end": m.end(),
        })
    return headings


def main():
    publish = "--publish" in sys.argv

    # 1. Load processes
    processes = load_processes()

    # 2. Generate XHTML tables
    print("\nGenerating XHTML tables...")
    tables = {}
    for bpmn_num, proc in processes.items():
        table_html = generate_process_table(proc)
        if bpmn_num == 0:
            # Overview table: NOT wrapped in expand (directly visible in TO-BE)
            tables[bpmn_num] = table_html
        else:
            # Section tables: wrapped in expand macro
            tables[bpmn_num] = wrap_in_expand(bpmn_num, proc["name"], table_html)
        print(f"  BPMN {bpmn_num}: {len(tables[bpmn_num])} chars")

    # 3. Get current Confluence page
    print("\nFetching Confluence page...")
    page = confluence_get(PAGE_ID)
    title = page["title"]
    version = page["version"]["number"]
    body = page["body"]["storage"]["value"]
    print(f"  Title: {title}, Version: {version}, Body: {len(body)} chars")

    # 4. Clean up: remove ALL drawio macros
    print("\nRemoving drawio macros...")
    drawio_pattern = re.compile(
        r'\s*<ac:structured-macro[^>]*ac:name="drawio"[^>]*>.*?</ac:structured-macro>\s*',
        re.DOTALL
    )
    body = drawio_pattern.sub('\n', body)
    print(f"  After drawio removal: {len(body)} chars")

    # 5. Clean up: remove old expand macros with process tables
    # Use nesting-aware approach: count open/close structured-macro tags
    def find_expand_macros(body):
        """Find expand macros with correct nesting (handles nested status/info macros)."""
        OPEN_TAG = '<ac:structured-macro'
        CLOSE_TAG = '</ac:structured-macro>'
        results = []
        pos = 0
        while True:
            # Find next expand macro opening
            idx = body.find(OPEN_TAG, pos)
            if idx == -1:
                break
            # Check if it's an expand macro
            tag_end = body.find('>', idx)
            if tag_end == -1:
                break
            tag = body[idx:tag_end + 1]
            if 'ac:name="expand"' not in tag:
                pos = tag_end + 1
                continue
            # Found an expand macro - now find its matching close tag
            depth = 1
            search_pos = tag_end + 1
            while depth > 0 and search_pos < len(body):
                next_open = body.find(OPEN_TAG, search_pos)
                next_close = body.find(CLOSE_TAG, search_pos)
                if next_close == -1:
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    search_pos = next_open + len(OPEN_TAG)
                else:
                    depth -= 1
                    if depth == 0:
                        end = next_close + len(CLOSE_TAG)
                        full_macro = body[idx:end]
                        # Extract title
                        title_m = re.search(r'<ac:parameter ac:name="title">(.*?)</ac:parameter>', full_macro)
                        title = title_m.group(1) if title_m else ""
                        results.append({"start": idx, "end": end, "title": title})
                    search_pos = next_close + len(CLOSE_TAG)
            pos = tag_end + 1
        return results

    def remove_expand_by_title(body, title_patterns):
        """Remove expand macros whose title matches any of the patterns."""
        macros = find_expand_macros(body)
        # Process in reverse to maintain positions
        for m in reversed(macros):
            if any(pat in m["title"] for pat in title_patterns):
                start = m["start"]
                end = m["end"]
                # Eat trailing whitespace/newlines
                while end < len(body) and body[end] in ' \t\n\r':
                    end += 1
                body = body[:start] + '\n' + body[end:]
        return body

    body = remove_expand_by_title(body, ["Табличное описание", "Схема процесса", "Легенда"])
    print(f"  After old table cleanup: {len(body)} chars")

    # 6. Replace section 4 (TO-BE): remove all sub-headings and content,
    #    keep only the h1, add overview description + BPMN 0 table
    print("\nRestructuring section 4 (TO-BE)...")
    headings = find_headings(body)

    # Find section 4 h1 and section 5 h1
    sec4_start = None
    sec5_start = None
    for h in headings:
        if h["level"] == 1 and "4." in h["text"] and "TO-BE" in h["text"]:
            sec4_start = h
        elif h["level"] == 1 and "5." in h["text"] and sec4_start:
            sec5_start = h
            break

    if sec4_start and sec5_start:
        # Content between end of h1 tag and start of section 5
        before_sec4 = body[:sec4_start["end"]]
        after_sec4 = body[sec5_start["start"]:]

        # New section 4 content: description + BPMN 0 overview table
        new_sec4 = '\n<p>Общая схема бизнес-процесса контроля рентабельности. Детальные процессы описаны в соответствующих разделах документа.</p>\n'
        new_sec4 += tables[0]  # BPMN 0 overview (not in expand)
        new_sec4 += '\n'

        body = before_sec4 + new_sec4 + after_sec4
        print(f"  Section 4 replaced. Body: {len(body)} chars")
    else:
        print("  WARNING: Could not find section 4 boundaries!")

    # 7. Insert process tables inline at end of corresponding sections
    print("\nInserting tables inline in sections...")

    # Group tables by target section heading
    section_tables = defaultdict(list)
    for bpmn_num in sorted(processes.keys()):
        if bpmn_num == 0:
            continue  # already handled in section 4
        target_heading = BPMN_HEADING.get(bpmn_num)
        if not target_heading:
            print(f"  WARNING: No target section for BPMN {bpmn_num}")
            continue
        order = BPMN_INSERT_ORDER.get(bpmn_num, 5)  # default order 5
        section_tables[target_heading].append((order, bpmn_num))

    # Sort tables within each section by order
    for heading in section_tables:
        section_tables[heading].sort()

    # Find insertion points (just before the next heading starts)
    headings = find_headings(body)  # re-parse after section 4 changes
    inserted = 0

    # Build list of (insert_position, html) tuples
    insertions = []
    for target_heading, bpmn_list in section_tables.items():
        # Find matching heading
        target_h = None
        for h in headings:
            if h["text"] == target_heading:
                target_h = h
                break

        if not target_h:
            print(f"  WARNING: Heading '{target_heading}' not found!")
            continue

        # Find the next heading at same or higher level
        next_h_start = len(body)
        for h in headings:
            if h["start"] > target_h["start"] and h["level"] <= target_h["level"]:
                next_h_start = h["start"]
                break
            # For h2 targets, also stop at next h1
            if h["start"] > target_h["start"] and h["level"] == 1:
                next_h_start = h["start"]
                break

        # Build combined table HTML for this section
        combined = ""
        for order, bpmn_num in bpmn_list:
            combined += tables[bpmn_num]
            print(f"  BPMN {bpmn_num} ({processes[bpmn_num]['name']}) -> {target_heading}")
            inserted += 1

        insertions.append((next_h_start, combined))

    # Apply insertions from bottom to top (to preserve positions)
    insertions.sort(key=lambda x: x[0], reverse=True)
    for pos, html in insertions:
        body = body[:pos] + html + body[pos:]

    print(f"\nInserted {inserted} tables. Final body: {len(body)} chars")

    # 8. Save to file for review
    output_file = Path("/tmp/confluence_body_with_tables.html")
    output_file.write_text(body, encoding="utf-8")
    print(f"\nSaved to {output_file}")

    # 9. Publish to Confluence if requested
    if publish:
        print("\nPublishing to Confluence...")
        msg = "Реструктуризация: BPMN-таблицы инлайн в разделах 3.x, обзорная схема в секции 4, drawio удалены"
        result = confluence_put(PAGE_ID, title, body, version, msg)
        new_version = result["version"]["number"]
        print(f"  Published! New version: {new_version}")
        print(f"  URL: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
    else:
        print("\nDry run mode. Use --publish to update Confluence.")
        print(f"Review the output at: {output_file}")


if __name__ == "__main__":
    main()
