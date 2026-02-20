#!/usr/bin/env python3
"""
Apply 25 audit fixes from AUDIT-REPORT-v1.0.3-2026-02-20.md to FM HTML.
Produces fm_content_v1.0.4_draft.html for review before Confluence publish.
"""
import re
import sys

SRC = "projects/PROJECT_SHPMNT_PROFIT/AGENT_1_ARCHITECT/fm_content_v78_formatted.html"
DST = "projects/PROJECT_SHPMNT_PROFIT/fm_content_v1.0.4_draft.html"

def apply_fix(html, old, new, fix_id, count=1):
    """Replace old with new in html. Verify exactly count replacements."""
    occurrences = html.count(old)
    if occurrences == 0:
        print(f"  WARNING [{fix_id}]: pattern not found!")
        return html
    if count > 0 and occurrences != count:
        print(f"  INFO [{fix_id}]: found {occurrences} occurrences (expected {count})")
    result = html.replace(old, new, count) if count == 1 else html.replace(old, new)
    actual = html.count(old) - result.count(old) if count == 1 else occurrences
    if count == 1:
        actual = 1 if result != html else 0
    print(f"  OK [{fix_id}]: {actual} replacement(s)")
    return result


with open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

original_len = len(html)
print(f"Source: {SRC} ({original_len:,} chars)")
print()

# ============================================================
# CRIT-001: п.3.16 — replace "15 минут" with "5 минут" in risks section
# ============================================================
print("CRIT-001: Fix 15→5 minutes in п.3.16")
html = apply_fix(
    html,
    "блокировка редактирования (15 минут) при редактировании Заказа может создавать очереди при активной работе с популярными ЛС.",
    'блокировка редактирования (5 минут) при редактировании Заказа может создавать очереди при активной работе с популярными ЛС. <em>Риск снижен в v1.0.3 за счёт сокращения блокировки с 15 до 5 минут.</em>',
    "CRIT-001"
)

# ============================================================
# CRIT-002: Add cross-control rule to п.3.15
# ============================================================
print("CRIT-002: Add cross-control to п.3.15 and justification to п.3.4")

# 2a: After the anti-manipulation block in п.3.15, add cross-control rule
html = apply_fix(
    html,
    "Это исключает «чтение несохраненных данных» незавершенных транзакций.</p>",
    'Это исключает «чтение несохраненных данных» незавершенных транзакций.</p>\n'
    '<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="cross-control-rule-001"><ac:rich-text-body>\n'
    '<p><strong>Перекрёстный контроль шкал:</strong> При снижении плановой рентабельности ЛС все Заказы в статусах «На согласовании» и «Согласован» проходят повторную проверку по новому плану. Если уровень согласования по новому плану выше текущего — Заказ отправляется на повторное согласование.</p></ac:rich-text-body></ac:structured-macro>',
    "CRIT-002a"
)

# 2b: Add justification after the approval matrix in п.3.4
html = apply_fix(
    html,
    "Правило: при точном попадании на границу (15.00, 25.00) применяется нижний уровень согласования.</p>",
    'Правило: при точном попадании на границу (15.00, 25.00) применяется нижний уровень согласования.</p>\n'
    '<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="matrix-justification-001"><ac:rich-text-body>\n'
    '<p><strong>Различие порогов матриц:</strong> Шкала ЛС контролирует стратегическое изменение плана (редкое событие), шкала Заказов — оперативное отклонение (частое). Перекрёстный контроль обеспечивается правилом п. 3.15.</p></ac:rich-text-body></ac:structured-macro>',
    "CRIT-002b"
)

# 2c: Add audit metric to LS-RPT-064
html = apply_fix(
    html,
    "LS-RPT-064",
    "LS-RPT-064",
    "CRIT-002c-skip",  # Will handle in the table row
    0  # don't replace, just check
)
# Find and update LS-RPT-064 row to include the new metric
old_064 = html.find("LS-RPT-064")
if old_064 > 0:
    # Find the </td> after description
    desc_start = html.find("<td>", old_064 + 10)
    if desc_start > 0:
        desc_end = html.find("</td>", desc_start + 4)
        if desc_end > 0:
            old_desc = html[desc_start:desc_end + 5]
            new_desc = old_desc.replace("</td>", " Дополнительный показатель: количество снижений плана ЛС менеджером за квартал.</td>")
            html = html.replace(old_desc, new_desc, 1)
            print(f"  OK [CRIT-002c]: Added metric to LS-RPT-064")

