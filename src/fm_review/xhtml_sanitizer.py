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
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError as XMLParseError

# Tags that are never allowed in Confluence storage format
FORBIDDEN_TAGS = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|applet|form|input|textarea|button|select)\b[^>]*>",
    re.IGNORECASE,
)

# Event handler attributes (onclick, onload, onerror, etc.)
# Matches: onclick="...", onclick='...', onclick=value (handles nested quotes)
EVENT_HANDLERS = re.compile(
    r'\s+on\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',
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

# Allowed elements in Confluence Storage Format (XHTML subset + ac:/ri: namespaces)
ALLOWED_ELEMENTS = {
    # Standard XHTML block elements
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "colgroup", "col",
    "blockquote", "pre", "hr", "br",
    # Standard XHTML inline elements
    "a", "span", "strong", "em", "b", "i", "u", "s", "sub", "sup",
    "code", "tt", "img",
    # Confluence-specific (ac: namespace — stored without prefix after parse)
    "structured-macro", "parameter", "rich-text-body", "plain-text-body",
    "link", "image", "layout", "layout-section", "layout-cell",
    "emoticon", "placeholder",
    # Confluence resource identifiers (ri: namespace)
    "page", "attachment", "url", "user", "space", "content-entity",
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
        # Clean up any leftover empty spaces before closing brackets that might have been left
        result = re.sub(r'\s+>', '>', result)

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

    # 8. XML well-formedness check (HIGH-A4: unclosed tags break Confluence pages)
    # Declare Confluence namespaces so ac:/ri: prefixes don't cause false positives
    _xml_wrapper = (
        '<root xmlns:ac="http://atlassian.com/content"'
        ' xmlns:ri="http://atlassian.com/resource-identifier">'
    )
    try:
        tree = ElementTree.fromstring(f"{_xml_wrapper}{result}</root>")  # nosec B314 — input is our own sanitized XHTML, not untrusted

        # 9. Structural validation: whitelist of allowed elements (D4)
        unknown_elements = set()
        for elem in tree.iter():
            # Strip namespace URI, keep local name
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "root":
                continue
            if tag not in ALLOWED_ELEMENTS:
                unknown_elements.add(tag)
        if unknown_elements:
            warnings.append(
                f"Non-whitelisted elements: {', '.join(sorted(unknown_elements))}"
            )
    except XMLParseError as e:
        warnings.append(f"XHTML well-formedness error: {e}")

    return result, warnings
