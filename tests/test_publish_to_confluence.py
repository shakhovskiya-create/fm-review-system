"""
Tests for scripts/publish_to_confluence.py

Tests the pure functions (XHTML generation, parsing, color mapping)
without requiring Confluence API access or python-docx.
"""
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── Helper function tests (imported directly) ──────────────


class TestEscapeHtml:
    """Tests for escape_html function."""

    def setup_method(self):
        # Import the function by reading module source to avoid argparse side effects
        self._load_functions()

    def _load_functions(self):
        """Load pure functions from publish_to_confluence.py without triggering argparse."""
        source_path = SCRIPTS_DIR / "publish_to_confluence.py"
        source = source_path.read_text()

        # Extract escape_html function
        match = re.search(
            r'(def escape_html\(text\):.*?(?=\ndef ))',
            source, re.DOTALL
        )
        if match:
            exec(match.group(1), self.__dict__)

    def test_escapes_ampersand(self):
        assert self.escape_html("A & B") == "A &amp; B"

    def test_escapes_lt_gt(self):
        assert self.escape_html("<tag>") == "&lt;tag&gt;"

    def test_no_change_for_plain_text(self):
        assert self.escape_html("Hello World") == "Hello World"

    def test_all_special_chars(self):
        result = self.escape_html("a & b < c > d")
        assert result == "a &amp; b &lt; c &gt; d"


class TestHexToConfluenceColor:
    """Tests for hex_to_confluence_color function."""

    def setup_method(self):
        source_path = SCRIPTS_DIR / "publish_to_confluence.py"
        source = source_path.read_text()
        match = re.search(
            r'(def hex_to_confluence_color\(hex_color\):.*?(?=\ndef ))',
            source, re.DOTALL
        )
        if match:
            exec(match.group(1), self.__dict__)

    def test_none_returns_none(self):
        assert self.hex_to_confluence_color(None) is None

    def test_auto_returns_none(self):
        assert self.hex_to_confluence_color("auto") is None

    def test_yellow_mapping(self):
        assert self.hex_to_confluence_color("FFDD00") == "#fffae6"

    def test_green_mapping(self):
        assert self.hex_to_confluence_color("DCFCE7") == "#e3fcef"

    def test_red_mapping(self):
        assert self.hex_to_confluence_color("FECACA") == "#ffebe6"

    def test_blue_mapping(self):
        assert self.hex_to_confluence_color("DBEAFE") == "#deebff"

    def test_gray_mapping(self):
        assert self.hex_to_confluence_color("F3F4F6") == "#f4f5f7"

    def test_rgb_analysis_yellow(self):
        """High R+G, low B = yellow."""
        result = self.hex_to_confluence_color("FFE000")
        assert result == "#fffae6"

    def test_rgb_analysis_green(self):
        """High G, low R = green."""
        result = self.hex_to_confluence_color("80F080")
        assert result == "#e3fcef"


# ── XHTML Content Verification ─────────────────────────────


class TestMetaBlockUpdate:
    """Tests verifying meta-block version update patterns."""

    def test_version_pattern_found(self, sample_xhtml):
        """Version pattern exists in sample XHTML."""
        pattern = r'<strong>Версия ФМ:</strong>\s*(\d+\.\d+\.\d+)'
        match = re.search(pattern, sample_xhtml)
        assert match is not None
        assert match.group(1) == "1.0.2"

    def test_version_replacement_in_meta_block(self, sample_xhtml):
        """Version can be safely replaced in meta-block only."""
        old_version = "1.0.2"
        new_version = "1.0.3"
        # Replace ONLY in meta-block pattern (first 500 chars)
        meta_block = sample_xhtml[:500]
        rest = sample_xhtml[500:]

        pattern = r'(<strong>Версия ФМ:</strong>\s*)' + re.escape(old_version)
        updated_meta = re.sub(pattern, r'\g<1>' + new_version, meta_block, count=1)

        result = updated_meta + rest
        assert new_version in result
        # Old version should still exist in history table (beyond 500 chars)
        assert old_version in result

    def test_date_pattern_found(self, sample_xhtml):
        """Date pattern exists in sample XHTML."""
        pattern = r'<strong>Дата:</strong>\s*(\d{2}\.\d{2}\.\d{4})'
        match = re.search(pattern, sample_xhtml)
        assert match is not None
        assert match.group(1) == "10.02.2026"


