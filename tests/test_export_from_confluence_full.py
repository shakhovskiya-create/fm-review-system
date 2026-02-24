"""
Comprehensive unit tests for export_from_confluence.py.
Target: 95-100% coverage. Mocks external deps (weasyprint, subprocess, API).
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import export_from_confluence as mod


# ── _get_page_id (additional coverage) ──────────────────────────────────────

class TestGetPageIdFull:
    def test_returns_first_digit_line_from_project_file(self):
        """When project file exists with valid ID, returns it."""
        with patch("export_from_confluence.os.path.dirname", return_value="/fake/scripts"):
            with patch("export_from_confluence.os.path.abspath", return_value="/fake/scripts/x.py"):
                with patch("export_from_confluence.os.path.join", side_effect=lambda *a: "/fake/projects/PROJ/CONFLUENCE_PAGE_ID"):
                    with patch("export_from_confluence.os.path.isfile", return_value=True):
                        with patch("builtins.open", mock_open(read_data="77777777\n")):
                            result = mod._get_page_id("PROJ")
        assert result == "77777777"

    def test_skips_comments_and_empty_lines(self):
        with patch("export_from_confluence.os.path.dirname", return_value="/fake/scripts"):
            with patch("export_from_confluence.os.path.abspath", return_value="/fake/scripts/x.py"):
                with patch("export_from_confluence.os.path.join", side_effect=lambda *a: "/fake/projects/PROJ/CONFLUENCE_PAGE_ID"):
                    with patch("export_from_confluence.os.path.isfile", return_value=True):
                        with patch("builtins.open", mock_open(read_data="# comment\n\n\n12345678\n")):
                            result = mod._get_page_id("PROJ")
        assert result == "12345678"

    def test_skips_non_digit_lines(self):
        with patch("export_from_confluence.os.path.dirname", return_value="/fake/scripts"):
            with patch("export_from_confluence.os.path.abspath", return_value="/fake/scripts/x.py"):
                with patch("export_from_confluence.os.path.join", side_effect=lambda *a: "/fake/projects/PROJ/CONFLUENCE_PAGE_ID"):
                    with patch("export_from_confluence.os.path.isfile", return_value=True):
                        with patch("builtins.open", mock_open(read_data="abc\n99999999\n")):
                            result = mod._get_page_id("PROJ")
        assert result == "99999999"


# ── _make_ssl_context ──────────────────────────────────────────────────────

class TestMakeSslContext:
    def test_verify_mode_is_none(self):
        ctx = mod._make_ssl_context()
        assert ctx.verify_mode == 0  # ssl.CERT_NONE


# ── setup_weasyprint_env ────────────────────────────────────────────────────

class TestSetupWeasyprintEnv:
    def test_skips_when_not_darwin(self):
        with patch.object(sys, "platform", "linux"):
            mod.setup_weasyprint_env()  # no-op, no side effects

    def test_skips_when_dyld_already_set(self):
        with patch.object(sys, "platform", "darwin"):
            with patch.dict(os.environ, {"DYLD_LIBRARY_PATH": "/existing"}, clear=False):
                mod.setup_weasyprint_env()

    def test_execve_when_darwin_and_homebrew_lib_exists(self):
        with patch.object(sys, "platform", "darwin"):
            with patch.dict(os.environ, {}, clear=True):
                env = os.environ.copy()
                env.pop("DYLD_LIBRARY_PATH", None)
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(os.path, "isdir", return_value=True):
                        with patch.object(os, "execve", side_effect=SystemExit):
                            with pytest.raises(SystemExit):
                                mod.setup_weasyprint_env()


# ── _urlopen_with_retry ─────────────────────────────────────────────────────

class TestUrlopenWithRetry:
    def test_returns_response_on_success(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("export_from_confluence.urllib.request.urlopen", return_value=mock_resp):
            result = mod._urlopen_with_retry(MagicMock())
        assert result is mock_resp


# ── api_request (error path) ────────────────────────────────────────────────

class TestApiRequestFull:
    @patch("export_from_confluence._urlopen_with_retry", side_effect=Exception("network"))
    def test_prints_and_returns_none_on_error(self, mock_urlopen, capsys):
        result = mod.api_request("GET", "content/1")
        assert result is None
        out, _ = capsys.readouterr()
        assert "API error" in out or "network" in out


# ── fetch_page ──────────────────────────────────────────────────────────────

class TestFetchPage:
    def test_returns_page_data_on_success(self):
        data = {
            "title": "Test Page",
            "version": {"number": 5},
            "body": {"storage": {"value": "<p>Content</p>"}},
        }
        with patch.object(mod, "api_request", return_value=data):
            with patch.object(mod, "PAGE_ID", "123"):
                result = mod.fetch_page("456")
        assert result["title"] == "Test Page"
        assert result["version"] == 5
        assert result["html"] == "<p>Content</p>"

    def test_uses_page_id_when_provided(self):
        data = {"title": "X", "version": {"number": 1}, "body": {"storage": {"value": ""}}}
        with patch.object(mod, "api_request", return_value=data) as mock_api:
            mod.fetch_page("999")
        mock_api.assert_called_once()
        assert "content/999" in str(mock_api.call_args)

    def test_exits_when_api_fails(self):
        with patch.object(mod, "api_request", return_value=None):
            with patch.object(sys, "exit", side_effect=SystemExit):
                with pytest.raises(SystemExit):
                    mod.fetch_page("1")


# ── confluence_to_clean_html (edge cases) ────────────────────────────────────

class TestConfluenceToCleanHtmlFull:
    def test_unknown_macro_with_body_replaces_with_body(self):
        xhtml = '''<ac:structured-macro ac:name="unknown">
            <ac:rich-text-body><p>Body content</p></ac:rich-text-body>
        </ac:structured-macro>'''
        result = mod.confluence_to_clean_html(xhtml, "T")
        assert "Body content" in result

    def test_unknown_macro_without_body_decomposes(self):
        xhtml = '''<ac:structured-macro ac:name="unknown"></ac:structured-macro>
        <p>After</p>'''
        result = mod.confluence_to_clean_html(xhtml, "T")
        assert "After" in result

    def test_unwraps_ac_elements_with_string_content(self):
        xhtml = '<ac:parameter ac:name="x">value</ac:parameter><p>p</p>'
        result = mod.confluence_to_clean_html(xhtml, "T")
        assert "value" in result

    def test_decomposes_ri_elements(self):
        xhtml = '<ri:attachment ri:filename="x.pdf"/><p>text</p>'
        result = mod.confluence_to_clean_html(xhtml, "T")
        assert "text" in result


# ── export_pdf ──────────────────────────────────────────────────────────────

class TestExportPdf:
    def test_success_when_weasyprint_available(self, tmp_path):
        pdf_path = tmp_path / "out.pdf"
        mock_html = MagicMock()
        with patch.dict("sys.modules", {"weasyprint": MagicMock(HTML=mock_html)}):
            with patch("export_from_confluence.weasyprint", MagicMock(HTML=mock_html), create=True):
                with patch("export_from_confluence.HTML", mock_html, create=True):
                    result = mod.export_pdf("<html></html>", str(pdf_path))
        assert result is True

    def test_returns_false_on_import_error(self, tmp_path):
        with patch.dict("sys.modules", {"weasyprint": None}):
            try:
                del sys.modules["weasyprint"]
            except KeyError:
                pass
        with patch("builtins.__import__", side_effect=ImportError("no weasyprint")):
            result = mod.export_pdf("<html></html>", str(tmp_path / "x.pdf"))
        assert result is False

    def test_returns_false_on_generic_exception(self, tmp_path):
        mock_html = MagicMock()
        mock_html.return_value.write_pdf.side_effect = RuntimeError("weasyprint failed")
        with patch("builtins.__import__", return_value=MagicMock(HTML=mock_html)):
            result = mod.export_pdf("<html></html>", str(tmp_path / "x.pdf"))
        assert result is False


# ── export_docx ─────────────────────────────────────────────────────────────

class TestExportDocx:
    def test_creates_docx_with_basic_content(self, tmp_path):
        html = "<h1>Title</h1><p>Paragraph</p>"
        path = tmp_path / "out.docx"
        result = mod.export_docx(html, "Doc Title", str(path))
        assert result is True
        assert path.exists()

    def test_handles_headings_h1_to_h4(self, tmp_path):
        html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3><h4>H4</h4>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_bold_and_italic(self, tmp_path):
        html = "<p>Normal <strong>bold</strong> and <em>italic</em></p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_table(self, tmp_path):
        html = """<table><tr><th>H1</th><th>H2</th></tr>
        <tr><td>A</td><td>B</td></tr></table>"""
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_table_with_background_color(self, tmp_path):
        html = """<table><tr><td style="background-color: #FF0000">Red</td></tr></table>"""
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_panels_warning_note_info(self, tmp_path):
        html = """<div class="panel-warning">Warn</div>
        <div class="panel-note">Note</div>
        <div class="panel-info">Info</div>"""
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_ul_and_ol(self, tmp_path):
        html = "<ul><li>Item1</li><li>Item2</li></ul><ol><li>First</li></ol>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_hr(self, tmp_path):
        html = "<p>Before</p><hr/><p>After</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_br_in_paragraph(self, tmp_path):
        html = "<p>Line1<br/>Line2</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_span_and_anchor(self, tmp_path):
        html = "<p><span>Span</span> <a href='#'>Link</a></p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_empty_table(self, tmp_path):
        html = "<table></table><p>After</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_table_with_empty_rows(self, tmp_path):
        html = "<table><tr></tr></table><p>x</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_regular_div(self, tmp_path):
        html = "<div><p>Inside div</p></div>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_panel_with_string_class(self, tmp_path):
        html = '<div class="panel-warning">W</div>'
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_nested_bold_and_italic_in_paragraph(self, tmp_path):
        html = "<p>Text <strong>bold <em>bold-italic</em></strong> end</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_section_article_body_elements(self, tmp_path):
        html = "<section><article><p>S</p></article></section><main><p>M</p></main><tbody><tr><td>X</td></tr></tbody>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_paragraph_with_empty_text_skipped(self, tmp_path):
        html = "<p>   </p><p>Real</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_nested_em_inside_strong(self, tmp_path):
        html = "<p>X<strong>B<em>BI</em></strong>Y</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_span_with_nested_element(self, tmp_path):
        html = "<p><span><em>nested</em></span></p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()

    def test_handles_sub_sup_other_inline(self, tmp_path):
        html = "<p>H<sub>2</sub>O</p>"
        path = tmp_path / "out.docx"
        mod.export_docx(html, "T", str(path))
        assert path.exists()


# ── main ────────────────────────────────────────────────────────────────────

class TestMain:
    def test_exits_when_no_token(self):
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": ""}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(sys, "exit", side_effect=SystemExit):
                    with pytest.raises(SystemExit):
                        mod.main()

    def test_help_exits_zero(self):
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "x"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(sys, "argv", ["script", "--help"]):
                    with patch.object(sys, "exit", side_effect=SystemExit):
                        with pytest.raises(SystemExit):
                            mod.main()

    def test_full_flow_pdf_and_docx(self, tmp_path, capsys):
        page_data = {
            "title": "Test FM",
            "version": 1,
            "html": "<p>Content</p>",
        }
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "tok", "CONFLUENCE_URL": "https://x"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_pdf", return_value=True):
                        with patch.object(mod, "export_docx", return_value=True):
                            with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                                with patch.object(mod, "_get_page_id", return_value="123"):
                                    with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                        mod.main()
        out, _ = capsys.readouterr()
        assert "FM EXPORTER" in out
        assert "Test FM" in out

    def test_full_flow_pdf_only(self, tmp_path):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_pdf", return_value=True):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", return_value="1"):
                                with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                    with patch.object(sys, "argv", ["script", "--pdf"]):
                                        mod.main()

    def test_full_flow_docx_only(self, tmp_path):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_docx", return_value=True):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", return_value="1"):
                                with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                    with patch.object(sys, "argv", ["script", "--docx"]):
                                        mod.main()

    def test_parses_page_arg(self, tmp_path):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data) as mock_fetch:
                    with patch.object(mod, "export_pdf", return_value=True):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", return_value="1"):
                                with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                    with patch.object(sys, "argv", ["script", "--page=999", "--pdf"]):
                                        mod.main()
        mock_fetch.assert_called_once_with("999")

    def test_parses_project_arg(self, tmp_path):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_pdf", return_value=True):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", side_effect=lambda p: "888" if p == "PROJ" else "1"):
                                with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                    with patch.object(sys, "argv", ["script", "--project=PROJ", "--pdf"]):
                                        mod.main()

    def test_both_flag_exports_pdf_and_docx(self, tmp_path):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_pdf", return_value=True):
                        with patch.object(mod, "export_docx", return_value=True):
                            with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                                with patch.object(mod, "_get_page_id", return_value="1"):
                                    with patch("export_from_confluence.os.path.getsize", return_value=1024):
                                        with patch.object(sys, "argv", ["script", "--both"]):
                                            mod.main()

    def test_pdf_error_path_prints_error(self, tmp_path, capsys):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_pdf", return_value=False):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", return_value="1"):
                                with patch.object(sys, "argv", ["script", "--pdf"]):
                                    mod.main()
        out, _ = capsys.readouterr()
        assert "ОШИБКА" in out or "PDF" in out

    def test_docx_error_path_prints_error(self, tmp_path, capsys):
        page_data = {"title": "X", "version": 1, "html": "<p>x</p>"}
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "t"}, clear=False):
            with patch.object(mod, "setup_weasyprint_env"):
                with patch.object(mod, "fetch_page", return_value=page_data):
                    with patch.object(mod, "export_docx", return_value=False):
                        with patch.object(mod, "OUTPUT_DIR", str(tmp_path)):
                            with patch.object(mod, "_get_page_id", return_value="1"):
                                with patch.object(sys, "argv", ["script", "--docx"]):
                                    mod.main()
        out, _ = capsys.readouterr()
        assert "ОШИБКА" in out or "Word" in out


# ── __main__ block ──────────────────────────────────────────────────────────

class TestMainBlock:
    def test_main_called_when_run_as_script(self):
        """if __name__ == '__main__' calls main(). runpy covers __main__ block in-process."""
        import runpy
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "x"}, clear=False):
            with patch.object(sys, "argv", ["export_from_confluence.py", "--help"]):
                with pytest.raises(SystemExit):
                    runpy.run_path(str(SCRIPTS_DIR / "export_from_confluence.py"), run_name="__main__")
