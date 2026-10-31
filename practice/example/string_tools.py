"""Small utilities for manipulating strings, e.g. building URL slugs."""

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Convert *text* into a URL slug.

    The text is lowercased and trimmed; every run of non-alphanumeric
    characters is replaced with a single hyphen, and leading/trailing
    hyphens are removed. Strings containing no alphanumeric characters
    (including the empty string) return "".
    """
    return _NON_ALNUM.sub("-", text.strip().lower()).strip("-")


if __name__ == "__main__":
    print(slugify("  Hello, World!  "))          # hello-world
    print(slugify("  ---***---  "))              # (empty string)