class TestHistoryTablePreservation:
    """Tests verifying history table rows are preserved."""

    def test_all_history_rows_present(self, sample_xhtml):
        """All version rows exist in history table."""
        assert "1.0.0" in sample_xhtml
        assert "1.0.1" in sample_xhtml
        assert "1.0.2" in sample_xhtml

    def test_history_dates_preserved(self, sample_xhtml):
        """Historical dates are preserved."""
        assert "01.02.2026" in sample_xhtml
        assert "05.02.2026" in sample_xhtml
        assert "10.02.2026" in sample_xhtml

    def test_history_descriptions_preserved(self, sample_xhtml):
        """Historical descriptions are preserved."""
        assert "Первая публикация" in sample_xhtml
        assert "Уточнены формулы расчета" in sample_xhtml
        assert "Добавлены SLA" in sample_xhtml

    def test_new_row_added_without_destroying_old(self, sample_xhtml):
        """Adding a new history row preserves existing rows."""
        new_row = ('<tr><td class="confluenceTd">1.0.3</td>'
                   '<td class="confluenceTd">18.02.2026</td>'
                   '<td class="confluenceTd">Шаховский А.С.</td>'
                   '<td class="confluenceTd">Добавлены контроли</td></tr>')

        # Insert before closing </tbody>
        updated = sample_xhtml.replace("</tbody></table>",
                                        new_row + "\n</tbody></table>", 1)

        # All old rows still present
        assert "1.0.0" in updated
        assert "1.0.1" in updated
        assert "1.0.2" in updated
        assert "Первая публикация" in updated
        # New row also present
        assert "1.0.3" in updated
        assert "Добавлены контроли" in updated

    def test_replace_all_version_would_break_history(self, sample_xhtml):
        """Demonstrates why replace_all for version numbers is dangerous."""
        # This is a negative test - showing the anti-pattern
        broken = sample_xhtml.replace("1.0.2", "1.0.3")
        # The history table row for 1.0.2 is now gone!
        assert "1.0.2" not in broken  # History corrupted!
        # This is why CLAUDE.md forbids replace_all for versions


class TestAuthorAlwaysShahovsky:
    """Tests verifying author is always 'Шаховский А.С.'"""

    def test_author_in_meta_block(self, sample_xhtml):
        """Meta-block has correct author."""
        assert "Шаховский А.С." in sample_xhtml

    def test_author_in_history_rows(self, sample_xhtml):
        """All history rows have correct author."""
        rows = re.findall(r'<tr><td[^>]*>(\d+\.\d+\.\d+)</td>.*?</tr>',
                          sample_xhtml, re.DOTALL)
        # Each row's author cell
        author_cells = re.findall(
            r'<td class="confluenceTd">Шаховский А\.С\.</td>', sample_xhtml
        )
        assert len(author_cells) == 3  # One per version row

    def test_no_ai_mentions(self, sample_xhtml):
        """No AI/Agent/Bot mentions in XHTML content."""
        forbidden = ["Agent ", "Claude", "Bot", "GPT", "ИИ", "AI "]
        text_lower = sample_xhtml.lower()
        for term in forbidden:
            assert term.lower() not in text_lower, \
                f"Forbidden term '{term}' found in XHTML"


class TestHeaderColors:
    """Tests for Confluence table header color standards."""

    def test_header_color_is_warm(self, sample_xhtml):
        """Table headers use warm color rgb(255,250,230), not blue."""
        assert "rgb(255,250,230)" in sample_xhtml
        assert "rgb(59,115,175)" not in sample_xhtml  # Blue is forbidden

    def test_no_unstyled_th(self, sample_xhtml):
        """All <th> elements have a style attribute."""
        th_tags = re.findall(r'<th[^>]*>', sample_xhtml)
        for th in th_tags:
            assert 'style=' in th, f"Unstyled <th> found: {th}"


# ── _get_page_id Tests ──────────────────────────────────────


class TestGetPageId:
    def test_reads_from_project_file(self, tmp_path):
        """_get_page_id reads PAGE_ID from project CONFLUENCE_PAGE_ID file."""
        # Create projects/PROJECT_TEST/CONFLUENCE_PAGE_ID structure
        project_dir = tmp_path / "projects" / "PROJECT_TEST"
        project_dir.mkdir(parents=True)
        (project_dir / "CONFLUENCE_PAGE_ID").write_text("99999999\n")

        source_path = SCRIPTS_DIR / "publish_to_confluence.py"
        source = source_path.read_text()

        # Extract function
        match = re.search(
            r'(def _get_page_id\(project_name=None\):.*?(?=\n\n))',
            source, re.DOTALL
        )
        assert match is not None
        func_code = match.group(1)

        # Patch root to tmp directory
        root = str(tmp_path)
        patched = func_code.replace(
            'os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
            f'"{root}"'
        )

        ns = {"os": os}
        exec(patched, ns)

        result = ns["_get_page_id"]("PROJECT_TEST")
        assert result == "99999999"

    def test_falls_back_to_env(self):
        """_get_page_id falls back to CONFLUENCE_PAGE_ID env var."""
        source_path = SCRIPTS_DIR / "publish_to_confluence.py"
        source = source_path.read_text()

        match = re.search(
            r'(def _get_page_id\(project_name=None\):.*?(?=\n\n))',
            source, re.DOTALL
        )
        func_code = match.group(1)
        patched = func_code.replace(
            'os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
            '"/nonexistent"'
        )

        ns = {"os": os}
        exec(patched, ns)

        with patch.dict(os.environ, {"CONFLUENCE_PAGE_ID": "77777"}):
            result = ns["_get_page_id"](None)
            assert result == "77777"
