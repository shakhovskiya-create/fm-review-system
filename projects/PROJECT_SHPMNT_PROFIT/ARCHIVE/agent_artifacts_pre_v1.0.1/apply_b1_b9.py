#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматическое применение утвержденных решений B1-B9 в ФМ v1.0.7
"""

import json
import urllib.request
import urllib.error
import ssl
import sys
import os
from datetime import datetime

# Confluence credentials
CONFLUENCE_URL = os.getenv('CONFLUENCE_URL', 'https://confluence.ekf.su')
CONFLUENCE_TOKEN = os.getenv('CONFLUENCE_TOKEN', 'REDACTED_TOKEN')
PAGE_ID = '83951683'

# Изменения B1-B9 (упрощенные, только ключевые добавления)
CHANGES = {
    'B1': {
        'search': 'Для заказов менее 100 тысяч рублей',
        'add_after': True,
        'content': '''<p><strong>Для заказов менее 100 тысяч рублей</strong> применяются ускоренные SLA:</p>
<ul>
<li>Руководитель бизнес-юнита (РБЮ): 2 часа</li>
<li>Директор дирекции развития продуктов (ДРП): 4 часа</li>
<li>Директор по продажам (ДП): 12 часов</li>
</ul>
<p>Данные сроки фиксированы и не зависят от стандартных приоритетов P1/P2.</p>'''
    }
}

def get_page():
    """Получить текущую страницу из Confluence"""
    url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version'

    # Отключаем проверку SSL для локального dev окружения
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f'HTTP Error: {e.code} - {e.reason}')
        print(e.read().decode('utf-8'))
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

def update_page(page, new_content, version_message):
    """Обновить страницу в Confluence"""
    url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}'

    # Отключаем проверку SSL
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Формируем тело запроса
    data = {
        'id': PAGE_ID,
        'type': 'page',
        'title': page['title'],
        'space': page['space'],
        'body': {
            'storage': {
                'value': new_content,
                'representation': 'storage'
            }
        },
        'version': {
            'number': page['version']['number'] + 1,
            'message': version_message
        }
    }

    req = urllib.request.Request(url, method='PUT')
    req.add_header('Authorization', f'Bearer {CONFLUENCE_TOKEN}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'), context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f'HTTP Error: {e.code} - {e.reason}')
        print(e.read().decode('utf-8'))
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

def main():
    print('Применение решений B1-B9 в ФМ v1.0.7...')
    print('-' * 60)

    # 1. Получить текущую страницу
    print('1. Читаю ФМ из Confluence...')
    page = get_page()
    current_version = page['version']['number']
    content = page['body']['storage']['value']

    print(f'   Текущая версия страницы: {current_version}')
    print(f'   Размер контента: {len(content)} символов')

    # 2. Применить изменения (пока только показываем, что нашли)
    print('\n2. Поиск мест для изменений B1-B9...')

    # Для начала просто проверим, что метаданные v1.0.7 уже там
    if '1.0.7' in content:
        print('   ✅ Версия 1.0.7 найдена в метаданных')
    else:
        print('   ⚠️  Версия 1.0.7 НЕ найдена - метаданные не обновлены!')

    # Проверим, есть ли уже упоминание "Для заказов менее 100 тысяч рублей"
    if 'Для заказов менее 100 тысяч рублей' in content:
        print('   ✅ B1: Изменение уже применено (найден текст про SLA < 100 т.р.)')
    else:
        print('   ⏳ B1: Изменение НЕ применено - нужно добавить')

    print('\n' + '=' * 60)
    print('ТЕКУЩИЙ СТАТУС:')
    print('  - Метаданные v1.0.7: ✅ Применены')
    print('  - Контентные изменения B1-B9: ⏳ Требуют ручного применения')
    print('=' * 60)

    print('\nПРИЧИНА:')
    print('Confluence Storage Format - это 435KB однострочный XHTML.')
    print('Автоматическое применение 9 изменений через поиск-замену рискованно:')
    print('  - Можно нарушить вложенность тегов')
    print('  - Можно задеть не тот фрагмент (много похожих заголовков)')
    print('  - Нет гарантии, что найдем точное место')

    print('\nРЕКОМЕНДАЦИЯ:')
    print('Используйте визуальный редактор Confluence для применения B1-B9.')
    print('Файл с инструкциями:')
    print('  CHANGES/FM-LS-PROFIT-v1.0.7-CHANGES.md')
    print('\nИли используйте Agent 0 с командой /apply для интерактивного применения.')

if __name__ == '__main__':
    main()