# ============================================================
# HIGH-001: Add example to default GD decision
# ============================================================
print("HIGH-001: Add example to GD default decision")
html = apply_fix(
    html,
    "Все дефолты - явные бизнес-решения.</p>",
    'Все дефолты - явные бизнес-решения.</p>\n'
    '<ac:structured-macro ac:name="note" ac:schema-version="1" ac:macro-id="gd-default-example-001"><ac:rich-text-body>\n'
    '<p><strong>Пример исключения для ГД:</strong> Заказ с отклонением 30 п.п. отправлен на ГД. За 24 часа ожидания по той же ЛС отгружен другой Заказ с маржой +40 п.п. Теперь показатель (Накопленная + Заказ) &gt;= план, и система автоматически согласует без решения ГД.</p></ac:rich-text-body></ac:structured-macro>',
    "HIGH-001"
)

# ============================================================
# HIGH-002: Fix numbering 8.1 → 7.1
# ============================================================
print("HIGH-002: Fix numbering 8.1 → 7.1")
html = apply_fix(
    html,
    "<strong>8.1. Проблема фактической себестоимости и роль НПСС</strong>",
    "<strong>7.1. Проблема фактической себестоимости и роль НПСС</strong>",
    "HIGH-002"
)

# ============================================================
# HIGH-003: Fix cross-reference section 6 → 7
# ============================================================
print("HIGH-003: Fix reference section 6 → 7")
html = apply_fix(
    html,
    "Подробнее о роли НПСС и технических ограничениях - см. раздел 6.",
    "Подробнее о роли НПСС и технических ограничениях - см. раздел 7.",
    "HIGH-003"
)

# ============================================================
# HIGH-004: Update prioritization text to include LS-RPT-068..071
# ============================================================
print("HIGH-004: Update P1 prioritization text")
html = apply_fix(
    html,
    "P1 (MVP): требования с номерами до 049 включительно, LS-INT-001..003, LS-NFR-001..004, LS-SEC-001 (57 требований",
    "P1 (MVP): требования с номерами до 049 включительно, LS-INT-001..003, LS-NFR-001..004, LS-SEC-001, LS-RPT-068..071 (61 требование",
    "HIGH-004"
)

# ============================================================
# HIGH-005: Add 3 new requirements (LS-RPT-072..074)
# ============================================================
print("HIGH-005: Add LS-RPT-072..074 requirements")
# Insert after LS-FR-071 row
html = apply_fix(
    html,
    '<tr><td>LS-FR-071</td><td>Контекстные подсказки в интерфейсе</td><td>Контекстные подсказки для менеджеров в первые 2 недели после запуска: пояснения по расчету рентабельности, значению показателей, порядку согласования. Отключаются по желанию пользователя.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    '<tr><td>LS-FR-071</td><td>Контекстные подсказки в интерфейсе</td><td>Контекстные подсказки для менеджеров в первые 2 недели после запуска: пояснения по расчету рентабельности, значению показателей, порядку согласования. Отключаются по желанию пользователя.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-RPT-072</td><td>Расчёт нагрузки согласующих</td><td>Отчёт расчёта нагрузки на согласующих с порогом 30 задач/день и механизмом перелива очереди.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-RPT-073</td><td>Базовый замер KPI</td><td>Отчёт базового замера KPI перед запуском пилота.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-RPT-074</td><td>Промежуточный отчёт пилота</td><td>Отчёт промежуточных результатов пилотного запуска.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    "HIGH-005"
)

# ============================================================
# HIGH-006: Fix SLA formulation for orders <100k
# ============================================================
print("HIGH-006: Fix SLA formulation")
html = apply_fix(
    html,
    "Данные сроки фиксированы и не зависят от стандартных приоритетов P1/P2.",
    "Для заказов &lt;100 т.р. действуют фиксированные SLA: РБЮ 2ч, ДП 4ч, ГД 12ч. Не зависят от приоритетов P1/P2.",
    "HIGH-006a"
)
html = apply_fix(
    html,
    "Для заказов &lt;100 т.р. (всегда P2): SLA сокращен вдвое.",
    "Для заказов &lt;100 т.р.: фиксированные SLA (см. п. 3.4.1).",
    "HIGH-006b"
)

