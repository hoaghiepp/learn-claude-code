"""Reusable helper utilities for demo_pkg."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

_NON_ALNUM: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


def reverse_string(text: str) -> str:
    """Return ``text`` with its characters reversed.

    Args:
        text: The string to reverse.

    Returns:
        The reversed string.

    Example:
        >>> reverse_string("hello")
        'olleh'
    """
    return text[::-1]


def slugify(text: str) -> str:
    """Convert ``text`` into a URL-friendly slug.

    Normalizes unicode, lowercases, and collapses runs of non-alphanumeric
    characters into single hyphens. Leading/trailing hyphens are stripped.

    Args:
        text: The string to slugify.

    Returns:
        A lowercase, hyphen-separated slug. Returns an empty string when
        ``text`` contains no alphanumeric characters.

    Example:
        >>> slugify("Hello, World! 2024")
        'hello-world-2024'
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_ALNUM.sub("-", ascii_only)
    return slug.strip("-")


def kebab_to_snake(text: str) -> str:
    """Convert a kebab-case string to snake_case.

    Hyphens are replaced with underscores; surrounding whitespace is stripped.

    Args:
        text: A kebab-case string, e.g. ``"my-cool-var"``.

    Returns:
        The snake_case equivalent, e.g. ``"my_cool_var"``.

    Example:
        >>> kebab_to_snake("my-cool-var")
        'my_cool_var'
    """
    return text.strip().replace("-", "_")


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    sample = "Hello, World! 2024"
    print(f"reverse_string({sample!r}) = {reverse_string(sample)!r}")
    print(f"slugify({sample!r})        = {slugify(sample)!r}")
    print(f"kebab_to_snake('my-var')   = {kebab_to_snake('my-var')!r}")
