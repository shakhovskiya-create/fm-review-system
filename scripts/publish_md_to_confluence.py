#!/usr/bin/env python3
"""
Publish Markdown files to Confluence as new pages.

Usage:
  python3 scripts/publish_md_to_confluence.py --title "Page Title" --file path/to/file.md \
    --space EW --parent 86048852 [--dry-run]

Converts Markdown to Confluence storage format (XHTML) and creates a new page.
"""

import argparse
import json
import os
import re
import ssl
import sys

import markdown
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension

# Load secrets
CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "https://confluence.ekf.su")
CONFLUENCE_TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")


def md_to_confluence_xhtml(md_text: str) -> str:
    """Convert markdown to Confluence storage format XHTML."""
    # Pre-process: remove markdown TOC links (they don't work in Confluence)
    md_text = re.sub(r'\[([^\]]+)\]\(#[^)]+\)', r'\1', md_text)

    # Convert to HTML
    html = markdown.markdown(
        md_text,
        extensions=[
            TableExtension(),
            FencedCodeExtension(),
            TocExtension(permalink=False),
        ],
        output_format='xhtml'
    )

    # Post-process for Confluence
    html = postprocess_for_confluence(html)

    return html


def postprocess_for_confluence(html: str) -> str:
    """Apply Confluence-specific transformations."""

    # 1. Add warm yellow background to table headers
    # Match <th> but not <thead>
    html = re.sub(
        r'<th(?=[\s>])',
        r'<th style="background-color: rgb(255,250,230);"',
        html
    )

    # 2. Wrap code blocks in Confluence macro
    def replace_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        # Map common language names
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

    # Match <pre><code class="language-X">...</code></pre> or <pre><code>...</code></pre>
    html = re.sub(
        r'<pre><code(?:\s+class="language-([^"]*)")?>(.*?)</code></pre>',
        replace_code_block,
        html,
        flags=re.DOTALL
    )

    # Also handle inline <code> → {{code}} style (Confluence macro)
    # Actually, <code> is fine in Confluence storage format, leave as-is

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

    # 4. Convert <h1>...<h6> to have anchor IDs for cross-references
    def add_anchor(match):
        tag = match.group(1)
        text = match.group(2)
        # Create anchor ID from text (transliterate Russian)
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


def create_confluence_page(space_key: str, title: str, content: str, parent_id: str = None) -> dict:
    """Create a new Confluence page via REST API."""
    import urllib.request

    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": content,
                "representation": "storage"
            }
        }
    }

    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        f"{CONFLUENCE_URL}/rest/api/content",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        },
        method="POST"
    )

    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            result = json.loads(resp.read().decode('utf-8'))
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


def main():
    parser = argparse.ArgumentParser(description="Publish Markdown to Confluence")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--file", required=True, help="Markdown file path")
    parser.add_argument("--space", default="EW", help="Confluence space key")
    parser.add_argument("--parent", help="Parent page ID")
    parser.add_argument("--dry-run", action="store_true", help="Print XHTML without publishing")
    parser.add_argument("--version-message", help="Version history message")
    args = parser.parse_args()

    # Read markdown file
    with open(args.file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert to Confluence XHTML
    xhtml = md_to_confluence_xhtml(md_content)

    if args.dry_run:
        print(f"=== XHTML for '{args.title}' ({len(xhtml)} chars) ===")
        print(xhtml[:2000])
        print(f"\n... ({len(xhtml)} total chars)")
        return

    # Check token
    if not CONFLUENCE_TOKEN:
        print("ERROR: CONFLUENCE_TOKEN not set. Run: source scripts/load-secrets.sh", file=sys.stderr)
        sys.exit(1)

    # Create page
    print(f"Creating page '{args.title}' in space {args.space}...")
    result = create_confluence_page(args.space, args.title, xhtml, args.parent)

    print(f"Created: {result['url']} (ID: {result['id']}, version: {result['version']})")
    # Output JSON for automation
    print(json.dumps(result))


if __name__ == "__main__":
    main()
