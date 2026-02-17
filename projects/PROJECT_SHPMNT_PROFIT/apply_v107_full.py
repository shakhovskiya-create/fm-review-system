#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПОЛНОЕ АВТОМАТИЧЕСКОЕ ПРИМЕНЕНИЕ v1.0.6 → v1.0.7
ВСЕ изменения B1-B9 + метаданные
"""

import json
import urllib.request
import ssl
import sys
import re
import os

CONFLUENCE_URL = os.getenv('CONFLUENCE_URL', 'https://confluence.ekf.su')
CONFLUENCE_TOKEN = os.getenv('CONFLUENCE_TOKEN')
if not CONFLUENCE_TOKEN:
    print("Error: CONFLUENCE_TOKEN environment variable is required")
    sys.exit(1)
PAGE_ID = '83951683'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ВСЕ изменения B1-B9
CHANGES = [
    ('3.4', '''
<h3><strong>Ускоренные SLA для заказов менее 100 тысяч рублей</strong></h3>
<p><strong>Для заказов менее 100 тысяч рублей</strong> применяются ускоренные SLA:</p>
<ul>
<li>Руководитель бизнес-юнита (РБЮ): 2 часа</li>
<li>Директор дирекции развития продуктов (ДРП): 4 часа</li>
<li>Директор по продажам (ДП): 12 часов</li>
</ul>
<p>Данные сроки фиксированы и не зависят от стандартных приоритетов P1/P2.</p>
''', 'B1'),

    ('3.5', '''
<h3><strong>Согласование с корректировкой цены</strong></h3>
<p><strong>Процесс:</strong></p>
<ol>
<li>Согласующий указывает рекомендуемую цену.</li>
<li>Рекомендация передается менеджеру через уведомление.</li>
<li>Менеджер вручную вносит корректировку (если согласен).</li>
<li>Система автоматически пересчитывает рентабельность.</li>
<li>Если отклонение допустимо - автосогласование.</li>
<li>Если нет - возврат на согласование.</li>
</ol>
<p><strong>Особенности:</strong></p>
<ul>
<li>EDI-заказы: корректировка недоступна.</li>
<li>Менеджер может отклонить рекомендацию.</li>
<li>Итерации не ограничены, фиксируются в аудите.</li>
</ul>
''', 'B2'),

    ('3.16', '''
<h3><strong>Логический резерв товара при дефиците</strong></h3>
<ul>
<li><strong>Блокирующий резерв (48 часов):</strong> Товар резервируется жестко на 48 часов для срочных заказов. Не может быть отгружен по другим заказам. По истечении 48ч резерв снимается автоматически.</li>
<li><strong>Информационная фиксация (до 90 дней):</strong> Система фиксирует потребность до 90 дней для планирования закупок. Не блокирует товар, служит для аналитики.</li>
</ul>
<p>Блокировка - 48ч (защита от cherry-picking), информация - 90д (для закупок).</p>
''', 'B3'),

    ('3.18', '''
<h3><strong>Регламентное задание "Пересчет санкций за невыкуп"</strong></h3>
<ul>
<li><strong>Расписание:</strong> Ежедневно 02:00 МСК.</li>
<li><strong>Retry:</strong> 3 попытки с интервалом 15 мин.</li>
<li><strong>Таймаут:</strong> 2 часа, при превышении - прерывание.</li>
<li><strong>Мониторинг:</strong> Уведомление ФД при сбое (email + push).</li>
<li><strong>Журналирование:</strong> Все запуски в журнале регламентных заданий.</li>
</ul>
''', 'B4'),

    ('3.5', '''
<h3><strong>Автоматический отказ генерального директора</strong></h3>
<p>Если ГД не рассмотрел заявку за 48ч - автоотказ со статусом "Превышение SLA".</p>
<p><strong>Дополнительно:</strong></p>
<ol>
<li>Уведомление CFO о факте автоотказа крупной сделки.</li>
<li>Пометка "Требует эскалации" в отчете CFO.</li>
<li>Менеджер может повторно подать заявку.</li>
<li>CFO может вручную одобрить через арбитраж.</li>
</ol>
''', 'B5'),

    ('3.5', '''
<h3><strong>Автосогласование при улучшении рентабельности</strong></h3>
<p>Если отклонение &lt; 1 п.п., система:</p>
<ol>
<li>Согласовывает автоматически.</li>
<li>Уведомляет согласующего.</li>
<li>Фиксирует в аудите.</li>
</ol>
<p><strong>Пример:</strong> Заявка у ДП (-4%), менеджер корректирует до -0.8% → автосогласование.</p>
''', 'B6'),

    ('3.13', '''
<h3><strong>Выручка отгруженного (нетто)</strong></h3>
<p><strong>Выручка отгруженного (нетто)</strong> = Сумма отгруженного по ЛС - Сумма возвращенного (за 60 дней)</p>
<p>Система пересчитывает рентабельность ЛС при каждом возврате в течение 60 дней. Обеспечивает корректный учет с учетом cherry-picking.</p>
''', 'B7'),

    ('3.15', '''
<h3><strong>Автопродление ЛС и контроль НПСС</strong></h3>
<p>Автопродление ЛС <strong>НЕ влияет</strong> на контроль НПСС &gt; 90 дней. Блокировка действует независимо.</p>
<p><strong>Пример:</strong> Товар поступил на 95-й день. ЛС продлена, но товар блокирован как НПСС &gt; 90д. Менеджер не может отгрузить до решения с РБЮ.</p>
''', 'B8'),

    ('3.16', '''
<h3><strong>Определение подтвержденного дефицита</strong></h3>
<p>Система автоматически определяет дефицит:</p>
<ul>
<li>Остаток = 0</li>
<li>Нет поступлений в течение 30 дней</li>
<li>Нет заказов поставщику</li>
</ul>
<p>Автофиксация + резерв 48ч + информация 90д.</p>
<p><strong>Арбитраж РБЮ:</strong> Если менеджер не согласен, заявка к РБЮ (SLA 3 дня).</p>
''', 'B9'),
]

def get_page():
    url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version,space'
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode('utf-8'))

def find_section_end(content, section):
    pattern = rf'(<h2[^>]*><strong>{re.escape(section)}\.?\s+[^<]+</strong></h2>)'
    match = re.search(pattern, content)
    if not match:
        return None
    start = match.end()
    next_h = re.search(r'<h[12][^>]*><strong>\d+\.', content[start:])
    if next_h:
        return start + next_h.start()
    return len(content)

def apply_changes(content):
    for section, text, change_id in CHANGES:
        pos = find_section_end(content, section)
        if pos:
            content = content[:pos] + text + content[pos:]
            print(f"  ✅ {change_id} → раздел {section}")
        else:
            print(f"  ⚠️  {change_id}: раздел {section} не найден")
    return content

def update_metadata(content):
    # Мета-блок
    content = re.sub(
        r'(Версия:</strong>\s*)1\.0\.6(\s*\|\s*Дата:</strong>\s*)09\.02\.2026',
        r'\g<1>1.0.7\g<2>13.02.2026', content)
    # Мета-таблица
    content = re.sub(r'(<td[^>]*>)\s*1\.0\.6\s*(</td>)', r'\g<1>1.0.7\g<2>',content, count=1)
    content = re.sub(r'(<td[^>]*>)\s*09\.02\.2026\s*(</td>)', r'\g<1>13.02.2026\g<2>',content, count=1)
    # История - добавим строку перед </tbody>
    hist = '<tr><td>1.0.7</td><td>13.02.2026</td><td>Шаховский А.С.</td><td>Внесены уточнения по 9 бизнес-вопросам: SLA для заказов менее 100 т.р., цикл согласования с корректировкой цены, логический резерв ЛС при дефиците (48ч + 90д), retry/мониторинг пересчета санкций, автоотказ ГД (уведомление CFO), автосогласование при улучшении рентабельности, формулы выручки (нетто с возвратами), контроль НПСС при автопродлении ЛС, автоматическое определение дефицита</td></tr>\n</tbody>'
    content = re.sub(r'</tbody>', hist, content, count=1)
    return content

print("=" * 60)
print("ПРИМЕНЕНИЕ v1.0.6 → v1.0.7")
print("=" * 60)
print()

page = get_page()
ver = page['version']['number']
content = page['body']['storage']['value']

print(f"Версия: {ver} | Размер: {len(content)} байт")
print()

print("Применяю метаданные...")
content = update_metadata(content)
print("  ✅ Метаданные")
print()

print("Применяю B1-B9...")
content = apply_changes(content)
print()

print("Публикую...")
data = {
    'id': PAGE_ID,
    'type': 'page',
    'title': page['title'],
    'space': page['space'],
    'body': {'storage': {'value': content, 'representation': 'storage'}},
    'version': {'number': ver + 1, 'message': '[FM 1.0.7] Уточнения по B1-B9'}
}

url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}'
req = urllib.request.Request(url, method='PUT')
req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')
req.add_header('Content-Type', 'application/json')

with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), context=ctx) as resp:
    result = json.loads(resp.read().decode('utf-8'))
    new_ver = result['version']['number']

print(f"✅ Опубликовано: версия {ver} → {new_ver}")
print()
print(f"Confluence: {CONFLUENCE_URL}/pages/viewpage.action?pageId={PAGE_ID}")
