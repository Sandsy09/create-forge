"""Verify `templates.toml` actually ships in the built wheel.

Editable installs read `templates.toml` straight from `src/`; a built wheel
only carries it if Hatchling's package-data rules are still correct. That is
invariant 5 in CLAUDE.md — a missing registry passes every other test and
breaks on a user's first `uvx` run.

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

_REGISTRY_MEMBER = "create_forge/templates.toml"


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
    """Build a wheel and fail loudly if the registry did not make it in."""
    with tempfile.TemporaryDirectory() as tmp:
        wheel = _build_wheel(Path(tmp))
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()

        if _REGISTRY_MEMBER not in names:
            print(
                f"error: {_REGISTRY_MEMBER!r} is missing from {wheel.name}.\n"
                "templates.toml did not ship in the wheel -- check "
                "[tool.hatch.build.targets.wheel] in pyproject.toml.",
                file=sys.stderr,
            )
            return 1

    print(f"ok: {_REGISTRY_MEMBER!r} found in {wheel.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
