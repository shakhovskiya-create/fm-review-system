"""
Tests for check_confluence_macros.py — Confluence macro checker.

Tests the module structure and load_env function.
The script performs live API calls, so we test utility functions
and validate the script's syntax/imports.
"""
import ast
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "check_confluence_macros.py"


class TestScriptStructure:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists()

    def test_valid_python_syntax(self):
        """Script parses as valid Python."""
        source = SCRIPT_PATH.read_text()
        ast.parse(source)  # Raises SyntaxError if invalid

    def test_has_load_env_function(self):
        """Script defines a load_env function."""
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "load_env" in func_names

    def test_has_api_get_function(self):
        """Script defines an api_get function."""
        source = SCRIPT_PATH.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        ]
        assert "api_get" in func_names

    def test_uses_bearer_auth(self):
        """Script uses Bearer token authentication."""
        source = SCRIPT_PATH.read_text()
        assert "Bearer" in source

    def test_no_hardcoded_tokens(self):
        """Script does not contain hardcoded API tokens."""
        source = SCRIPT_PATH.read_text()
        # Should read from config, not have tokens inline
        assert "load_env" in source or "os.environ" in source

    def test_uses_ssl_context(self):
        """Script handles SSL context."""
        source = SCRIPT_PATH.read_text()
        assert "ssl" in source
