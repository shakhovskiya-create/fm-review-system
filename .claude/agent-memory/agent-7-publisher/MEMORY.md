# Agent 7 (Publisher) Memory

## Active Projects
- PROJECT_SHPMNT_PROFIT: PAGE_ID=83951683

## Confluence API
- Base URL: https://confluence.ekf.su
- Auth: Bearer token (CONFLUENCE_TOKEN env var)
- Publishing uses ConfluenceClient from fm_review.confluence_utils
- FC-01: lock + backup + retry on every write
- FC-12B: agent_name="Agent7_Publisher" in audit log

## Publishing Modes
1. **--from-file** (primary): reads pre-built XHTML, publishes to Confluence
2. **docx import** (legacy): parses .docx, converts to XHTML, publishes

## XHTML Rules
- Sanitize via fm_review.xhtml_sanitizer before publishing
- No script/iframe tags, no event handlers, no javascript: URLs
- Allowed macros: warning, note, info, tip, expand, toc, code, panel
- Tables: class="confluenceTable", headers with #f4f5f7 background
- No blue header color (rgb 59,115,175 = prohibited)
- Author: "Shahovsky A.S." — never mention AI/Agent

## Version Management
- FM_VERSION always "1.0.0" in script (meta-table override)
- Real version tracked via fm_version.sh and Confluence version history
- Version message passed via --message flag

## Common Issues
- Lock timeout: another agent writing — retry after 30s
- SSL: custom CA may need _make_ssl_context() from confluence_utils
- Rate limit: Confluence Server has no explicit rate limit but respect 429
