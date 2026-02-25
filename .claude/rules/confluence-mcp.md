---
globs: scripts/publish_to_confluence.py, scripts/export_from_confluence.py, src/fm_review/confluence_utils.py, .claude/agents/**
---

# Confluence MCP Tools

| Инструмент | Назначение | Кто использует |
|-----------|-----------|----------------|
| `confluence_get_page` | Прочитать страницу ФМ (XHTML) | Все агенты (0-8) |
| `confluence_update_page` | Обновить страницу (PUT) | Только Agent 7 |
| `confluence_create_page` | Создать новую страницу | Только Agent 7 |
| `confluence_search` | Поиск по Confluence | Все агенты |
| `confluence_get_comments` | Прочитать комментарии | Agent 3 (Defender) |
| `confluence_add_comment` | Добавить комментарий | Agent 3, Agent 7 |
| `confluence_get_labels` | Получить метки страницы | Agent 7 |
| `confluence_add_label` | Добавить метку | Agent 7 |
| `confluence_get_page_children` | Дочерние страницы | Agent 7 |

**Fallback:** REST API `https://confluence.ekf.su/rest/api/content/{PAGE_ID}`, Bearer token, `src/fm_review/confluence_utils.py`
