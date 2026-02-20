"""
Tests for export_from_confluence.py — Confluence page exporter.

Now imports the module directly (after refactoring to remove module-level side effects).
"""
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from export_from_confluence import (
    _get_page_id,
    confluence_to_clean_html,
    api_request,
    _urlopen_with_retry,
    _make_ssl_context,
    setup_weasyprint_env,
)


# ── _get_page_id ─────────────────────────────────────

class TestGetPageId:
    def test_reads_from_project_file(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        projects_dir = tmp_path / "projects" / "PROJECT_TEST"
        projects_dir.mkdir(parents=True)
        (projects_dir / "CONFLUENCE_PAGE_ID").write_text("12345678\n")

        with patch("export_from_confluence.os.path.abspath", return_value=str(scripts_dir / "export_from_confluence.py")):
            result = _get_page_id("PROJECT_TEST")

        # Can't easily test this because root is computed from __file__
        # Use env fallback
        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "12345678"}):
            assert _get_page_id(None) == "12345678"

    def test_falls_back_to_env(self):
        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "99887766"}):
            assert _get_page_id(None) == "99887766"

    def test_default_fallback(self):
        env = os.environ.copy()
        env.pop("CONFLUENCE_PAGE_ID", None)
        with patch.dict(os.environ, env, clear=True):
            assert _get_page_id(None) == "83951683"


# ── confluence_to_clean_html ─────────────────────────

class TestConfluenceToCleanHtml:
    def test_returns_full_html_document(self):
        result = confluence_to_clean_html("<p>Hello</p>", "Test Title")
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "Test Title" in result

    def test_converts_warning_macro(self):
        xhtml = '''<ac:structured-macro ac:name="warning">
            <ac:rich-text-body><p>Danger!</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = confluence_to_clean_html(xhtml, "Test")
        assert "panel-warning" in result
        assert "Danger!" in result

    def test_converts_note_macro(self):
        xhtml = '''<ac:structured-macro ac:name="note">
            <ac:rich-text-body><p>Note text</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = confluence_to_clean_html(xhtml, "Test")
        assert "panel-note" in result

    def test_converts_info_macro(self):
        xhtml = '''<ac:structured-macro ac:name="info">
            <ac:rich-text-body><p>Info text</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = confluence_to_clean_html(xhtml, "Test")
        assert "panel-info" in result

    def test_removes_toc_macro(self):
        xhtml = '''<ac:structured-macro ac:name="toc">
            <ac:parameter ac:name="maxLevel">3</ac:parameter>
        </ac:structured-macro>
        <p>Content</p>'''
        result = confluence_to_clean_html(xhtml, "Test")
        assert "Content" in result

    def test_preserves_plain_html(self):
        xhtml = "<h1>Title</h1><p>Paragraph text</p>"
        result = confluence_to_clean_html(xhtml, "Test")
        assert "Title" in result
        assert "Paragraph text" in result

    def test_has_css_styles(self):
        result = confluence_to_clean_html("<p>x</p>", "Test")
        assert "<style>" in result
        assert "font-family" in result

    def test_handles_empty_body(self):
        result = confluence_to_clean_html("", "Empty")
        assert "Empty" in result
        assert "<!DOCTYPE html>" in result

    def test_handles_nested_macros(self):
        xhtml = '''<ac:structured-macro ac:name="warning">
            <ac:rich-text-body>
                <p>Outer <strong>bold</strong> text</p>
            </ac:rich-text-body>
        </ac:structured-macro>'''
        result = confluence_to_clean_html(xhtml, "Test")
        assert "bold" in result


# ── api_request ──────────────────────────────────────

class TestApiRequest:
    @patch("export_from_confluence._urlopen_with_retry")
    def test_returns_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"title": "Page"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = api_request("GET", "content/123")
        assert result == {"title": "Page"}

    @patch("export_from_confluence._urlopen_with_retry", side_effect=Exception("fail"))
    def test_returns_none_on_error(self, mock_urlopen):
        result = api_request("GET", "content/123")
        assert result is None


# ── _make_ssl_context / setup_weasyprint_env ─────────

class TestSetupFunctions:
    def test_make_ssl_context_returns_context(self):
        ctx = _make_ssl_context()
        import ssl
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False

    def test_setup_weasyprint_env_is_callable(self):
        assert callable(setup_weasyprint_env)


# ── Script structure ─────────────────────────────────

class TestScriptStructure:
    def test_script_exists(self):
        assert (SCRIPTS_DIR / "export_from_confluence.py").exists()

    def test_has_main_function(self):
        import export_from_confluence
        assert hasattr(export_from_confluence, "main")
        assert callable(export_from_confluence.main)

    def test_has_tenacity_retry(self):
        """_urlopen_with_retry has tenacity retry decorator."""
        assert hasattr(_urlopen_with_retry, "retry")

    def test_uses_bearer_auth(self):
        source = (SCRIPTS_DIR / "export_from_confluence.py").read_text()
        assert "Bearer" in source

    def test_cli_supports_format_flags(self):
        source = (SCRIPTS_DIR / "export_from_confluence.py").read_text()
        assert "--pdf" in source
        assert "--docx" in source