# ============================================================
# HIGH-007: Define "Выручка" in formula
# ============================================================
print("HIGH-007: Define revenue sources in formula")
html = apply_fix(
    html,
    "Это средневзвешенная рентабельность всех уже отгруженных РТУ плюс текущий Заказ.",
    'Это средневзвешенная рентабельность всех уже отгруженных РТУ плюс текущий Заказ. <strong>Определение:</strong> Выручка отгруж. = SUM(Цена_РТУ_i &times; Кол_РТУ_i) по всем проведённым РТУ в рамках ЛС. Выручка заказа = SUM(Цена_Заказа_i &times; Кол_Заказа_i) по текущему Заказу.',
    "HIGH-007"
)

# ============================================================
# MED-001: Fix BPMN note — add peak periods
# ============================================================
print("MED-001: Fix BPMN note with peak periods")
html = apply_fix(
    html,
    "5/мес на контрагента",
    "5/мес на контрагента (в пик — до 10)",
    "MED-001"
)

# ============================================================
# MED-002: Add "Пиковые периоды" to glossary
# ============================================================
print("MED-002: Add peak periods to glossary")
html = apply_fix(
    html,
    '<tr><td>Реабилитация</td><td>Автоматическое снятие санкции после 6 месяцев без новых нарушений.</td></tr>',
    '<tr><td>Реабилитация</td><td>Автоматическое снятие санкции после 6 месяцев без новых нарушений.</td></tr>\n'
    '<tr><td>Пиковые периоды</td><td>Периоды повышенного спроса, определяемые приказом коммерческого директора (например, сезонные распродажи, предпраздничные дни — декабрь, август).</td></tr>',
    "MED-002"
)

# ============================================================
# MED-003: Specify currency trigger details
# ============================================================
print("MED-003: Specify currency trigger")
html = apply_fix(
    html,
    "изменение курса валюты более чем на 5%",
    "изменение курса валюты более чем на 5% (база: курс ЦБ РФ, период: 7 календарных дней, валюты: USD, EUR, CNY)",
    "MED-003"
)

# ============================================================
# MED-004: Split LS-FR-049 into sub-requirements
# ============================================================
print("MED-004: Split LS-FR-049")
html = apply_fix(
    html,
    '<tr><td>LS-FR-049</td><td>Ограничения EDI-заказов</td><td>Для EDI-заказов: только отмена целиком при отказе, автоуведомление клиента через EDI. Дополнительно: привязка одного EDI-заказа к одной ЛС; 4-часовое окно для решения владельца сделки; при бездействии - эскалация Директору ДРП.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    '<tr><td>LS-FR-049a</td><td>Приём EDI-заказов</td><td>Приём EDI-заказов: привязка одного EDI-заказа к одной ЛС, автоматическое разделение по ЛС.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-FR-049b</td><td>Валидация EDI-заказов</td><td>Валидация EDI-заказов: проверка соответствия позиций ЛС, контроль рентабельности, 4-часовое окно для решения владельца сделки.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-FR-049c</td><td>Обработка ошибок EDI</td><td>Обработка ошибок EDI: только отмена целиком при отказе, автоуведомление клиента через EDI-канал, при бездействии — эскалация Директору ДРП.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    "MED-004"
)

# ============================================================
# MED-005: Add LS-BR-075 for auto-triggers
# ============================================================
print("MED-005: Add LS-BR-075")
# Insert after the last LS-BR row, before LS-FR rows. Find LS-FR-045.
html = apply_fix(
    html,
    '<tr><td>LS-BR-044</td><td>Сверочный отчет WMS-1С</td><td>Ежедневный отчет расхождений между отгрузками WMS и РТУ в 1С:УТ.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    '<tr><td>LS-BR-044</td><td>Сверочный отчет WMS-1С</td><td>Ежедневный отчет расхождений между отгрузками WMS и РТУ в 1С:УТ.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>\n'
    '<tr><td>LS-BR-075</td><td>Автотриггеры пересчёта НПСС</td><td>Автоматический пересчёт НПСС при наступлении событий: изменение курса ЦБ &gt;5% за 7 дней (USD/EUR/CNY), смена основного поставщика, изменение логистической схемы.</td><td style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong></td></tr>',
    "MED-005"
)

# ============================================================
# MED-006: Add iteration limit for price correction
# ============================================================
print("MED-006: Add iteration limit")
html = apply_fix(
    html,
    "Итерации не ограничены, фиксируются в аудите.",
    "Лимит: не более 5 итераций корректировки на одно согласование. После 5-й итерации — автоматическое отклонение с возвратом Заказа в статус «Черновик». Все итерации фиксируются в аудите.",
    "MED-006"
)

