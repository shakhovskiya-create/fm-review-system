"""
Tests for check_confluence_macros.py — Confluence macro checker.

Now imports the module directly (after refactoring to __name__ guard).
"""
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_confluence_macros import load_env, api_get, find_macros


class TestLoadEnv:
    def test_parses_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")
        result = load_env(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_skips_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nKEY=val\n")
        result = load_env(env_file)
        assert result == {"KEY": "val"}

    def test_skips_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nKEY=val\n\n")
        result = load_env(env_file)
        assert result == {"KEY": "val"}

    def test_handles_value_with_equals(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("URL=https://host.com?a=1&b=2\n")
        result = load_env(env_file)
        assert result == {"URL": "https://host.com?a=1&b=2"}

    def test_strips_whitespace(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("  KEY  =  value  \n")
        result = load_env(env_file)
        assert result == {"KEY": "value"}

    def test_exits_on_missing_file(self, tmp_path):
        with pytest.raises(SystemExit):
            load_env(tmp_path / "nonexistent")


class TestFindMacros:
    def test_finds_macro_names(self):
        html = '<ac:structured-macro ac:name="warning"><ac:structured-macro ac:name="note">'
        assert find_macros(html) == ["note", "warning"]

    def test_deduplicates(self):
        html = '<ac:structured-macro ac:name="info"><ac:structured-macro ac:name="info">'
        assert find_macros(html) == ["info"]

    def test_returns_sorted(self):
        html = '<ac:structured-macro ac:name="note"><ac:structured-macro ac:name="code"><ac:structured-macro ac:name="anchor">'
        assert find_macros(html) == ["anchor", "code", "note"]

    def test_empty_body(self):
        assert find_macros("") == []
        assert find_macros("<p>no macros</p>") == []


class TestApiGet:
    @patch("check_confluence_macros.urllib.request.urlopen")
    def test_returns_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"title": "Test Page"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = api_get("content/123", "https://conf.example.com", "token123")
        assert result == {"title": "Test Page"}
        mock_urlopen.assert_called_once()

    @patch("check_confluence_macros.urllib.request.urlopen", side_effect=urllib.error.URLError("Network error"))
    def test_returns_none_on_error(self, mock_urlopen):
        result = api_get("content/123", "https://conf.example.com", "token123")
        assert result is None

    @patch("check_confluence_macros.urllib.request.urlopen")
    def test_sends_bearer_auth(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        api_get("content/123", "https://conf.example.com", "mytoken")
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer mytoken"
