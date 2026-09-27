"""List a destination's own staging-directory siblings, if any survive.

CF-25.01: this two-line helper was independently duplicated in
`tests/test_data_science_pipeline.py` and `tests/test_e2e_installed_rollout.py`.
Factored out here so `tests/test_cli.py` can use it too, for the staging-
cleanup check that was previously exercised only at the pipeline and
installed-console layers, never through `CliRunner`.

No network, no filesystem outside the one directory passed in.
"""

from __future__ import annotations

from pathlib import Path

# Matches `staging._STAGING_PREFIX` -- not imported, since that's a private
# module attribute and the two definitions this factors out never imported
# it either; kept as a literal here for the same reason `staging.py`'s own
# tests (`tests/test_staging.py`) check it independently rather than by
# reference, so a change to the prefix is caught by drift, not silently
# absorbed by both sides moving together.
_STAGING_PREFIX = ".create-forge-"


def staging_siblings(dest: Path) -> list[Path]:
    """Every leftover `.create-forge-*` staging directory beside `dest`.

    `dest.parent` itself may not exist in an installed-console check where a
    failure removed more than just `dest` -- that reads as "no siblings"
    rather than raising.
    """
    parent = dest.parent
    if not parent.is_dir():
        return []
    return [p for p in parent.iterdir() if p.name.startswith(_STAGING_PREFIX)]
