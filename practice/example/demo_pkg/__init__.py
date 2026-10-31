"""demo_pkg: a small example Python package.

Demonstrates standard package layout with:

- ``demo_pkg.utils``  – reusable helper utilities
- ``demo_pkg.tests`` – unit tests for those utilities
"""

__version__ = "0.1.0"

from .utils import kebab_to_snake, reverse_string, slugify

__all__ = ["__version__", "kebab_to_snake", "reverse_string", "slugify"]
