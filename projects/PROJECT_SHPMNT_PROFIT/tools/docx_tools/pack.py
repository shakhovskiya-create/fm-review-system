#!/usr/bin/env python3
"""
DOCX Pack Script
Упаковывает распакованный DOCX обратно в .docx файл.

Использование:
    python pack.py ./unpacked/ output.docx --original input.docx
"""

import sys
import zipfile
import os
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET


def validate_xml(xml_path):
    """Проверяет валидность XML и пытается исправить типичные ошибки"""
    
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    errors = []
    fixed = False
    
    # 1. Проверка durableId (должен быть < 0x7FFFFFFF)
    durable_pattern = re.compile(r'w:durableId="(\d+)"')
    for match in durable_pattern.finditer(content):
        durable_id = int(match.group(1))
        if durable_id >= 0x7FFFFFFF:
            # Генерируем новый валидный ID
            import random
            new_id = random.randint(1, 0x7FFFFFFE)
            content = content.replace(f'w:durableId="{durable_id}"', f'w:durableId="{new_id}"')
            errors.append(f"  ⚠️ Fixed durableId: {durable_id} → {new_id}")
            fixed = True
    
    # 2. Проверка xml:space="preserve" для <w:t> с пробелами
    t_pattern = re.compile(r'<w:t>([^<]*)</w:t>')
    for match in t_pattern.finditer(content):
        text = match.group(1)
        if text.startswith(' ') or text.endswith(' ') or '  ' in text:
            old = match.group(0)
            new = f'<w:t xml:space="preserve">{text}</w:t>'
            content = content.replace(old, new, 1)
            fixed = True
    
    # 3. Проверка парности тегов (базовая)
    open_tags = re.findall(r'<w:(\w+)(?:\s|>)', content)
    close_tags = re.findall(r'</w:(\w+)>', content)
    
    # Считаем несбалансированные теги
    from collections import Counter
    open_count = Counter(open_tags)
    close_count = Counter(close_tags)
    
    for tag in set(open_count.keys()) | set(close_count.keys()):
        diff = open_count.get(tag, 0) - close_count.get(tag, 0)
        if diff != 0 and tag not in ['br', 'tab', 'cr']:  # self-closing tags
            errors.append(f"  ⚠️ Tag imbalance: <w:{tag}> open={open_count.get(tag,0)}, close={close_count.get(tag,0)}")
    
    # Сохраняем исправленный контент
    if fixed:
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return errors, fixed


def condense_xml(xml_path):
    """Убирает лишние пробелы и переносы строк из XML"""
    
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Убираем переносы строк и лишние пробелы между тегами
    content = re.sub(r'>\s+<', '><', content)
    
    # Но сохраняем пробелы внутри <w:t>
    # Это сложнее, поэтому делаем осторожно
    
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(content)


def pack_docx(input_dir, output_path, original_path=None, validate=True, condense=True):
    """
    Упаковывает директорию в DOCX файл.
    
    Args:
        input_dir: директория с распакованным DOCX
        output_path: путь для выходного .docx файла
        original_path: путь к оригинальному файлу (для копирования media)
        validate: проверять и исправлять XML
        condense: сжимать XML (убирать лишние пробелы)
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    
    if not input_dir.exists():
        print(f"❌ Директория не найдена: {input_dir}")
        sys.exit(1)
    
    print(f"📦 Упаковка: {input_dir} → {output_path}")
    
    # Валидация XML файлов
    if validate:
        xml_files = list(input_dir.rglob('*.xml'))
        for xml_path in xml_files:
            if xml_path.is_file():
                errors, fixed = validate_xml(xml_path)
                if errors:
                    rel_path = xml_path.relative_to(input_dir)
                    print(f"  📄 {rel_path}:")
                    for err in errors:
                        print(err)
                if fixed:
                    print(f"    ✓ Auto-fixed")
    
    # Сжатие XML (опционально)
    if condense:
        xml_files = list(input_dir.rglob('*.xml'))
        for xml_path in xml_files:
            if xml_path.is_file():
                condense_xml(xml_path)
    
    # Копируем media из оригинала если указан
    if original_path:
        original_path = Path(original_path)
        if original_path.exists():
            with zipfile.ZipFile(original_path, 'r') as zf:
                for name in zf.namelist():
                    if name.startswith('word/media/'):
                        dest = input_dir / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not dest.exists():
                            with zf.open(name) as src, open(dest, 'wb') as dst:
                                dst.write(src.read())
                            print(f"  📷 Скопировано: {name}")
    
    # Удаляем старый файл если существует
    if output_path.exists():
        output_path.unlink()
    
    # Создаём ZIP с правильным порядком файлов
    # [Content_Types].xml должен быть первым
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Сначала [Content_Types].xml
        content_types = input_dir / '[Content_Types].xml'
        if content_types.exists():
            zf.write(content_types, '[Content_Types].xml')
        
        # Затем остальные файлы
        for root, dirs, files in os.walk(input_dir):
            # Пропускаем скрытые директории
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file == '[Content_Types].xml':
                    continue  # Уже добавили
                if file.startswith('.'):
                    continue  # Пропускаем скрытые файлы
                
                file_path = Path(root) / file
                arcname = file_path.relative_to(input_dir)
                zf.write(file_path, arcname)
    
    print(f"✅ Создан: {output_path}")
    print(f"   Размер: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    if len(sys.argv) < 3:
        print("Использование: python pack.py <input_dir> <output.docx> [--original original.docx]")
        print("Опции:")
        print("  --original <file>   Копировать media из оригинального файла")
        print("  --no-validate       Не проверять XML")
        print("  --no-condense       Не сжимать XML")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_path = sys.argv[2]
    
    # Парсим опции
    original_path = None
    if '--original' in sys.argv:
        idx = sys.argv.index('--original')
        if idx + 1 < len(sys.argv):
            original_path = sys.argv[idx + 1]
    
    validate = '--no-validate' not in sys.argv
    condense = '--no-condense' not in sys.argv
    
    pack_docx(input_dir, output_path, original_path, validate, condense)


if __name__ == '__main__':
    main()
