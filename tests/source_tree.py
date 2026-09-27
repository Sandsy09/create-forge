"""Discover every production module under `src/create_forge/`.

CF-25.01: several guard tests used to hand-list `cli.py` and its neighbours
in a flat tuple, or glob `src/create_forge/*.py` non-recursively. Both shapes
silently stop covering a module the moment it moves under a subpackage (the
`commands/` split CF-25.02 plans) -- a `commands/new.py` importing
`forge_template` directly, say, would simply never be scanned. This module is
the one place that walks the real tree, so every guard that needs "every
shipped module" imports it instead of re-implementing the walk.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "create_forge"


def production_modules() -> list[Path]:
    """Every `.py` file under `src/create_forge/`, recursive, sorted."""
    return sorted(SRC_ROOT.rglob("*.py"))


def production_module_text() -> dict[Path, str]:
    """Every production module's own source, keyed by its path.

    For guards that search *content* (a substring, an import, a string
    literal) rather than needing to walk each file's AST separately.
    """
    return {path: path.read_text(encoding="utf-8") for path in production_modules()}
