#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for rime-install.py's default.custom.yaml schema_list editor.

Run from the repository root:

    python plugins/test_rime_install.py

or with unittest discovery:

    python -m unittest discover -s plugins -p "test_*.py"
"""

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

SOURCE = Path(__file__).resolve().parent
MODULE_PATH = SOURCE / "rime-install.py"

_spec = importlib.util.spec_from_file_location("rime_install", MODULE_PATH)
rime_install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rime_install)  # type: ignore[union-attr]

IME_NAME = "flypy_cangjie5_hk"
NEW_ITEM = f"    - {{schema: {IME_NAME}}}"
HEADER = "patch:\n  schema_list:\n"


def parsed_schema_list(text):
    """Return patch.schema_list as a list, or None if PyYAML is unavailable."""
    if yaml is None:
        return None
    data = yaml.safe_load(text) or {}
    return data.get("patch", {}).get("schema_list", [])


class TestInsertSchema(unittest.TestCase):
    """The new entry must always occupy its own physical line."""

    def assert_item_on_own_line(self, text):
        lines = text.splitlines()
        self.assertIn(
            NEW_ITEM,
            lines,
            msg=f"new schema entry is not on its own line:\n{text!r}",
        )

    def assert_schema_list(self, text, expected):
        """If PyYAML is present, the result must still be valid YAML."""
        items = parsed_schema_list(text)
        if items is None:
            return
        self.assertEqual(items, [{"schema": name} for name in expected], msg=text)

    def test_appends_after_existing_entry(self):
        """Baseline: a newline-terminated file is handled correctly."""
        text = HEADER + "    - {schema: luna_pinyin}\n"
        out = rime_install._insert_schema_into_yaml(text, IME_NAME)

        self.assert_item_on_own_line(out)
        self.assert_schema_list(out, ["luna_pinyin", IME_NAME])

    def test_appends_when_file_has_no_final_newline(self):
        """Reproduces the glued line: last entry lacks a trailing newline."""
        text = HEADER + "    - {schema: luna_pinyin}"
        out = rime_install._insert_schema_into_yaml(text, IME_NAME)

        self.assert_item_on_own_line(out)
        self.assert_schema_list(out, ["luna_pinyin", IME_NAME])

    def test_appends_to_empty_schema_list_at_eof(self):
        """Reproduces the glued line: empty schema_list is the last line."""
        text = "patch:\n  schema_list:\n"
        out = rime_install._insert_schema_into_yaml(text, IME_NAME)

        self.assert_item_on_own_line(out)
        self.assert_schema_list(out, [IME_NAME])

    def test_appends_to_empty_schema_list_before_sibling_key(self):
        """Reproduces the glued line: empty schema_list followed by a key."""
        text = "patch:\n  schema_list:\n  menu:\n    page_size: 5\n"
        out = rime_install._insert_schema_into_yaml(text, IME_NAME)

        self.assert_item_on_own_line(out)
        self.assert_schema_list(out, [IME_NAME])

    def test_preserves_trailing_spaces_without_final_newline(self):
        """Reproduces the glued line: item line ends with spaces, then EOF."""
        text = HEADER + "    - {schema: luna_pinyin}   "
        out = rime_install._insert_schema_into_yaml(text, IME_NAME)

        self.assert_item_on_own_line(out)
        self.assert_schema_list(out, ["luna_pinyin", IME_NAME])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]], verbosity=2)