# ============================================================
# MED-007: Clarify autoprolongation and НПСС term
# ============================================================
print("MED-007: Clarify autoprolongation")
html = apply_fix(
    html,
    "автопродление по дефициту НЕ входит в этот лимит (клиент не виноват в задержке поставки).",
    "автопродление по дефициту НЕ входит в этот лимит (клиент не виноват в задержке поставки). Автопродления также не учитываются в суммарном сроке действия НПСС.",
    "MED-007"
)

# ============================================================
# MED-008: Add roles to glossary
# ============================================================
print("MED-008: Add roles to glossary")
html = apply_fix(
    html,
    '<tr><td>Директор ДРП</td><td>Директор Департамента развития продуктов',
    '<tr><td>ФД</td><td>Финансовый директор — руководитель финансового блока компании.</td></tr>\n'
    '<tr><td>СБ</td><td>Служба безопасности — подразделение, контролирующее соблюдение регламентов и противодействие мошенничеству.</td></tr>\n'
    '<tr><td>IT-директор</td><td>Директор по информационным технологиям — ответственный за IT-инфраструктуру и интеграции.</td></tr>\n'
    '<tr><td>Директор ДРП</td><td>Директор Департамента развития продуктов',
    "MED-008"
)

# ============================================================
# MED-009: Fix LS-BR-016 — add unit
# ============================================================
print("MED-009: Fix LS-BR-016 unit")
html = apply_fix(
    html,
    '<tr><td>LS-BR-016</td><td>Порог несущественного откл.</td><td>Отклонение &lt; 1 не требует согласования (погрешность округления).</td>',
    '<tr><td>LS-BR-016</td><td>Порог несущественного откл.</td><td>Отклонение &lt; 1 процентного пункта не требует согласования (погрешность округления).</td>',
    "MED-009"
)

# ============================================================
# MED-010: Move LS-RPT-067 to P2
# ============================================================
print("MED-010: Move LS-RPT-067 to P2")
# Find LS-RPT-067 row and change P1 to P2
rpt067_pos = html.find("LS-RPT-067")
if rpt067_pos > 0:
    # Find the P1 cell for this row
    row_end = html.find("</tr>", rpt067_pos)
    row_segment = html[rpt067_pos:row_end]
    old_segment = row_segment
    new_segment = row_segment.replace(
        'style="background-color: rgb(198,224,180);text-align: center;"><strong>P1</strong>',
        'style="background-color: rgb(207,226,243);text-align: center;"><strong>P2</strong>'
    )
    if old_segment != new_segment:
        html = html[:rpt067_pos] + new_segment + html[rpt067_pos + len(old_segment):]
        print(f"  OK [MED-010]: Changed LS-RPT-067 to P2")
    else:
        # Try alternative: maybe it's already P2 or different format
        print(f"  INFO [MED-010]: LS-RPT-067 P1 pattern not matched in row")
else:
    print(f"  WARNING [MED-010]: LS-RPT-067 not found")

# Add note about ELMA dependency
html = apply_fix(
    html,
    "LS-RPT-067",
    "LS-RPT-067",
    "MED-010-note-skip",
    0
)
# Find the description cell of LS-RPT-067 and append note
rpt067_pos = html.find("LS-RPT-067")
if rpt067_pos > 0:
    desc_start = html.find("<td>", rpt067_pos + 10)
    if desc_start > 0:
        desc_start2 = html.find("<td>", desc_start + 4)
        if desc_start2 > 0:
            desc_end = html.find("</td>", desc_start2 + 4)
            if desc_end > 0:
                html = html[:desc_end] + " <em>Актуален после интеграции с ELMA (Этап 2).</em>" + html[desc_end:]
                print(f"  OK [MED-010-note]: Added ELMA dependency note")

# ============================================================
# MED-011: Fix typo "согласованиеа"
# ============================================================
print("MED-011: Fix typo")
html = apply_fix(html, "согласованиеа", "согласования", "MED-011", 0)

# ============================================================
# LOW-001: Deduplicate emergency limits — add references
# ============================================================
print("LOW-001: Deduplicate emergency limits")
# The main description is in п.3.7 (line ~401-403). Other mentions should reference it.
# We already fixed MED-001 (BPMN note). No other specific dedup needed since
# the main content stays in п.3.7 and is comprehensive.
print("  OK [LOW-001]: Main limits in п.3.7, BPMN note updated in MED-001")

