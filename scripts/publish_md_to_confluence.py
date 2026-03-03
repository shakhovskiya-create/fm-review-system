#!/usr/bin/env python3
"""
Publish Markdown files to Confluence as new or updated pages.

Usage:
  # Create new page:
  python3 scripts/publish_md_to_confluence.py --title "Page Title" --file path/to/file.md \
    --space EW --parent 86048852

  # Update existing page:
  python3 scripts/publish_md_to_confluence.py --title "Page Title" --file path/to/file.md \
    --page-id 86049879 --version-message "Updated cross-references"

  # Dry run (preview XHTML):
  python3 scripts/publish_md_to_confluence.py --title "Test" --file file.md --dry-run

Converts Markdown to Confluence storage format (XHTML) and creates/updates a page.
Features:
  - Strips manual "## Содержание" sections (Confluence TOC macro replaces them)
  - Converts cross-references (phase1a_domain_model.md etc.) to clickable Confluence links
  - Warm yellow table headers, collapsible TOC, code block macros
"""

import argparse
import json
import os
import re
import ssl
import sys
import urllib.request

import markdown
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension

# Load secrets
CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")

# Cross-reference mapping: filename → Confluence page ID
# Updated by publish runs; kept in sync with MEMORY.md
CROSS_REFS = {
    "phase1a_domain_model.md": ("86049881", "Phase 1A: Domain Model"),
    "phase1b_go_architecture.md": ("86049882", "Phase 1B: Go Architecture"),
    "phase1c_react_architecture.md": ("86049883", "Phase 1C: React Architecture"),
    "phase1d_ai_analytics.md": ("86049884", "Phase 1D: AI Analytics"),
    "phase1e_integration_architecture.md": ("86049885", "Phase 1E: Integration Architecture"),
    "TZ-GO-v1.0.md": ("86049879", "ТЗ Go+React"),
}

# Additional well-known page IDs
KNOWN_PAGES = {
    "83951683": "ФМ FM-LS-PROFIT",
    "86049548": "ТЗ 1С",
    "86049550": "Архитектура 1С",
    "86049879": "ТЗ Go+React",
    "86049880": "Архитектура Go+React",
}


def strip_manual_toc(md_text: str) -> str:
    """Remove manual '## Содержание' section from markdown.

    Matches from '## Содержание' until the next '## ' heading or '---' separator.
    The Confluence TOC macro replaces this.
    """
    # Pattern: ## Содержание followed by numbered list items, until next ## or ---
    pattern = r'^## Содержание\s*\n(?:(?!^## |^---).)*'
    return re.sub(pattern, '', md_text, flags=re.MULTILINE | re.DOTALL)


def linkify_cross_refs(md_text: str) -> str:
    """Replace file references with Confluence page links.

    Patterns handled:
    - `phase1a_domain_model.md` → clickable link
    - см. phase1a_domain_model.md → clickable link
    - phase1a, секция 5.1 → clickable link with section hint
    - PAGE_ID 83951683 → clickable link
    """
    for filename, (page_id, title) in CROSS_REFS.items():
        url = f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
        base = filename.replace('.md', '')

        # Pattern 1: `filename` (in backticks)
        md_text = md_text.replace(
            f'`{filename}`',
            f'[{title}]({url})'
        )

        # Pattern 2: bare filename (not in backticks, not already in link)
        md_text = re.sub(
            rf'(?<!\[)(?<!\()(?<!`){re.escape(filename)}(?!`|\))',
            f'[{title}]({url})',
            md_text
        )

        # Pattern 3: short name with section (e.g., "phase1a, секция 5.1")
        short = base.replace('_domain_model', '').replace('_go_architecture', '') \
                     .replace('_react_architecture', '').replace('_ai_analytics', '') \
                     .replace('_integration_architecture', '')
        _title, _url = title, url  # bind for lambda closure
        md_text = re.sub(
            rf'(?<!\[){re.escape(short)}(?:,\s*секци[яию]\s*[\d.]+)',
            lambda m, t=_title, u=_url: f'[{t}, {m.group(0).split(",", 1)[1].strip()}]({u})',
            md_text
        )

    # Pattern 4: PAGE_ID NNNN → clickable link
    for page_id, label in KNOWN_PAGES.items():
        url = f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
        md_text = re.sub(
            rf'PAGE_ID\s+{page_id}',
            f'[{label}]({url})',
            md_text
        )

    # Pattern 5: Confluence PAGE_ID NNNN
    md_text = re.sub(
        r'Confluence\s+PAGE_ID\s+(\d+)',
        lambda m: (
            f'[{KNOWN_PAGES.get(m.group(1), "Confluence")}]'
            f'({CONFLUENCE_URL}/pages/viewpage.action?pageId={m.group(1)})'
            if m.group(1) in KNOWN_PAGES
            else m.group(0)
        ),
        md_text
    )

    return md_text


def md_to_confluence_xhtml(md_text: str) -> str:
    """Convert markdown to Confluence storage format XHTML."""
    # Step 1: Strip manual TOC
    md_text = strip_manual_toc(md_text)

    # Step 2: Linkify cross-references
    md_text = linkify_cross_refs(md_text)

    # Step 3: Remove markdown TOC anchor links (they don't work in Confluence)
    md_text = re.sub(r'\[([^\]]+)\]\(#[^)]+\)', r'\1', md_text)

    # Step 4: Convert to HTML
    html = markdown.markdown(
        md_text,
        extensions=[
            TableExtension(),
            FencedCodeExtension(),
            TocExtension(permalink=False),
        ],
        output_format='xhtml'
    )

    # Step 5: Post-process for Confluence
    html = postprocess_for_confluence(html)

    return html


