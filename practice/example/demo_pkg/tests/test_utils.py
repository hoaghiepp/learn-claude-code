"""Tests for demo_pkg.utils."""

from __future__ import annotations

import unittest

# Relative import keeps the tests working whether ``demo_pkg`` is on
# sys.path directly or reached via ``practice.example.demo_pkg``.
from ..utils import kebab_to_snake, reverse_string, slugify


class TestReverseString(unittest.TestCase):
    def test_simple_word(self):
        self.assertEqual(reverse_string("hello"), "olleh")

    def test_empty_string(self):
        self.assertEqual(reverse_string(""), "")

    def test_palindrome_is_unchanged(self):
        self.assertEqual(reverse_string("racecar"), "racecar")

    def test_whitespace_and_punctuation(self):
        self.assertEqual(reverse_string("a b!c"), "c!b a")


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello, World! 2024"), "hello-world-2024")

    def test_collapses_multiple_separators(self):
        self.assertEqual(slugify("a  --  b"), "a-b")

    def test_strips_leading_and_trailing_hyphens(self):
        self.assertEqual(slugify("---hello---"), "hello")

    def test_unicode_is_transliterated(self):
        # 'café' -> 'cafe' after NFKD normalization drops the accent
        self.assertEqual(slugify("café"), "cafe")

    def test_only_symbols_yields_empty(self):
        self.assertEqual(slugify("!!!???***"), "")


class TestKebabToSnake(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(kebab_to_snake("my-cool-var"), "my_cool_var")

    def test_no_hyphens_is_unchanged(self):
        self.assertEqual(kebab_to_snake("plain"), "plain")

    def test_surrounding_whitespace_stripped(self):
        self.assertEqual(kebab_to_snake("  my-var  "), "my_var")

    def test_empty_string(self):
        self.assertEqual(kebab_to_snake(""), "")


if __name__ == "__main__":
    unittest.main()