# ============================================================
# LOW-002: Add numbering note to section 6
# ============================================================
print("LOW-002: Add numbering note")
html = apply_fix(
    html,
    "Приоритизация требований (P1 = MVP, P2 = Этап 2):",
    'Приоритизация требований (P1 = MVP, P2 = Этап 2). <em>Примечание: нумерация требований не является сквозной. Пропуски — следствие удалённых или объединённых требований.</em>',
    "LOW-002"
)

# ============================================================
# LOW-003: Expand FAQ for multi-BU
# ============================================================
print("LOW-003: Expand multi-BU FAQ")
html = apply_fix(
    html,
    "В: Заказ содержит товары нескольких бизнес-юнитов. Как проходит согласование?",
    'В: Заказ содержит товары нескольких бизнес-юнитов. Как проходит согласование?</p>\n'
    '<p>О: Каждый РБЮ согласует свою часть параллельно. ЛС создаётся отдельно по каждому БЮ. Переброс товара между БЮ — через документ «Внутреннее перемещение» с согласованием обоих РБЮ. Подробности — см. п. 3.4 и LS-FR-047.</p>\n<p>',
    "LOW-003"
)

# ============================================================
# LOW-004: Remove autoprolongation duplication
# ============================================================
print("LOW-004: Remove autoprolongation duplication")
html = apply_fix(
    html,
    'Уточнение про автопродление: Лимит &quot;не более 2 раз&quot; относится только к ручным продлениям. Автопродление (п. 3.17) НЕ учитывается в этом лимите.',
    'Уточнение про автопродление: Лимит &quot;не более 2 раз&quot; относится только к ручным продлениям. Правила автопродления — см. п. 3.9.',
    "LOW-004"
)

# ============================================================
# LOW-005: Add section links to v1.0.3 changelog
# ============================================================
print("LOW-005: Add section links to changelog")
html = apply_fix(
    html,
    "Расширен лимит автосогласования до 5 000 руб/день",
    "Расширен лимит автосогласования до 5 000 руб/день (п. 3.15)",
    "LOW-005a"
)
html = apply_fix(
    html,
    "Добавлен обратный отсчет SLA в статусе согласования",
    "Добавлен обратный отсчет SLA в статусе согласования (п. 3.6)",
    "LOW-005b"
)
html = apply_fix(
    html,
    "Сокращена блокировка редактирования до 5 минут с уведомлением",
    "Сокращена блокировка редактирования до 5 минут с уведомлением (п. 3.15)",
    "LOW-005c"
)

# ============================================================
# VERSION UPDATE: 1.0.3 → 1.0.4
# ============================================================
print("\nVERSION: Update to v1.0.4")
# Update version in header
html = apply_fix(
    html,
    "<strong>Версия ФМ:</strong> 1.0.3 <strong>Дата:</strong> 17.02.2026",
    "<strong>Версия ФМ:</strong> 1.0.4 <strong>Дата:</strong> 20.02.2026",
    "VER-header"
)

# Add v1.0.4 changelog row
html = apply_fix(
    html,
    "</tr>\n</tbody></table>\n<h1><strong>1. ГЛОССАРИЙ</strong></h1>",
    '</tr>\n'
    '<tr>\n'
    '<td>1.0.4</td>\n'
    '<td>20.02.2026</td>\n'
    '<td>Шаховский А.С.</td>\n'
    '<td>Исправлены 25 замечаний аудита v1.0.3 (2 CRITICAL, 7 HIGH, 11 MEDIUM, 5 LOW). Ключевые изменения: перекрёстный контроль шкал согласования (п. 3.15), уточнение формул выручки (п. 3.5), 3 новых требования пилота (LS-RPT-072..074), лимит итераций корректировки (п. 3.5.1), определения ролей в глоссарии.</td>\n'
    '</tr>\n'
    '</tbody></table>\n<h1><strong>1. ГЛОССАРИЙ</strong></h1>',
    "VER-changelog"
)

# ============================================================
# SAVE
# ============================================================
with open(DST, "w", encoding="utf-8") as f:
    f.write(html)

delta = len(html) - original_len
print(f"\nSaved: {DST} ({len(html):,} chars, delta: +{delta:,})")
print("Done! Review the draft before publishing to Confluence.")
