#!/usr/bin/env python3
"""Check Технические ограничения in backup."""

import json
import re
from pathlib import Path

backup_file = Path("backups/FM-LS-PROFIT_v8_20260205_200346.json")

with open(backup_file) as f:
    data = json.load(f)

body = data.get("body", {}).get("storage", {}).get("value", "")

# Find section
tech_pos = body.find("<strong>Технические ограничения</strong>")
faq_pos = body.find("FAQ")

version = data.get("version", 0)
if isinstance(version, dict):
    version = version.get("number", 0)
print(f"Backup version: {version}")
print(f"Tech pos: {tech_pos}, FAQ pos: {faq_pos}")

if tech_pos > 0 and faq_pos > 0:
    section = body[tech_pos:faq_pos]
    clean = re.sub(r'<[^>]+>', '\n', section)
    clean = re.sub(r'\n+', '\n', clean).strip()

    print(f"\nSection length: {len(section)} chars")
    print("\n" + "=" * 60)
    print("CONTENT:")
    print("=" * 60)
    print(clean[:8000])
