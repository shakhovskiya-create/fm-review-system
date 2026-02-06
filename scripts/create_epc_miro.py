#!/usr/bin/env python3
"""
ePC Diagram Creator for FM-LS-PROFIT in Miro
Creates 3 Event-driven Process Chain diagrams via Miro REST API v2

Diagram 1: Основной поток контроля рентабельности
Diagram 2: Процесс согласования (РБЮ/ДП/ГД + SLA + эскалация)
Diagram 3: Экстренное согласование

Board: fm-review-system (uXjVGFq_knA=)
"""

import requests
import json
import time
import sys
import os

# === CONFIG ===
# Set MIRO_TOKEN environment variable before running
MIRO_TOKEN = os.environ.get("MIRO_TOKEN", "")
BOARD_ID = os.environ.get("MIRO_BOARD_ID", "uXjVGFq_knA=")

if not MIRO_TOKEN:
    print("ERROR: MIRO_TOKEN environment variable not set")
    print("Run: export MIRO_TOKEN='your-miro-token-here'")
    sys.exit(1)

BASE_URL = f"https://api.miro.com/v2/boards/{BOARD_ID}"
HEADERS = {
    "Authorization": f"Bearer {MIRO_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# === EKF COLOR SCHEME (from AGENT_8) ===
C = {
    "start":    "#C8E6C9",  # Green - start event
    "mid":      "#FFE0B2",  # Orange - intermediate event
    "end":      "#FFCDD2",  # Red - end event
    "fn":       "#B2EBF2",  # Teal - function
    "xor":      "#FFF9C4",  # Yellow - XOR
    "and":      "#E1BEE7",  # Purple - AND
    "org":      "#FFECB3",  # Yellow - org unit
    "doc":      "#BBDEFB",  # Blue - document
    "sys":      "#E0E0E0",  # Grey - IT system
    "ref":      "#D1C4E9",  # Light purple - reference to other diagram
}

# Layout
VS = 200   # vertical step
HS = 380   # horizontal offset for branches

# Track created items per diagram
items = {}
stats = {"shapes": 0, "connectors": 0, "texts": 0, "frames": 0}


def shape(name, stype, text, x, y, w=220, h=100, color="#FFF",
          border="#333333", fs="14", bw="2"):
    """Create a shape."""
    payload = {
        "data": {"shape": stype, "content": f"<p>{text}</p>"},
        "style": {
            "fillColor": color, "fontFamily": "arial", "fontSize": fs,
            "textAlign": "center", "textAlignVertical": "middle",
            "borderColor": border, "borderWidth": bw, "fillOpacity": "1.0"
        },
        "geometry": {"width": w, "height": h},
        "position": {"x": x, "y": y}
    }
    r = requests.post(f"{BASE_URL}/shapes", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        iid = r.json()["id"]
        items[name] = iid
        stats["shapes"] += 1
        return iid
    else:
        print(f"  ! ERR {name}: {r.status_code} {r.text[:150]}")
        return None


def conn(a, b, label=None):
    """Create a connector."""
    aid, bid = items.get(a), items.get(b)
    if not aid or not bid:
        return None
    payload = {
        "startItem": {"id": aid}, "endItem": {"id": bid},
        "style": {"strokeColor": "#333333", "strokeWidth": "2",
                  "startStrokeCap": "none", "endStrokeCap": "stealth"},
        "shape": "elbowed"
    }
    if label:
        payload["captions"] = [{"content": label, "textAlignVertical": "bottom"}]
    r = requests.post(f"{BASE_URL}/connectors", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        stats["connectors"] += 1
        return r.json()["id"]
    else:
        print(f"  ! ERR conn {a}->{b}: {r.status_code} {r.text[:120]}")
        return None


def text(content, x, y, w=400, fs="24"):
    """Create a text block."""
    payload = {
        "data": {"content": f"<p><b>{content}</b></p>"},
        "position": {"x": x, "y": y},
        "geometry": {"width": w}
    }
    r = requests.post(f"{BASE_URL}/texts", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        tid = r.json()["id"]
        # Style it
        requests.patch(f"{BASE_URL}/texts/{tid}", headers=HEADERS,
                       json={"style": {"fontSize": fs, "textAlign": "center"}})
        stats["texts"] += 1
        return tid
    return None


def frame(title, x, y, w, h):
    """Create a frame."""
    payload = {
        "data": {"title": title, "type": "freeform"},
        "style": {"fillColor": "#f5f5f5"},
        "geometry": {"width": w, "height": h},
        "position": {"x": x, "y": y}
    }
    r = requests.post(f"{BASE_URL}/frames", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        stats["frames"] += 1
        return r.json()["id"]
    else:
        print(f"  ! ERR frame: {r.status_code} {r.text[:150]}")
        return None


# Shortcuts
def event(name, txt, x, y, color, w=220, h=100):
    return shape(name, "hexagon", txt, x, y, w, h, color, fs="13")

def func(name, txt, x, y, w=240, h=90):
    return shape(name, "round_rectangle", txt, x, y, w, h, C["fn"], fs="13")

def xor(name, x, y):
    return shape(name, "rhombus", "XOR", x, y, 70, 70, C["xor"], fs="12", bw="3")

def org(name, txt, x, y):
    return shape(name, "circle", txt, x, y, 110, 55, C["org"], fs="11")

def sys_(name, txt, x, y):
    return shape(name, "rectangle", txt, x, y, 100, 45, C["sys"], fs="11")

def doc(name, txt, x, y):
    return shape(name, "rectangle", txt, x, y, 160, 55, C["doc"], fs="11")

def ref(name, txt, x, y, w=220, h=80):
    """Reference to another diagram (dashed purple box)."""
    return shape(name, "round_rectangle", txt, x, y, w, h, C["ref"],
                 border="#7E57C2", fs="12", bw="3")


# ============================================================
# DIAGRAM 1: Основной поток контроля рентабельности
# ============================================================
def diagram_1(ox=0, oy=0):
    """Main flow: Order -> Calculate -> Auto/Manual -> Ship."""
    cx = ox  # center x
    y = oy

    print("\n[D1] Основной поток контроля рентабельности")

    # Frame
    frame("1. Основной поток контроля рентабельности", ox, oy + 1200, 1400, 2700)

    # Title
    text("1. Основной поток контроля\nрентабельности", cx, y - 60, w=500, fs="20")

    # --- Start ---
    y += 80
    event("d1_start", "Заказ клиента\nсоздан", cx, y, C["start"])

    # --- Check NPSS ---
    y += VS
    func("d1_fn_check_npss", "Проверить наличие\nНПСС по позициям", cx, y)
    sys_("d1_sys_1c_1", "1С:УТ", cx + 260, y)

    y += VS
    event("d1_ev_npss_checked", "НПСС\nпроверена", cx, y, C["mid"])

    y += VS
    xor("d1_xor_npss", cx, y)

    # --- Left: NPSS=0 -> Block ---
    lx = cx - HS
    yl = y + VS
    event("d1_ev_npss_zero", "НПСС = 0\nили NULL", lx, yl, C["end"], w=180, h=80)

    yl += VS
    func("d1_fn_block_npss", "Блокировать позицию\nУведомить финслужбу", lx, yl, w=220, h=80)
    org("d1_org_fin", "Финслужба", lx - 250, yl)

    yl += VS
    event("d1_ev_npss_blocked", "Позиция\nзаблокирована\n(SLA 24ч)", lx, yl, C["end"], w=200, h=100)

    # --- Right: NPSS OK -> Calculate ---
    rx = cx + HS
    yr = y + VS
    event("d1_ev_npss_ok", "НПСС\nактуальна", rx, yr, C["mid"], w=180, h=80)

    yr += VS
    func("d1_fn_calc", "Рассчитать\nрентабельность\nЗаказа", rx, yr, w=240, h=90)
    org("d1_org_mgr", "Менеджер", rx - 270, yr)
    sys_("d1_sys_1c_2", "1С:УТ", rx + 260, yr)

    yr += VS
    event("d1_ev_calc_done", "Рентабельность\nрассчитана", rx, yr, C["mid"])

    yr += VS
    func("d1_fn_check_dev", "Проверить отклонение\nот плановой рент. ЛС", rx, yr, w=260, h=80)

    yr += VS
    event("d1_ev_dev_checked", "Отклонение\nопределено", rx, yr, C["mid"])

    # --- XOR: Deviation ---
    yr += VS
    xor("d1_xor_dev", rx, yr)

    # Left: < 1 p.p. -> Auto
    auto_x = rx - HS
    ya = yr + VS
    event("d1_ev_ok", "Отклонение\n< 1 п.п.", auto_x, ya, C["mid"], w=180, h=80)

    ya += VS
    func("d1_fn_auto", "Автосогласование\nЗаказа", auto_x, ya, w=200, h=70)
    sys_("d1_sys_auto", "1С:УТ (авто)", auto_x - 230, ya)

    ya += VS
    event("d1_ev_auto_ok", "Заказ\nавтосогласован", auto_x, ya, C["start"], w=200, h=80)

    # Right: >= 1 p.p. -> Manual (reference to D2)
    man_x = rx + HS
    ym = yr + VS
    event("d1_ev_dev", "Отклонение\n>= 1 п.п.", man_x, ym, C["mid"], w=180, h=80)

    ym += VS
    ref("d1_ref_d2", ">> Диаграмма 2:\nПроцесс\nсогласования", man_x, ym, w=220, h=90)

    ym += VS
    xor("d1_xor_d2_result", man_x, ym)

    # Result branches from D2
    ym_ok = ym + VS
    event("d1_ev_d2_ok", "Заказ\nодобрен", man_x - 180, ym_ok, C["start"], w=160, h=70)
    event("d1_ev_d2_no", "Заказ\nотклонен", man_x + 180, ym_ok, C["end"], w=160, h=70)

    ym_ret = ym_ok + VS
    func("d1_fn_return", "Вернуть менеджеру\nна корректировку", man_x + 180, ym_ret, w=210, h=80)

    ym_end_no = ym_ret + VS
    event("d1_ev_end_no", "Процесс\nзавершен\n(отказ)", man_x + 180, ym_end_no, C["end"], w=180, h=90)

    # --- Main join ---
    join_y = max(ya, ym_ok) + VS
    xor("d1_xor_join", cx, join_y)

    # --- Final flow ---
    y2 = join_y + VS
    event("d1_ev_agreed", "Заказ\nсогласован", cx, y2, C["start"])

    y2 += VS
    func("d1_fn_reserve", "Зарезервировать\nтовар", cx, y2, w=220, h=70)
    sys_("d1_sys_reserve", "1С:УТ", cx + 250, y2)

    y2 += VS
    event("d1_ev_reserved", "Товар\nзарезервирован", cx, y2, C["mid"])

    y2 += VS
    func("d1_fn_ship", "Передать заказ\nна склад", cx, y2, w=220, h=70)
    org("d1_org_ship", "Менеджер", cx - 250, y2)

    y2 += VS
    event("d1_ev_end", "Заказ передан\nна склад", cx, y2, C["end"])

    # --- Connectors ---
    print("  [connectors]")
    conn("d1_start", "d1_fn_check_npss")
    conn("d1_sys_1c_1", "d1_fn_check_npss")
    conn("d1_fn_check_npss", "d1_ev_npss_checked")
    conn("d1_ev_npss_checked", "d1_xor_npss")

    conn("d1_xor_npss", "d1_ev_npss_zero", "НПСС = 0")
    conn("d1_xor_npss", "d1_ev_npss_ok", "НПСС ОК")
    conn("d1_ev_npss_zero", "d1_fn_block_npss")
    conn("d1_org_fin", "d1_fn_block_npss")
    conn("d1_fn_block_npss", "d1_ev_npss_blocked")

    conn("d1_ev_npss_ok", "d1_fn_calc")
    conn("d1_org_mgr", "d1_fn_calc")
    conn("d1_sys_1c_2", "d1_fn_calc")
    conn("d1_fn_calc", "d1_ev_calc_done")
    conn("d1_ev_calc_done", "d1_fn_check_dev")
    conn("d1_fn_check_dev", "d1_ev_dev_checked")
    conn("d1_ev_dev_checked", "d1_xor_dev")

    conn("d1_xor_dev", "d1_ev_ok", "< 1 п.п.")
    conn("d1_xor_dev", "d1_ev_dev", ">= 1 п.п.")

    conn("d1_ev_ok", "d1_fn_auto")
    conn("d1_sys_auto", "d1_fn_auto")
    conn("d1_fn_auto", "d1_ev_auto_ok")
    conn("d1_ev_auto_ok", "d1_xor_join")

    conn("d1_ev_dev", "d1_ref_d2")
    conn("d1_ref_d2", "d1_xor_d2_result")
    conn("d1_xor_d2_result", "d1_ev_d2_ok", "Одобрено")
    conn("d1_xor_d2_result", "d1_ev_d2_no", "Отклонено")
    conn("d1_ev_d2_no", "d1_fn_return")
    conn("d1_fn_return", "d1_ev_end_no")
    conn("d1_ev_d2_ok", "d1_xor_join")

    conn("d1_xor_join", "d1_ev_agreed")
    conn("d1_ev_agreed", "d1_fn_reserve")
    conn("d1_sys_reserve", "d1_fn_reserve")
    conn("d1_fn_reserve", "d1_ev_reserved")
    conn("d1_ev_reserved", "d1_fn_ship")
    conn("d1_org_ship", "d1_fn_ship")
    conn("d1_fn_ship", "d1_ev_end")


# ============================================================
# DIAGRAM 2: Процесс согласования
# ============================================================
def diagram_2(ox=2000, oy=0):
    """Approval: Determine level -> RBU/DP/GD -> SLA -> Escalation -> Decision."""
    cx = ox
    y = oy

    print("\n[D2] Процесс согласования")

    frame("2. Процесс согласования", ox, oy + 1050, 1500, 2400)

    text("2. Процесс согласования\n(РБЮ / ДП / ГД)", cx, y - 60, w=450, fs="20")

    # --- Start ---
    y += 80
    event("d2_start", "Отклонение\nобнаружено\n(>= 1 п.п.)", cx, y, C["mid"], w=220, h=100)

    y += VS
    func("d2_fn_level", "Определить уровень\nсогласования", cx, y, w=240, h=80)
    sys_("d2_sys_do", "1С:ДО", cx + 260, y)

    y += VS
    event("d2_ev_level", "Уровень\nопределен", cx, y, C["mid"])

    # --- XOR: By level ---
    y += VS
    xor("d2_xor_level", cx, y)

    x_rbu = cx - HS
    x_dp = cx
    x_gd = cx + HS

    ya = y + VS

    # РБЮ
    func("d2_fn_rbu", "Согласование\nРБЮ", x_rbu, ya, w=200, h=70)
    org("d2_org_rbu", "РБЮ", x_rbu, ya - 80)
    shape("d2_sla_rbu", "rectangle", "SLA: 4ч", x_rbu - 200, ya, 90, 35, "#FFFFFF", fs="10")

    # ДП
    func("d2_fn_dp", "Согласование\nДП", x_dp, ya, w=200, h=70)
    org("d2_org_dp", "ДП", x_dp, ya - 80)
    shape("d2_sla_dp", "rectangle", "SLA: 8ч", x_dp - 200, ya, 90, 35, "#FFFFFF", fs="10")

    # ГД
    func("d2_fn_gd", "Согласование\nГД", x_gd, ya, w=200, h=70)
    org("d2_org_gd", "ГД", x_gd, ya - 80)
    shape("d2_sla_gd", "rectangle", "SLA: 24ч", x_gd + 200, ya, 90, 35, "#FFFFFF", fs="10")

    # --- XOR Join ---
    ya += VS
    xor("d2_xor_join_level", cx, ya)

    ya += VS
    event("d2_ev_waiting", "Ожидание\nрешения", cx, ya, C["mid"])

    # --- XOR: Timeout? ---
    ya += VS
    xor("d2_xor_timeout", cx, ya)

    # Timeout branch (right)
    esc_x = cx + HS
    yt = ya + VS
    event("d2_ev_timeout", "SLA\nпревышен", esc_x, yt, C["end"], w=160, h=70)

    yt += VS
    func("d2_fn_escalate", "Автоэскалация\nна вышестоящего", esc_x, yt, w=220, h=80)
    sys_("d2_sys_esc", "1С:ДО (авто)", esc_x + 250, yt)

    yt += VS
    event("d2_ev_escalated", "Задача\nэскалирована", esc_x, yt, C["mid"], w=180, h=70)

    # Decision received (left / center)
    dec_x = cx - HS // 2
    yd = ya + VS
    event("d2_ev_decided", "Решение\nпринято", dec_x, yd, C["mid"])

    # --- XOR: Result ---
    yd += VS
    xor("d2_xor_result", dec_x, yd)

    yr = yd + VS
    event("d2_ev_ok", "Заказ\nодобрен", dec_x - 200, yr, C["start"], w=160, h=70)
    event("d2_ev_no", "Заказ\nотклонен", dec_x + 200, yr, C["end"], w=160, h=70)

    # Approved -> details
    yr2 = yr + VS
    func("d2_fn_notify_ok", "Уведомить менеджера\n(push + email)", dec_x - 200, yr2, w=220, h=70)

    yr2 += VS
    event("d2_ev_end_ok", "Согласование\nзавершено\n(одобрено)", dec_x - 200, yr2, C["start"], w=200, h=90)

    # Rejected -> details
    yr3 = yr + VS
    func("d2_fn_notify_no", "Уведомить менеджера\n(причина отказа)", dec_x + 200, yr3, w=220, h=70)

    yr3 += VS
    event("d2_ev_end_no", "Согласование\nзавершено\n(отклонено)", dec_x + 200, yr3, C["end"], w=200, h=90)

    # --- ГД special: auto-reject 48h ---
    gd_x = cx + HS + 200
    ygd = yt + VS
    event("d2_ev_gd_48", "ГД: 48ч\nбез ответа", gd_x, ygd, C["end"], w=160, h=70)

    ygd += VS
    func("d2_fn_auto_reject", "Автоматический\nотказ", gd_x, ygd, w=180, h=70)
    sys_("d2_sys_gd_auto", "1С:ДО (авто)", gd_x + 220, ygd)

    # --- Connectors ---
    print("  [connectors]")
    conn("d2_start", "d2_fn_level")
    conn("d2_sys_do", "d2_fn_level")
    conn("d2_fn_level", "d2_ev_level")
    conn("d2_ev_level", "d2_xor_level")

    conn("d2_xor_level", "d2_fn_rbu", "1-15 п.п.")
    conn("d2_xor_level", "d2_fn_dp", "15-25 п.п.")
    conn("d2_xor_level", "d2_fn_gd", "> 25 п.п.")

    conn("d2_org_rbu", "d2_fn_rbu")
    conn("d2_org_dp", "d2_fn_dp")
    conn("d2_org_gd", "d2_fn_gd")
    conn("d2_sla_rbu", "d2_fn_rbu")
    conn("d2_sla_dp", "d2_fn_dp")
    conn("d2_sla_gd", "d2_fn_gd")

    conn("d2_fn_rbu", "d2_xor_join_level")
    conn("d2_fn_dp", "d2_xor_join_level")
    conn("d2_fn_gd", "d2_xor_join_level")

    conn("d2_xor_join_level", "d2_ev_waiting")
    conn("d2_ev_waiting", "d2_xor_timeout")

    conn("d2_xor_timeout", "d2_ev_decided", "Решение")
    conn("d2_xor_timeout", "d2_ev_timeout", "Таймаут")

    conn("d2_ev_timeout", "d2_fn_escalate")
    conn("d2_sys_esc", "d2_fn_escalate")
    conn("d2_fn_escalate", "d2_ev_escalated")
    conn("d2_ev_escalated", "d2_ev_waiting")  # loop back

    conn("d2_ev_decided", "d2_xor_result")
    conn("d2_xor_result", "d2_ev_ok", "Одобрено")
    conn("d2_xor_result", "d2_ev_no", "Отклонено")

    conn("d2_ev_ok", "d2_fn_notify_ok")
    conn("d2_fn_notify_ok", "d2_ev_end_ok")

    conn("d2_ev_no", "d2_fn_notify_no")
    conn("d2_fn_notify_no", "d2_ev_end_no")

    # GD auto-reject
    conn("d2_ev_timeout", "d2_ev_gd_48")
    conn("d2_ev_gd_48", "d2_fn_auto_reject")
    conn("d2_sys_gd_auto", "d2_fn_auto_reject")


# ============================================================
# DIAGRAM 3: Экстренное согласование
# ============================================================
def diagram_3(ox=4200, oy=0):
    """Emergency approval: Urgent order -> Verbal permission -> Post-factum."""
    cx = ox
    y = oy

    print("\n[D3] Экстренное согласование")

    frame("3. Экстренное согласование", ox, oy + 900, 1200, 2100)

    text("3. Экстренное согласование", cx, y - 60, w=400, fs="20")

    # --- Start ---
    y += 80
    event("d3_start", "Срочный заказ\nклиента", cx, y, C["start"])

    y += VS
    func("d3_fn_request", "Запросить устное\nразрешение\n(телефон/мессенджер)", cx, y, w=250, h=90)
    org("d3_org_mgr", "Менеджер", cx - 270, y)

    y += VS
    event("d3_ev_requested", "Разрешение\nзапрошено", cx, y, C["mid"])

    # --- XOR: Permission given? ---
    y += VS
    xor("d3_xor_perm", cx, y)

    # Left: Denied
    lx = cx - HS
    yl = y + VS
    event("d3_ev_denied", "Отказано", lx, yl, C["end"], w=150, h=60)

    yl += VS
    ref("d3_ref_d2", ">> Диаграмма 2:\nСтандартное\nсогласование", lx, yl, w=200, h=80)

    # Right: Permitted
    rx = cx + HS // 2
    yr = y + VS
    event("d3_ev_ok", "Разрешение\nполучено", rx, yr, C["mid"], w=180, h=70)

    yr += VS
    func("d3_fn_fix", "Зафиксировать факт:\nскриншот/журнал\n+ ФИО из справочника", rx, yr, w=260, h=100)
    sys_("d3_sys_1c", "1С:УТ", rx + 280, yr)
    doc("d3_doc_proof", "Скриншот/запись\nв журнале", rx - 270, yr)

    yr += VS
    event("d3_ev_fixed", "Экстренное\nсогласование\nоформлено", rx, yr, C["mid"], w=200, h=90)

    yr += VS
    func("d3_fn_approve", "Перевести Заказ\nв «Согласован»\nс пометкой «Экстренно»", rx, yr, w=260, h=100)

    yr += VS
    event("d3_ev_approved", "Заказ согласован\n(экстренно)", rx, yr, C["start"])

    # --- Post-factum ---
    yr += VS
    func("d3_fn_postfactum", "Получить согласование\nпостфактум в 1С:ДО\n(SLA 24 раб. часа)", rx, yr, w=260, h=100)
    sys_("d3_sys_do", "1С:ДО", rx + 280, yr)
    org("d3_org_approver", "Согласующий", rx - 270, yr)

    yr += VS
    event("d3_ev_pf_done", "Постфактум\nсогласование\nзавершено", rx, yr, C["mid"], w=200, h=90)

    # --- XOR: Post-factum result ---
    yr += VS
    xor("d3_xor_pf", rx, yr)

    # OK
    yr_ok = yr + VS
    event("d3_ev_pf_ok", "Подтверждено\nпостфактум", rx - 200, yr_ok, C["start"], w=170, h=70)

    yr_ok += VS
    event("d3_ev_end_ok", "Процесс\nзавершен", rx - 200, yr_ok, C["start"], w=160, h=70)

    # Rejected post-factum
    yr_no = yr + VS
    event("d3_ev_pf_no", "Отклонено\nпостфактум", rx + 200, yr_no, C["end"], w=170, h=70)

    yr_no += VS
    func("d3_fn_incident", "Зарегистрировать\nинцидент", rx + 200, yr_no, w=200, h=70)

    yr_no += VS
    event("d3_ev_incident", "Инцидент\nзафиксирован\n(в отчет)", rx + 200, yr_no, C["end"], w=180, h=90)

    # --- Limits note ---
    note_y = yr_no + VS
    shape("d3_note", "round_rectangle",
          "Лимит: 3 экстр./мес\nна менеджера\n5 экстр./мес\nна контрагента",
          rx, note_y, 200, 100, "#FFF3E0", border="#FF9800", fs="11")

    # --- Connectors ---
    print("  [connectors]")
    conn("d3_start", "d3_fn_request")
    conn("d3_org_mgr", "d3_fn_request")
    conn("d3_fn_request", "d3_ev_requested")
    conn("d3_ev_requested", "d3_xor_perm")

    conn("d3_xor_perm", "d3_ev_denied", "Отказ")
    conn("d3_xor_perm", "d3_ev_ok", "Разрешено")

    conn("d3_ev_denied", "d3_ref_d2")

    conn("d3_ev_ok", "d3_fn_fix")
    conn("d3_sys_1c", "d3_fn_fix")
    conn("d3_doc_proof", "d3_fn_fix")
    conn("d3_fn_fix", "d3_ev_fixed")
    conn("d3_ev_fixed", "d3_fn_approve")
    conn("d3_fn_approve", "d3_ev_approved")
    conn("d3_ev_approved", "d3_fn_postfactum")
    conn("d3_sys_do", "d3_fn_postfactum")
    conn("d3_org_approver", "d3_fn_postfactum")
    conn("d3_fn_postfactum", "d3_ev_pf_done")
    conn("d3_ev_pf_done", "d3_xor_pf")

    conn("d3_xor_pf", "d3_ev_pf_ok", "Подтверждено")
    conn("d3_xor_pf", "d3_ev_pf_no", "Отклонено")

    conn("d3_ev_pf_ok", "d3_ev_end_ok")
    conn("d3_ev_pf_no", "d3_fn_incident")
    conn("d3_fn_incident", "d3_ev_incident")


# ============================================================
# LEGEND (shared)
# ============================================================
def build_legend(ox=5800, oy=0):
    print("\n[Legend]")

    frame("Легенда ePC", ox, oy + 300, 350, 800)

    text("Легенда", ox, oy - 40, w=200, fs="18")

    y = oy + 40
    event("leg_ev_s", "Начало", ox, y, C["start"], w=140, h=55)
    y += 80
    event("leg_ev_m", "Промежуточное", ox, y, C["mid"], w=140, h=55)
    y += 80
    event("leg_ev_e", "Конец", ox, y, C["end"], w=140, h=55)
    y += 80
    func("leg_fn", "Функция", ox, y, w=140, h=50)
    y += 70
    xor("leg_xor", ox, y)
    y += 70
    org("leg_org", "Роль", ox, y)
    y += 70
    sys_("leg_sys", "ИС", ox, y)
    y += 70
    doc("leg_doc", "Документ", ox, y)
    y += 70
    ref("leg_ref", "Ссылка на\nдругую\nдиаграмму", ox, y, w=140, h=60)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("Miro ePC Creator: FM-LS-PROFIT (3 diagrams)")
    print(f"Board: {BOARD_ID}")

    # Test connection
    r = requests.get(f"https://api.miro.com/v2/boards/{BOARD_ID}", headers=HEADERS)
    if r.status_code != 200:
        print(f"ERROR: {r.status_code}")
        sys.exit(1)
    print(f"Board: {r.json()['name']}\n")

    diagram_1(ox=0, oy=0)
    diagram_2(ox=2200, oy=0)
    diagram_3(ox=4600, oy=0)
    build_legend(ox=6200, oy=0)

    print(f"\n{'='*50}")
    print(f"Frames:     {stats['frames']}")
    print(f"Shapes:     {stats['shapes']}")
    print(f"Texts:      {stats['texts']}")
    print(f"Connectors: {stats['connectors']}")
    print(f"TOTAL:      {sum(stats.values())}")
    print(f"\nBoard: https://miro.com/app/board/{BOARD_ID}")