def postprocess_for_confluence(html: str) -> str:
    """Apply Confluence-specific transformations."""

    # 1. Add warm yellow background to table headers
    html = re.sub(
        r'<th(?=[\s>])',
        r'<th style="background-color: rgb(255,250,230);"',
        html
    )

    # 2. Wrap code blocks in Confluence macro
    def replace_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        lang_map = {
            'go': 'go', 'golang': 'go',
            'typescript': 'typescript', 'ts': 'typescript',
            'javascript': 'javascript', 'js': 'javascript',
            'python': 'python', 'py': 'python',
            'bash': 'bash', 'sh': 'bash', 'shell': 'bash',
            'sql': 'sql',
            'json': 'javascript',
            'yaml': 'yaml', 'yml': 'yaml',
            'xml': 'xml', 'html': 'xml',
            'proto': 'text', 'protobuf': 'text',
            'bsl': 'text', '1c': 'text',
            'text': 'text', 'plaintext': 'text', '': 'text',
        }
        conf_lang = lang_map.get(lang.lower(), 'text')
        return (
            f'<ac:structured-macro ac:name="code">'
            f'<ac:parameter ac:name="language">{conf_lang}</ac:parameter>'
            f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
            f'</ac:structured-macro>'
        )

    html = re.sub(
        r'<pre><code(?:\s+class="language-([^"]*)")?>(.*?)</code></pre>',
        replace_code_block,
        html,
        flags=re.DOTALL
    )

    # 3. Add collapsible TOC at the top
    toc_macro = (
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">Навигация по документу</ac:parameter>'
        '<ac:rich-text-body>'
        '<ac:structured-macro ac:name="toc">'
        '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
        '</ac:structured-macro>'
        '</ac:rich-text-body>'
        '</ac:structured-macro>'
    )
    html = toc_macro + '\n' + html

    # 4. Add anchor IDs to headings for cross-references
    def add_anchor(match):
        tag = match.group(1)
        text = match.group(2)
        anchor_id = re.sub(r'[^\w\s-]', '', text.lower())
        anchor_id = re.sub(r'[\s]+', '-', anchor_id).strip('-')
        anchor = (
            f'<ac:structured-macro ac:name="anchor">'
            f'<ac:parameter ac:name="">{anchor_id}</ac:parameter>'
            f'</ac:structured-macro>'
        )
        return f'{anchor}<{tag}>{text}</{tag}>'

    html = re.sub(r'<(h[1-6])>(.*?)</\1>', add_anchor, html)

    # 5. Fix horizontal rules
    html = html.replace('<hr />', '<hr/>')

    return html


def _api_request(url: str, data: bytes = None, method: str = "GET") -> dict:
    """Make authenticated Confluence REST API request."""
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        },
        method=method
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode('utf-8'))


def create_confluence_page(space_key: str, title: str, content: str,
                           parent_id: str = None) -> dict:
    """Create a new Confluence page via REST API."""
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": content, "representation": "storage"}}
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

    try:
        result = _api_request(
            f"{CONFLUENCE_URL}/rest/api/content",
            data=json.dumps(payload).encode('utf-8'),
            method="POST"
        )
        return {
            "id": result["id"],
            "title": result["title"],
            "url": f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={result['id']}",
            "version": result.get("version", {}).get("number", 1),
        }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"ERROR {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def update_confluence_page(page_id: str, title: str, content: str,
                           version_message: str = "") -> dict:
    """Update an existing Confluence page via REST API."""
    # Get current version
    try:
        current = _api_request(
            f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=version"
        )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"ERROR reading page {page_id}: {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)

    current_version = current["version"]["number"]

    payload = {
        "type": "page",
        "title": title,
        "body": {"storage": {"value": content, "representation": "storage"}},
        "version": {
            "number": current_version + 1,
            "message": version_message or "Updated via publish_md_to_confluence.py"
        }
    }

    try:
        result = _api_request(
            f"{CONFLUENCE_URL}/rest/api/content/{page_id}",
            data=json.dumps(payload).encode('utf-8'),
            method="PUT"
        )
        return {
            "id": result["id"],
            "title": result["title"],
            "url": f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={result['id']}",
            "version": result.get("version", {}).get("number", current_version + 1),
        }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"ERROR {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Publish Markdown to Confluence")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--file", required=True, help="Markdown file path")
    parser.add_argument("--space", default="EW", help="Confluence space key")
    parser.add_argument("--parent", help="Parent page ID (for create)")
    parser.add_argument("--page-id", help="Existing page ID (for update)")
    parser.add_argument("--dry-run", action="store_true", help="Print XHTML without publishing")
    parser.add_argument("--version-message", default="", help="Version history message")
    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    xhtml = md_to_confluence_xhtml(md_content)

    if args.dry_run:
        print(f"=== XHTML for '{args.title}' ({len(xhtml)} chars) ===")
        print(xhtml[:3000])
        print(f"\n... ({len(xhtml)} total chars)")
        return

    if not CONFLUENCE_TOKEN:
        print("ERROR: CONFLUENCE_TOKEN not set. Run: source scripts/load-secrets.sh",
              file=sys.stderr)
        sys.exit(1)

    if args.page_id:
        # Update existing page
        print(f"Updating page '{args.title}' (ID: {args.page_id})...")
        result = update_confluence_page(
            args.page_id, args.title, xhtml, args.version_message
        )
        print(f"Updated: {result['url']} (version: {result['version']})")
    else:
        # Create new page
        print(f"Creating page '{args.title}' in space {args.space}...")
        result = create_confluence_page(args.space, args.title, xhtml, args.parent)
        print(f"Created: {result['url']} (ID: {result['id']}, version: {result['version']})")

    print(json.dumps(result))


if __name__ == "__main__":
    main()
