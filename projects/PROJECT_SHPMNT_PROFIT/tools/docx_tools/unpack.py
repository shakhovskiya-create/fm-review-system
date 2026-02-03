#!/usr/bin/env python3
"""
DOCX Unpack Script
Распаковывает .docx файл, форматирует XML и мержит split runs.

Использование:
    python unpack.py input.docx ./unpacked/
"""

import sys
import zipfile
import os
import re
import shutil
from pathlib import Path
import xml.dom.minidom as minidom


def merge_adjacent_runs(xml_content):
    """
    Объединяет соседние <w:r> блоки с одинаковым форматированием.
    Это решает проблему split runs в Word.
    """
    # Паттерн для поиска соседних runs с одинаковым rPr
    # <w:r><w:rPr>...</w:rPr><w:t>text1</w:t></w:r><w:r><w:rPr>...</w:rPr><w:t>text2</w:t></w:r>
    
    def merge_runs_in_paragraph(match):
        """Мержит runs внутри одного параграфа"""
        content = match.group(0)
        
        # Находим все runs
        run_pattern = re.compile(
            r'<w:r>(\s*<w:rPr>(.*?)</w:rPr>\s*)?<w:t([^>]*)>(.*?)</w:t>\s*</w:r>',
            re.DOTALL
        )
        
        runs = list(run_pattern.finditer(content))
        if len(runs) < 2:
            return content
        
        # Группируем runs по форматированию
        merged = []
        i = 0
        while i < len(runs):
            current_rPr = runs[i].group(2) or ""
            current_attrs = runs[i].group(3) or ""
            texts = [runs[i].group(4)]
            
            # Собираем все следующие runs с таким же форматированием
            j = i + 1
            while j < len(runs):
                next_rPr = runs[j].group(2) or ""
                if next_rPr == current_rPr:
                    texts.append(runs[j].group(4))
                    j += 1
                else:
                    break
            
            # Создаём объединённый run
            merged_text = "".join(texts)
            if current_rPr:
                merged_run = f'<w:r><w:rPr>{current_rPr}</w:rPr><w:t{current_attrs}>{merged_text}</w:t></w:r>'
            else:
                merged_run = f'<w:r><w:t{current_attrs}>{merged_text}</w:t></w:r>'
            
            merged.append(merged_run)
            i = j
        
        # Заменяем runs в контенте
        result = content
        for run in reversed(runs):
            result = result[:run.start()] + result[run.end():]
        
        # Вставляем merged runs
        insert_pos = content.find('<w:r>')
        if insert_pos != -1:
            result = content[:insert_pos] + ''.join(merged) + content[runs[-1].end():]
        
        return result
    
    # Применяем к каждому параграфу
    # Упрощённый подход - мержим соседние runs глобально
    pattern = re.compile(
        r'</w:t></w:r>(\s*)<w:r>(\s*<w:rPr>(.*?)</w:rPr>\s*)?<w:t([^>]*)>',
        re.DOTALL
    )
    
    def simple_merge(m):
        whitespace = m.group(1)
        rPr_block = m.group(2) or ""
        rPr_content = m.group(3) or ""
        t_attrs = m.group(4) or ""
        
        # Если следующий run имеет rPr, не мержим (разное форматирование)
        if rPr_content:
            return m.group(0)
        
        # Мержим - убираем закрытие/открытие тегов
        return ""
    
    # Итеративно мержим пока есть что мержить
    prev_content = None
    while prev_content != xml_content:
        prev_content = xml_content
        xml_content = pattern.sub(simple_merge, xml_content)
    
    return xml_content


def convert_smart_quotes(xml_content):
    """Конвертирует smart quotes в XML entities"""
    replacements = [
        (''', '&#x2018;'),  # left single quote
        (''', '&#x2019;'),  # right single quote / apostrophe
        ('"', '&#x201C;'),  # left double quote
        ('"', '&#x201D;'),  # right double quote
        ('–', '&#x2013;'),  # en dash
        ('—', '&#x2014;'),  # em dash
        ('…', '&#x2026;'),  # ellipsis
    ]
    
    for char, entity in replacements:
        xml_content = xml_content.replace(char, entity)
    
    return xml_content


def pretty_print_xml(xml_content):
    """Форматирует XML для читаемости"""
    try:
        # Пробуем через minidom
        dom = minidom.parseString(xml_content.encode('utf-8'))
        pretty = dom.toprettyxml(indent="  ")
        # Убираем лишнюю XML декларацию если она дублируется
        lines = pretty.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        return '\n'.join(lines)
    except Exception:
        # Если не получилось - возвращаем как есть
        return xml_content


def unpack_docx(input_path, output_dir, merge_runs=True, pretty=True):
    """
    Распаковывает DOCX файл.
    
    Args:
        input_path: путь к .docx файлу
        output_dir: директория для распаковки
        merge_runs: объединять ли split runs
        pretty: форматировать ли XML
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        sys.exit(1)
    
    # Очищаем output директорию если существует
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(parents=True)
    
    print(f"📦 Распаковка: {input_path}")
    
    # Распаковываем ZIP
    with zipfile.ZipFile(input_path, 'r') as zf:
        zf.extractall(output_dir)
    
    # Обрабатываем XML файлы
    xml_files = [
        'word/document.xml',
        'word/styles.xml',
        'word/numbering.xml',
        'word/comments.xml',
        'word/footnotes.xml',
        'word/endnotes.xml',
    ]
    
    for xml_file in xml_files:
        xml_path = output_dir / xml_file
        if not xml_path.exists():
            continue
        
        print(f"  📄 Обработка: {xml_file}")
        
        with open(xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Конвертируем smart quotes
        content = convert_smart_quotes(content)
        
        # Мержим split runs (только для document.xml)
        if merge_runs and xml_file == 'word/document.xml':
            original_runs = content.count('<w:r>')
            content = merge_adjacent_runs(content)
            new_runs = content.count('<w:r>')
            if original_runs != new_runs:
                print(f"    ✓ Merged runs: {original_runs} → {new_runs}")
        
        # Pretty print
        if pretty:
            content = pretty_print_xml(content)
        
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    print(f"✅ Распаковано в: {output_dir}")
    print(f"   Основной файл: {output_dir}/word/document.xml")
    
    # Статистика
    doc_xml = output_dir / 'word' / 'document.xml'
    if doc_xml.exists():
        with open(doc_xml, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tables = content.count('<w:tbl>')
        paragraphs = content.count('<w:p>')
        print(f"   Таблиц: {tables}, Параграфов: {paragraphs}")


def main():
    if len(sys.argv) < 3:
        print("Использование: python unpack.py <input.docx> <output_dir>")
        print("Опции:")
        print("  --no-merge    Не объединять split runs")
        print("  --no-pretty   Не форматировать XML")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    merge_runs = '--no-merge' not in sys.argv
    pretty = '--no-pretty' not in sys.argv
    
    unpack_docx(input_path, output_dir, merge_runs, pretty)


if __name__ == '__main__':
    main()
