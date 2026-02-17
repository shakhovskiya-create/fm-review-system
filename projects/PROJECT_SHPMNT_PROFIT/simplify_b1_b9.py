import json
import urllib.request
import ssl
import re
import os
import sys

CONFLUENCE_URL = os.getenv('CONFLUENCE_URL', 'https://confluence.ekf.su')
CONFLUENCE_TOKEN = os.getenv('CONFLUENCE_TOKEN')
if not CONFLUENCE_TOKEN:
    print("Error: CONFLUENCE_TOKEN environment variable is required")
    sys.exit(1)
PAGE_ID = '83951683'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version,space'
req = urllib.request.Request(url)
req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')

with urllib.request.urlopen(req, context=ctx) as resp:
    page = json.loads(resp.read().decode('utf-8'))
    content = page['body']['storage']['value']
    version = page['version']['number']

print(f"Версия: {version}")
print()
print("УПРОЩЕНИЕ B1-B9 (простой язык для менеджера):")
print("=" * 60)

# Замены ВСЕХ сложных формулировок
replacements = [
    # B2
    ('автосогласование', 'система согласует сама'),
    
    # B3
    ('резервируется жестко', 'резервируется'),
    ('через 48ч', 'через 48 часов'),
    
    # B4 - КРИТИЧНО: англицизмы!
    ('Таймаут:', 'Максимальное время:'),
    ('email + push', 'письмо на почту + уведомление в системе'),
    
    # B5
    ('автоотказ', 'автоматический отказ'),
    ('арбитраж', 'ручное согласование'),
    
    # B6
    ('п.п.', 'процента'),
    ('Фиксирует в аудите', 'Записывает в журнал'),
    
    # B7 - КРИТИЧНО: англицизм!
    ('cherry-picking', 'выборочного возврата'),
    
    # B9
    ('Автофиксация', 'Система автоматически фиксирует'),
    
    # Общие
    ('корректировку (если согласен)', 'изменение цены (по желанию)'),
    ('допустимо -', 'стало допустимым -'),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1
        print(f"✅ {count}. '{old[:40]}' → '{new[:40]}'")

print()
print(f"Всего замен: {count}")
print()

# Публикуем
data = {
    'id': PAGE_ID,
    'type': 'page',
    'title': page['title'],
    'space': page['space'],
    'body': {'storage': {'value': content, 'representation': 'storage'}},
    'version': {'number': version + 1, 'message': '[FM 1.0.7] Упрощение B1-B9: убраны англицизмы, простой язык'}
}

url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}'
req = urllib.request.Request(url, method='PUT')
req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')
req.add_header('Content-Type', 'application/json')

with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), context=ctx) as resp:
    result = json.loads(resp.read().decode('utf-8'))
    new_ver = result['version']['number']

print(f"✅ Опубликовано: {version} → {new_ver}")
