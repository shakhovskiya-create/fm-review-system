#!/usr/bin/env python3
"""
XHTML Sanitizer for Confluence Storage Format.

Strips potentially dangerous or prohibited content from agent-generated XHTML
before publishing to Confluence:
  - JavaScript (script tags, event handlers, javascript: URLs)
  - External images/iframes that could exfiltrate data
  - AI/Agent mentions (per project policy: author = "Шаховский А.С.")
  - Invalid/unsupported Confluence macros

Usage:
    from fm_review.xhtml_sanitizer import sanitize_xhtml
    clean_body = sanitize_xhtml(raw_body)
"""

import re
from typing import Tuple

# Tags that are never allowed in Confluence storage format
FORBIDDEN_TAGS = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|applet|form|input|textarea|button|select)\b[^>]*>",
    re.IGNORECASE,
)

# Event handler attributes (onclick, onload, onerror, etc.)
EVENT_HANDLERS = re.compile(
    r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']",
    re.IGNORECASE,
)

# javascript: URLs in href/src attributes
JS_URLS = re.compile(
    r'(href|src|action)\s*=\s*["\']?\s*javascript\s*:',
    re.IGNORECASE,
)

# data: URLs (potential XSS vector, except safe image types)
DATA_URLS_UNSAFE = re.compile(
    r'(href|src)\s*=\s*["\']?\s*data\s*:(?!image/(png|jpeg|gif|svg\+xml))',
    re.IGNORECASE,
)

# AI/Agent/Bot mentions that should not appear in published content
AI_MENTIONS = re.compile(
    r"\b(Agent\s*[0-8]|Claude|GPT|ChatGPT|ИИ\s*агент|ИИ-агент|Bot|LLM|"
    r"сгенерировано\s+автоматически|generated\s+by\s+AI|artificial\s+intelligence)\b",
    re.IGNORECASE,
)

# Blue header color (prohibited per project style — should be warm yellow)
BLUE_HEADER = re.compile(
    r"rgb\s*\(\s*59\s*,\s*115\s*,\s*175\s*\)",
    re.IGNORECASE,
)

# Allowed Confluence macros
ALLOWED_MACROS = {
    "warning", "note", "info", "tip", "expand", "panel", "code",
    "toc", "children", "excerpt", "anchor", "section", "column",
    "status", "jira", "recently-updated", "page-tree",
}


def sanitize_xhtml(body: str) -> Tuple[str, list]:
    """
    Sanitize XHTML body for Confluence storage format.

    Args:
        body: Raw XHTML string

    Returns:
        Tuple of (sanitized_body, list_of_warnings)
    """
    warnings = []
    result = body

    # 1. Remove forbidden tags
    forbidden_found = FORBIDDEN_TAGS.findall(result)
    if forbidden_found:
        warnings.append(f"Removed forbidden tags: {', '.join(set(forbidden_found))}")
        result = FORBIDDEN_TAGS.sub("", result)

    # 2. Remove event handlers
    handlers_found = EVENT_HANDLERS.findall(result)
    if handlers_found:
        warnings.append(f"Removed {len(handlers_found)} event handler(s)")
        result = EVENT_HANDLERS.sub("", result)

    # 3. Remove javascript: URLs
    if JS_URLS.search(result):
        warnings.append("Removed javascript: URL(s)")
        result = JS_URLS.sub(r'\1=""', result)

    # 4. Remove unsafe data: URLs
    if DATA_URLS_UNSAFE.search(result):
        warnings.append("Removed unsafe data: URL(s)")
        result = DATA_URLS_UNSAFE.sub(r'\1=""', result)

    # 5. Check for AI mentions (warn but don't remove — may be in legitimate context)
    ai_found = AI_MENTIONS.findall(result)
    if ai_found:
        unique = sorted(set(m if isinstance(m, str) else m[0] for m in ai_found))
        warnings.append(f"AI/Agent mentions detected: {', '.join(unique)}")

    # 6. Check blue header color
    if BLUE_HEADER.search(result):
        warnings.append("Prohibited blue header color rgb(59,115,175) found — should be rgb(255,250,230)")

    # 7. Check for unknown Confluence macros
    macros = re.findall(r'ac:name="([^"]+)"', result)
    unknown = [m for m in macros if m not in ALLOWED_MACROS]
    if unknown:
        warnings.append(f"Unknown Confluence macros: {', '.join(sorted(set(unknown)))}")

    return result, warnings
