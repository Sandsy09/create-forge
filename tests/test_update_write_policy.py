"""create-forge#214: `update.py` must never write the metadata file with
`Path.write_text`.

`write_text` translates `\\n` to `\\r\\n` on Windows, so rewriting the
recorded generation-metadata document with byte-for-byte the same content
still changes its bytes -- breaking rule 15's "rewrites ... to byte-identical
content" (`docs/engine-project-lifecycle.md`). `write_recorded` was fixed to
use `path.write_bytes(content.encode("utf-8"))`; this is the tripwire so
`write_text` cannot quietly return to this module, matching
`tests/test_subprocess_policy.py`'s own house idiom: parse the source with
`ast` rather than grep it, and self-check the detector against a synthetic
snippet first so a guard that has stopped matching anything fails here
rather than passing for the wrong reason.

Deliberately scoped to `update.py` alone. `src/create_forge/config.py` also
calls `write_text` for the user's own config file
(`~/.config/create-forge/config.toml`) -- out of scope per #214's own
exclusions: no line-ending policy is proposed for any file but the recorded
generation metadata.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPDATE_MODULE = REPO_ROOT / "src" / "create_forge" / "update.py"


def _write_text_calls(source: str) -> list[int]:
    """Every `<expr>.write_text(...)` call's line number, however `<expr>` is
    named -- `write_text` is never a bare or `subprocess`-style import, so
    this only needs to match the attribute access itself.
    """
    tree = ast.parse(source)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]


def test_the_detector_finds_write_text_regardless_of_the_receiver_name() -> None:
    assert _write_text_calls("path.write_text('x')\n") == [1]
    assert _write_text_calls("self._path.write_text('x', encoding='utf-8')\n") == [1]
    assert _write_text_calls("path.write_bytes(b'x')\n") == []
    assert _write_text_calls("path.read_text()\n") == []


def test_update_py_never_calls_write_text() -> None:
    source = UPDATE_MODULE.read_text(encoding="utf-8")

    offenders = _write_text_calls(source)

    assert not offenders, (
        "src/create_forge/update.py calls Path.write_text at line(s) "
        f"{offenders} -- on Windows this translates \\n to \\r\\n, so "
        "rewriting the recorded generation-metadata document with the same "
        "content would still change its bytes, breaking rule 15's "
        "byte-identical no-op update (create-forge#214). Use "
        "path.write_bytes(content.encode('utf-8')) instead. "
        "src/create_forge/config.py's own write_text for the user's config "
        "file is deliberately out of this guard's scope."
    )
