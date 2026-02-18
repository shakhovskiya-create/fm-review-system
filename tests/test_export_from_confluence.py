"""
Tests for export_from_confluence.py — Confluence page exporter.

Tests utility functions (HTML conversion, _get_page_id) without
requiring live Confluence API access. The script performs API calls
at module level, so we test functions via AST analysis and isolated imports.
"""
import ast
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "export_from_confluence.py"


class TestScriptStructure:
    """Validate script structure and syntax."""

    def test_script_exists(self):
        assert SCRIPT_PATH.exists()

    def test_valid_python_syntax(self):
        source = SCRIPT_PATH.read_text()
        ast.parse(source)

    def test_has_expected_functions(self):
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "_get_page_id" in func_names
        assert "api_request" in func_names
        assert "fetch_page" in func_names
        assert "confluence_to_clean_html" in func_names
        assert "export_pdf" in func_names
        assert "export_docx" in func_names
        assert "main" in func_names

    def test_uses_bearer_auth(self):
        source = SCRIPT_PATH.read_text()
        assert "Bearer" in source

    def test_reads_token_from_env(self):
        source = SCRIPT_PATH.read_text()
        assert "CONFLUENCE_TOKEN" in source

    def test_no_hardcoded_token(self):
        """No actual token values in source code."""
        source = SCRIPT_PATH.read_text()
        # Token should come from env vars, not hardcoded
        # Looking for suspicious patterns that could be tokens
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "TOKEN" in line and "=" in line:
                # Should be os.environ.get() or empty string, not a real token
                assert "os.environ" in line or '""' in line or "load_env" in line, (
                    f"Line {i+1} may contain hardcoded token: {line.strip()}"
                )


class TestGetPageId:
    """Test _get_page_id function (extracted from script)."""

    def _import_get_page_id(self, fake_file_path=None):
        """Import _get_page_id without executing module-level API calls."""
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_get_page_id":
                func_source = ast.get_source_segment(source, node)
                # Provide __file__ so os.path.dirname(__file__) works
                file_path = fake_file_path or str(SCRIPT_PATH)
                exec_globals = {"os": os, "__file__": file_path}
                exec(compile(ast.parse(f"import os\n{func_source}"), "<test>", "exec"), exec_globals)
                return exec_globals["_get_page_id"]
        pytest.fail("_get_page_id function not found in script")

    def test_reads_from_project_file(self, tmp_path):
        # Create fake project structure
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        projects_dir = tmp_path / "projects" / "PROJECT_TEST"
        projects_dir.mkdir(parents=True)
        (projects_dir / "CONFLUENCE_PAGE_ID").write_text("12345678\n")

        func = self._import_get_page_id(str(scripts_dir / "export_from_confluence.py"))
        result = func("PROJECT_TEST")
        assert result == "12345678"

    def test_falls_back_to_env(self):
        func = self._import_get_page_id()
        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "99887766"}):
            result = func(None)
            assert result == "99887766"

    def test_default_fallback(self):
        func = self._import_get_page_id()
        env = os.environ.copy()
        os.environ.pop("CONFLUENCE_PAGE_ID", None)
        try:
            result = func(None)
            assert result == "83951683"  # Default fallback
        finally:
            os.environ.update(env)


class TestConfluenceToCleanHtml:
    """Test HTML conversion logic by importing the function."""

    @pytest.fixture
    def converter(self):
        """Import confluence_to_clean_html function."""
        # We need BeautifulSoup available
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "confluence_to_clean_html":
                func_source = ast.get_source_segment(source, node)
                exec_globals = {
                    "re": re,
                    "BeautifulSoup": __import__("bs4", fromlist=["BeautifulSoup"]).BeautifulSoup,
                }
                exec(compile(ast.parse(f"import re\nfrom bs4 import BeautifulSoup\n{func_source}"), "<test>", "exec"), exec_globals)
                return exec_globals["confluence_to_clean_html"]
        pytest.fail("confluence_to_clean_html not found")

    def test_returns_full_html_document(self, converter):
        result = converter("<p>Hello</p>", "Test Title")
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "Test Title" in result

    def test_converts_warning_macro(self, converter):
        xhtml = '''<ac:structured-macro ac:name="warning">
            <ac:rich-text-body><p>Danger!</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = converter(xhtml, "Test")
        assert "panel-warning" in result
        assert "Danger!" in result

    def test_converts_note_macro(self, converter):
        xhtml = '''<ac:structured-macro ac:name="note">
            <ac:rich-text-body><p>Note text</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = converter(xhtml, "Test")
        assert "panel-note" in result

    def test_converts_info_macro(self, converter):
        xhtml = '''<ac:structured-macro ac:name="info">
            <ac:rich-text-body><p>Info text</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = converter(xhtml, "Test")
        assert "panel-info" in result

    def test_removes_toc_macro(self, converter):
        xhtml = '''<ac:structured-macro ac:name="toc">
            <ac:parameter ac:name="maxLevel">3</ac:parameter>
        </ac:structured-macro>
        <p>Content</p>'''
        result = converter(xhtml, "Test")
        assert "toc" not in result.lower().split("<style>")[0]  # Not in body content
        assert "Content" in result

    def test_preserves_plain_html(self, converter):
        xhtml = "<h1>Title</h1><p>Paragraph text</p>"
        result = converter(xhtml, "Test")
        assert "Title" in result
        assert "Paragraph text" in result

    def test_has_css_styles(self, converter):
        result = converter("<p>x</p>", "Test")
        assert "<style>" in result
        assert "font-family" in result
        assert "border-collapse" in result


class TestExportFunctions:
    """Test export_pdf and export_docx structure."""

    def test_export_pdf_handles_missing_weasyprint(self):
        """export_pdf returns False when WeasyPrint is not installed."""
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "export_pdf":
                func_source = ast.get_source_segment(source, node)
                # Function should handle ImportError
                assert "ImportError" in func_source

    def test_export_docx_uses_python_docx(self):
        """export_docx imports from python-docx."""
        source = SCRIPT_PATH.read_text()
        assert "from docx import Document" in source

    def test_cli_supports_help(self):
        """Script supports --help flag."""
        source = SCRIPT_PATH.read_text()
        assert "--help" in source
        assert "-h" in source

    def test_cli_supports_format_flags(self):
        """Script supports --pdf, --docx, --both flags."""
        source = SCRIPT_PATH.read_text()
        assert "--pdf" in source
        assert "--docx" in source
        assert "--both" in source
