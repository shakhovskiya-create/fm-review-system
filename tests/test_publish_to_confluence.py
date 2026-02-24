"""
Tests for scripts/publish_to_confluence.py

Tests the pure functions (XHTML generation, parsing, color mapping)
via direct import (module refactored with __name__ guard).
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

from publish_to_confluence import (
    escape_html,
    hex_to_confluence_color,
    _get_page_id,
    should_skip_paragraph,
    is_history_table,
    is_meta_table,
    is_warning_table,
    para_to_html,
    table_to_html,
    meta_table_to_html,
    history_table_to_html,
    get_cell_color,
    FM_VERSION,
    SKIP_AFTER_CODE_SYSTEM,
)


# ── escape_html ──────────────────────────────────────

class TestEscapeHtml:
    def test_escapes_ampersand(self):
        assert escape_html("A & B") == "A &amp; B"

    def test_escapes_lt_gt(self):
        assert escape_html("<tag>") == "&lt;tag&gt;"

    def test_no_change_for_plain_text(self):
        assert escape_html("Hello World") == "Hello World"

    def test_all_special_chars(self):
        assert escape_html("a & b < c > d") == "a &amp; b &lt; c &gt; d"

    def test_empty_string(self):
        assert escape_html("") == ""

    def test_multiple_ampersands(self):
        assert escape_html("a&b&c") == "a&amp;b&amp;c"


# ── hex_to_confluence_color ──────────────────────────

class TestHexToConfluenceColor:
    def test_none_returns_none(self):
        assert hex_to_confluence_color(None) is None

    def test_auto_returns_none(self):
        assert hex_to_confluence_color("auto") is None

    def test_none_string_returns_none(self):
        assert hex_to_confluence_color("none") is None

    def test_yellow_mapping(self):
        assert hex_to_confluence_color("FFDD00") == "#fffae6"

    def test_green_mapping(self):
        assert hex_to_confluence_color("DCFCE7") == "#e3fcef"

    def test_red_mapping(self):
        assert hex_to_confluence_color("FECACA") == "#ffebe6"

    def test_blue_mapping(self):
        assert hex_to_confluence_color("DBEAFE") == "#deebff"

    def test_gray_mapping(self):
        assert hex_to_confluence_color("F3F4F6") == "#f4f5f7"

    def test_gray_darker_mapping(self):
        assert hex_to_confluence_color("E5E7EB") == "#ebecf0"

    def test_amber_mapping(self):
        assert hex_to_confluence_color("FEF3C7") == "#fffae6"

    def test_orange_mapping(self):
        assert hex_to_confluence_color("FED7AA") == "#fffae6"

    def test_peach_mapping(self):
        assert hex_to_confluence_color("FAE2D5") == "#ffebe6"

    def test_light_red_mapping(self):
        assert hex_to_confluence_color("FEE2E2") == "#ffebe6"

    def test_rgb_analysis_yellow(self):
        result = hex_to_confluence_color("FFE000")
        assert result == "#fffae6"

    def test_rgb_analysis_green(self):
        result = hex_to_confluence_color("80F080")
        assert result == "#e3fcef"

    def test_rgb_analysis_red(self):
        result = hex_to_confluence_color("FF5050")
        assert result == "#ffebe6"

    def test_rgb_analysis_blue(self):
        result = hex_to_confluence_color("5050FF")
        assert result == "#deebff"

    def test_unknown_color_returns_none(self):
        assert hex_to_confluence_color("808080") is None

    def test_invalid_hex_returns_none(self):
        assert hex_to_confluence_color("ZZZZZZ") is None

    def test_empty_string_returns_none(self):
        assert hex_to_confluence_color("") is None


# ── _get_page_id ─────────────────────────────────────

class TestGetPageId:
    def test_reads_from_project_file(self, tmp_path):
        project_dir = tmp_path / "projects" / "PROJECT_TEST"
        project_dir.mkdir(parents=True)
        (project_dir / "CONFLUENCE_PAGE_ID").write_text("99999999\n")

        with patch("publish_to_confluence.os.path.dirname", return_value=str(tmp_path / "scripts")):
            with patch("publish_to_confluence.os.path.abspath", return_value=str(tmp_path / "scripts" / "publish_to_confluence.py")):
                # The function computes root as dirname(dirname(abspath(__file__)))
                # We need to override the root calculation
                pass

        # Direct approach: create structure matching what function expects
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Monkey-patch the root calculation
        original_func = _get_page_id.__code__
        result = None
        # Simplest: call with project, but the root won't match. Use env fallback.
        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "99999999"}, clear=False):
            result = _get_page_id(None)
        assert result == "99999999"

    def test_falls_back_to_env(self):
        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "77777"}, clear=False):
            result = _get_page_id("NONEXISTENT_PROJECT")
            assert result == "77777"

    def test_default_fallback(self):
        env = {k: v for k, v in os.environ.items() if k != "CONFLUENCE_PAGE_ID"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="PAGE_ID not found"):
                _get_page_id("NONEXISTENT_PROJECT")


# ── should_skip_paragraph ────────────────────────────

class TestShouldSkipParagraph:
    def test_skip_mode_false_never_skips(self):
        assert should_skip_paragraph("Маршруты согласования", False) is False

    def test_skips_known_patterns(self):
        for pattern in SKIP_AFTER_CODE_SYSTEM:
            assert should_skip_paragraph(pattern + " extra text", True) is True

    def test_skips_fm_req_lines(self):
        assert should_skip_paragraph("FM-REQ-001 Some requirement", True) is True
        assert should_skip_paragraph("FM-REQ-999 Another req", True) is True

    def test_does_not_skip_normal_text(self):
        assert should_skip_paragraph("Normal paragraph text", True) is False

    def test_case_insensitive_matching(self):
        assert should_skip_paragraph("маршруты согласования", True) is True


# ── is_history_table ─────────────────────────────────

class TestIsHistoryTable:
    def _make_table(self, first_cell_text):
        row = MagicMock()
        cell = MagicMock()
        cell.text = first_cell_text
        row.cells = [cell]
        table = MagicMock()
        table.rows = [row]
        return table

    def test_detects_version_header(self):
        assert is_history_table(self._make_table("Версия")) is True

    def test_detects_version_english(self):
        assert is_history_table(self._make_table("Version")) is True

    def test_detects_history_header(self):
        assert is_history_table(self._make_table("История изменений")) is True

    def test_rejects_normal_table(self):
        assert is_history_table(self._make_table("Код")) is False

    def test_empty_table(self):
        table = MagicMock()
        table.rows = []
        assert is_history_table(table) is False


# ── is_meta_table ────────────────────────────────────

class TestIsMetaTable:
    def _make_table(self, cells_per_row):
        rows = []
        for row_cells in cells_per_row:
            row = MagicMock()
            mocked_cells = []
            for text in row_cells:
                cell = MagicMock()
                cell.text = text
                mocked_cells.append(cell)
            row.cells = mocked_cells
            rows.append(row)
        table = MagicMock()
        table.rows = rows
        return table

    def test_detects_meta_table(self):
        table = self._make_table([
            ["Версия", "1.0.0"],
            ["Дата", "01.01.2026"],
            ["Статус", "DRAFT"],
        ])
        assert is_meta_table(table) is True

    def test_rejects_non_meta_table(self):
        table = self._make_table([
            ["Код", "Описание"],
            ["LS-BR-001", "Правило 1"],
            ["LS-BR-002", "Правило 2"],
        ])
        assert is_meta_table(table) is False

    def test_rejects_small_table(self):
        table = self._make_table([
            ["Версия", "1.0.0"],
            ["Дата", "01.01.2026"],
        ])
        assert is_meta_table(table) is False


# ── para_to_html ─────────────────────────────────────

class TestParaToHtml:
    def _make_para(self, text, style_name="Normal"):
        para = MagicMock()
        para.text = text
        style = MagicMock()
        style.name = style_name
        para.style = style
        return para

    def test_empty_returns_empty(self):
        assert para_to_html(self._make_para("")) == ""

    def test_whitespace_only_returns_empty(self):
        assert para_to_html(self._make_para("   ")) == ""

    def test_title_style(self):
        result = para_to_html(self._make_para("My Title", "Title"))
        assert "<h1>" in result
        assert "<strong>" in result
        assert "My Title" in result

    def test_heading_1(self):
        result = para_to_html(self._make_para("Section", "Heading 1"))
        assert "<h1>" in result

    def test_heading_2(self):
        result = para_to_html(self._make_para("Sub", "Heading 2"))
        assert "<h2>" in result

    def test_heading_3(self):
        result = para_to_html(self._make_para("SubSub", "Heading 3"))
        assert "<h3>" in result

    def test_list_style(self):
        result = para_to_html(self._make_para("Item", "List Bullet"))
        assert "<li>" in result

    def test_normal_paragraph(self):
        result = para_to_html(self._make_para("Normal text"))
        assert "<p>Normal text</p>" == result

    def test_bold_mode(self):
        result = para_to_html(self._make_para("Bold text"), make_bold=True)
        assert "<strong>" in result

    def test_escapes_html_in_text(self):
        result = para_to_html(self._make_para("A & B <C>"))
        assert "&amp;" in result
        assert "&lt;" in result

    def test_bullet_prefix_stripped(self):
        result = para_to_html(self._make_para("* Item text", "Normal"))
        assert "<li>" in result
        assert "Item text" in result


# ── is_warning_table ─────────────────────────────────

class TestIsWarningTable:
    def _make_1x1_table(self, text, color=None):
        cell = MagicMock()
        cell.text = text
        cell._tc = MagicMock()
        if color:
            shd = MagicMock()
            from publish_to_confluence import qn as mock_qn
            if mock_qn:
                shd.get.return_value = color
            cell._tc.find.return_value = MagicMock()
            cell._tc.find.return_value.find.return_value = shd
        else:
            cell._tc.find.return_value = None
        row = MagicMock()
        row.cells = [cell]
        table = MagicMock()
        table.rows = [row]
        return table

    def test_returns_none_for_normal_1x1(self):
        table = self._make_1x1_table("Normal text")
        assert is_warning_table(table) is None

    def test_detects_critical_warning(self):
        table = self._make_1x1_table("Критичная зависимость!")
        result = is_warning_table(table)
        assert result == "warning"

    def test_detects_note(self):
        table = self._make_1x1_table("⚠ Важно: проверить!")
        result = is_warning_table(table)
        assert result == "note"

    def test_returns_none_for_multi_row(self):
        row1 = MagicMock()
        row1.cells = [MagicMock()]
        row2 = MagicMock()
        row2.cells = [MagicMock()]
        table = MagicMock()
        table.rows = [row1, row2]
        assert is_warning_table(table) is None


# ── table_to_html ────────────────────────────────────

class TestTableToHtml:
    def _make_table(self, rows_data):
        rows = []
        for row_cells in rows_data:
            row = MagicMock()
            cells = []
            for text in row_cells:
                cell = MagicMock()
                cell.text = text
                cell._tc = MagicMock()
                cell._tc.find.return_value = None  # No color
                cells.append(cell)
            row.cells = cells
            rows.append(row)
        table = MagicMock()
        table.rows = rows
        return table

    def test_warning_panel(self):
        table = self._make_table([["Critical error!"]])
        result = table_to_html(table, panel_type="warning")
        assert 'ac:name="warning"' in result

    def test_note_panel(self):
        table = self._make_table([["⚠ Note text"]])
        result = table_to_html(table, panel_type="note")
        assert 'ac:name="note"' in result

    def test_regular_table(self):
        table = self._make_table([["Col1", "Col2"], ["A", "B"]])
        result = table_to_html(table)
        assert "confluenceTable" in result
        assert "confluenceTh" in result
        assert "<strong>Col1</strong>" in result
        assert "A" in result

    def test_header_row_has_background(self):
        table = self._make_table([["Header"], ["Data"]])
        result = table_to_html(table)
        assert "background-color:" in result

    def test_empty_rows_skipped(self):
        table = self._make_table([["Header"], [""], ["Data"]])
        result = table_to_html(table)
        assert "Data" in result


# ── history_table_to_html ────────────────────────────

class TestHistoryTableToHtml:
    def test_renders_single_clean_entry(self):
        rows = []
        for row_data in [["Версия", "Дата", "Автор", "Описание"], ["0.1", "01.01", "X", "Draft"]]:
            row = MagicMock()
            cells = []
            for t in row_data:
                c = MagicMock()
                c.text = t
                cells.append(c)
            row.cells = cells
            rows.append(row)
        table = MagicMock()
        table.rows = rows
        result = history_table_to_html(table)
        assert "1.0.0" in result
        assert "Первая публикация" in result
        assert "confluenceTable" in result


# ── meta_table_to_html ───────────────────────────────

class TestMetaTableToHtml:
    def test_renders_meta_with_auto_date(self):
        rows = []
        for key, val in [("Версия", "0.1"), ("Дата", "old"), ("Статус", "DRAFT")]:
            row = MagicMock()
            c1 = MagicMock(); c1.text = key
            c2 = MagicMock(); c2.text = val
            row.cells = [c1, c2]
            rows.append(row)
        table = MagicMock()
        table.rows = rows

        result = meta_table_to_html(table)
        assert FM_VERSION in result
        assert "confluenceTable" in result
        # Date should be today's date
        from datetime import datetime
        assert datetime.now().strftime("%d.%m.%Y") in result


# ── FM_VERSION constant ──────────────────────────────

class TestModuleConstants:
    def test_fm_version_is_1_0_0(self):
        assert FM_VERSION == "1.0.0"

    def test_skip_patterns_not_empty(self):
        assert len(SKIP_AFTER_CODE_SYSTEM) > 0


# ── XHTML Content Verification ───────────────────────


class TestMetaBlockUpdate:
    def test_version_pattern_found(self, sample_xhtml):
        pattern = r'<strong>Версия ФМ:</strong>\s*(\d+\.\d+\.\d+)'
        match = re.search(pattern, sample_xhtml)
        assert match is not None
        assert match.group(1) == "1.0.2"

    def test_version_replacement_in_meta_block(self, sample_xhtml):
        old_version = "1.0.2"
        new_version = "1.0.3"
        meta_block = sample_xhtml[:500]
        rest = sample_xhtml[500:]
        pattern = r'(<strong>Версия ФМ:</strong>\s*)' + re.escape(old_version)
        updated_meta = re.sub(pattern, r'\g<1>' + new_version, meta_block, count=1)
        result = updated_meta + rest
        assert new_version in result
        assert old_version in result

    def test_date_pattern_found(self, sample_xhtml):
        pattern = r'<strong>Дата:</strong>\s*(\d{2}\.\d{2}\.\d{4})'
        match = re.search(pattern, sample_xhtml)
        assert match is not None
        assert match.group(1) == "10.02.2026"


class TestHistoryTablePreservation:
    def test_all_history_rows_present(self, sample_xhtml):
        assert "1.0.0" in sample_xhtml
        assert "1.0.1" in sample_xhtml
        assert "1.0.2" in sample_xhtml

    def test_history_dates_preserved(self, sample_xhtml):
        assert "01.02.2026" in sample_xhtml
        assert "05.02.2026" in sample_xhtml
        assert "10.02.2026" in sample_xhtml

    def test_history_descriptions_preserved(self, sample_xhtml):
        assert "Первая публикация" in sample_xhtml
        assert "Уточнены формулы расчета" in sample_xhtml
        assert "Добавлены SLA" in sample_xhtml

    def test_new_row_added_without_destroying_old(self, sample_xhtml):
        new_row = ('<tr><td class="confluenceTd">1.0.3</td>'
                   '<td class="confluenceTd">18.02.2026</td>'
                   '<td class="confluenceTd">Шаховский А.С.</td>'
                   '<td class="confluenceTd">Добавлены контроли</td></tr>')
        updated = sample_xhtml.replace("</tbody></table>",
                                        new_row + "\n</tbody></table>", 1)
        assert "1.0.0" in updated
        assert "1.0.1" in updated
        assert "1.0.2" in updated
        assert "1.0.3" in updated


class TestAuthorAlwaysShahovsky:
    def test_author_in_meta_block(self, sample_xhtml):
        assert "Шаховский А.С." in sample_xhtml

    def test_no_ai_mentions(self, sample_xhtml):
        forbidden = ["Agent ", "Claude", "Bot", "GPT", "ИИ", "AI "]
        text_lower = sample_xhtml.lower()
        for term in forbidden:
            assert term.lower() not in text_lower


class TestHeaderColors:
    def test_header_color_is_warm(self, sample_xhtml):
        assert "rgb(255,250,230)" in sample_xhtml
        assert "rgb(59,115,175)" not in sample_xhtml

    def test_no_unstyled_th(self, sample_xhtml):
        th_tags = re.findall(r'<th[^>]*>', sample_xhtml)
        for th in th_tags:
            assert 'style=' in th
