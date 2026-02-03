#!/usr/bin/env python3
"""
Batch DOCX XML Replacements
Массовые замены текста в document.xml с поддержкой tracked changes.

Использование:
    python batch_replace.py <document.xml> [--tracked] [--dry-run]
    
Или импортировать как модуль:
    from batch_replace import batch_replace, add_comment
"""

import re
import sys
import shutil
from datetime import datetime
from pathlib import Path


# === КОНФИГУРАЦИЯ ===
AUTHOR = "Claude"


def get_next_id(content):
    """Находит максимальный w:id и возвращает следующий"""
    ids = re.findall(r'w:id="(\d+)"', content)
    return max(int(i) for i in ids) + 1 if ids else 1


def escape_xml(text):
    """Экранирует специальные XML символы"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x2019;"))


def make_tracked_change(old_text, new_text, del_id, ins_id, rPr=""):
    """
    Создаёт XML для tracked change с сохранением форматирования.
    
    Args:
        old_text: исходный текст
        new_text: новый текст
        del_id: ID для w:del
        ins_id: ID для w:ins
        rPr: содержимое <w:rPr> (без тегов)
    """
    date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    rPr_block = f"<w:rPr>{rPr}</w:rPr>" if rPr else ""
    
    old_escaped = escape_xml(old_text)
    new_escaped = escape_xml(new_text)
    
    return (
        f'<w:del w:id="{del_id}" w:author="{AUTHOR}" w:date="{date}">'
        f'<w:r>{rPr_block}<w:delText>{old_escaped}</w:delText></w:r>'
        f'</w:del>'
        f'<w:ins w:id="{ins_id}" w:author="{AUTHOR}" w:date="{date}">'
        f'<w:r>{rPr_block}<w:t>{new_escaped}</w:t></w:r>'
        f'</w:ins>'
    )


def batch_replace(xml_path, replacements, use_tracked=True, dry_run=False):
    """
    Выполняет массовые замены в XML файле.
    
    Args:
        xml_path: путь к document.xml
        replacements: список кортежей (old_text, new_text)
        use_tracked: использовать tracked changes
        dry_run: только показать что будет изменено, не менять файл
    
    Returns:
        list of (old_text, new_text, count) - выполненные замены
    """
    xml_path = Path(xml_path)
    
    if not xml_path.exists():
        print(f"❌ Файл не найден: {xml_path}")
        return []
    
    # Бэкап
    backup_path = xml_path.with_suffix('.xml.backup')
    if not dry_run:
        shutil.copy(xml_path, backup_path)
        print(f"✓ Бэкап: {backup_path}")
    
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    next_id = get_next_id(content)
    results = []
    
    for old_text, new_text in replacements:
        if not old_text:
            continue
            
        # Паттерн: ищем текст внутри <w:t>...</w:t>
        # Захватываем rPr если есть
        pattern = re.compile(
            r'(<w:r>\s*)'
            r'(<w:rPr>.*?</w:rPr>\s*)?'
            r'(<w:t(?:\s+[^>]*)?>)'
            rf'([^<]*?)({re.escape(old_text)})([^<]*?)'
            r'(</w:t>\s*</w:r>)',
            re.DOTALL
        )
        
        count = 0
        
        def replacer(m):
            nonlocal next_id, count
            r_open, rPr_full, t_open, before, matched, after, close = m.groups()
            
            # Извлекаем содержимое rPr
            rPr_content = ""
            if rPr_full:
                rPr_match = re.search(r'<w:rPr>(.*?)</w:rPr>', rPr_full, re.DOTALL)
                if rPr_match:
                    rPr_content = rPr_match.group(1)
            
            count += 1
            
            if use_tracked:
                result = ""
                
                # Текст до замены
                if before:
                    result += f'{r_open}{rPr_full or ""}{t_open}{before}</w:t></w:r>'
                
                # Tracked change
                result += make_tracked_change(matched, new_text, next_id, next_id + 1, rPr_content)
                next_id += 2
                
                # Текст после замены
                if after:
                    rPr_block = f"<w:rPr>{rPr_content}</w:rPr>" if rPr_content else ""
                    result += f'<w:r>{rPr_block}<w:t>{after}</w:t></w:r>'
                
                return result
            else:
                # Простая замена без tracked changes
                new_full = before + new_text + after
                return f'{r_open}{rPr_full or ""}{t_open}{new_full}{close}'
        
        new_content = pattern.sub(replacer, content)
        
        if count > 0:
            results.append((old_text, new_text, count))
            content = new_content
            status = "✓" if not dry_run else "→"
            print(f"  {status} '{old_text}' → '{new_text}': {count} замен")
        else:
            print(f"  ⚠ '{old_text}': НЕ НАЙДЕНО")
    
    # Сохраняем
    if not dry_run and results:
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    # Итоги
    total_changes = sum(r[2] for r in results)
    print(f"\n{'='*50}")
    if dry_run:
        print(f"[DRY RUN] Будет выполнено: {len(results)} типов замен, {total_changes} вхождений")
    else:
        print(f"Выполнено: {len(results)} типов замен, {total_changes} вхождений")
        if results:
            print(f"Сохранено: {xml_path}")
            print(f"Бэкап: {backup_path}")
    
    return results


def find_text(xml_path, search_text, context=50):
    """
    Ищет текст в XML и показывает контекст.
    Полезно для проверки перед заменой.
    """
    with open(xml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем в сыром XML
    pattern = re.compile(rf'.{{0,{context}}}{re.escape(search_text)}.{{0,{context}}}')
    matches = pattern.findall(content)
    
    print(f"Поиск '{search_text}': найдено {len(matches)} вхождений")
    for i, match in enumerate(matches[:10], 1):  # Показываем первые 10
        # Очищаем от XML тегов для читаемости
        clean = re.sub(r'<[^>]+>', '', match)
        print(f"  {i}. ...{clean}...")
    
    if len(matches) > 10:
        print(f"  ... и ещё {len(matches) - 10}")
    
    return len(matches)


def restore_backup(xml_path):
    """Восстанавливает файл из бэкапа"""
    xml_path = Path(xml_path)
    backup_path = xml_path.with_suffix('.xml.backup')
    
    if backup_path.exists():
        shutil.copy(backup_path, xml_path)
        print(f"✓ Восстановлено из: {backup_path}")
    else:
        print(f"❌ Бэкап не найден: {backup_path}")


# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python batch_replace.py <document.xml> [--tracked] [--dry-run]")
        print("  python batch_replace.py <document.xml> --find 'текст'")
        print("  python batch_replace.py <document.xml> --restore")
        print("")
        print("Или отредактируй REPLACEMENTS в скрипте и запусти без аргументов.")
        sys.exit(1)
    
    xml_path = sys.argv[1]
    
    # Команда --find
    if '--find' in sys.argv:
        idx = sys.argv.index('--find')
        if idx + 1 < len(sys.argv):
            find_text(xml_path, sys.argv[idx + 1])
        sys.exit(0)
    
    # Команда --restore
    if '--restore' in sys.argv:
        restore_backup(xml_path)
        sys.exit(0)
    
    # Замены
    use_tracked = '--tracked' in sys.argv or '--track' in sys.argv
    dry_run = '--dry-run' in sys.argv or '--dry' in sys.argv
    
    # === СПИСОК ЗАМЕН — ОТРЕДАКТИРУЙ ЭТО ===
    REPLACEMENTS = [
        # ("что найти", "на что заменить"),
        ("30 дней", "45 дней"),
        ("1С:ERP", "1С:ERP 2.5"),
        # Добавь свои замены...
    ]
    
    if not REPLACEMENTS or REPLACEMENTS == [("30 дней", "45 дней"), ("1С:ERP", "1С:ERP 2.5")]:
        print("⚠️  Отредактируй список REPLACEMENTS в скрипте!")
        print("    Или используй как модуль:")
        print("")
        print("    from batch_replace import batch_replace")
        print("    batch_replace('document.xml', [('old', 'new')], use_tracked=True)")
        sys.exit(1)
    
    print("Batch DOCX Replace")
    print("="*50)
    print(f"Файл: {xml_path}")
    print(f"Tracked changes: {'Да' if use_tracked else 'Нет'}")
    print(f"Dry run: {'Да' if dry_run else 'Нет'}")
    print("="*50)
    
    batch_replace(xml_path, REPLACEMENTS, use_tracked=use_tracked, dry_run=dry_run)
