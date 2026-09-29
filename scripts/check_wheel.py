"""Verify `templates.toml` and every shipped module actually ship in the built wheel.

Editable installs read `src/` directly; a built wheel only carries what
Hatchling's package-data rules say to. That is invariant 5 in CLAUDE.md — a
missing registry passes every other test and breaks on a user's first
`uvx` run. The module check (CF-25.03) closes the same gap one level wider:
a future packaging change that drops `commands/` (or any other package
subdirectory) from `[tool.hatch.build.targets.wheel]` would pass every local
and editable-install test too, and only fail for a user on first import.

This replaces a one-line `shell` task
(`uv build && python -m zipfile -l dist/*.whl | grep templates.toml`) that had
two real bugs: the pipe swallowed `uv build`'s exit code, and `dist/*.whl`
could silently match a *stale* wheel left over from an earlier build rather
than the one just produced. Building into a fresh temporary directory each run
closes both.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "create_forge"
_REGISTRY_MEMBER = "create_forge/templates.toml"


def _expected_module_members() -> list[str]:
    """Every `.py` file under `src/create_forge/`, as its wheel member path.

    Derived from the real source tree, not hard-coded -- the same reasoning
    `tests/source_tree.py` documents for its own guards: a hard-coded list
    silently stops covering a module the moment it moves under a new
    subpackage.
    """
    return sorted(
        f"create_forge/{path.relative_to(SRC_ROOT).as_posix()}"
        for path in SRC_ROOT.rglob("*.py")
    )


def _build_wheel(out_dir: Path) -> Path:
    """Build a wheel into `out_dir` and return its path."""
    subprocess.run(  # noqa: S603
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],  # noqa: S607
        check=True,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        msg = f"expected exactly one wheel in {out_dir}, found {len(wheels)}: {wheels}"
        raise RuntimeError(msg)
    return wheels[0]


def main() -> int:
    """Build a wheel and fail loudly if the registry or a module is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        wheel = _build_wheel(Path(tmp))
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())

        if _REGISTRY_MEMBER not in names:
            print(
                f"error: {_REGISTRY_MEMBER!r} is missing from {wheel.name}.\n"
                "templates.toml did not ship in the wheel -- check "
                "[tool.hatch.build.targets.wheel] in pyproject.toml.",
                file=sys.stderr,
            )
            return 1

        missing = [m for m in _expected_module_members() if m not in names]
        if missing:
            print(
                f"error: {len(missing)} module(s) missing from {wheel.name}:\n  "
                + "\n  ".join(missing)
                + "\ncheck [tool.hatch.build.targets.wheel] in pyproject.toml.",
                file=sys.stderr,
            )
            return 1

    print(f"ok: {_REGISTRY_MEMBER!r} and every shipped module found in {wheel.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
