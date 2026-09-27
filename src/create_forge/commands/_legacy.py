"""The `--legacy` Copier route's shared availability check.

ADR 0060 decision 3, filled in during implementation: `_ensure_legacy_available`
is needed by both `commands/update.py` (the direct-Copier update route) and
`commands/new.py` (`new --legacy`) -- two different command modules, so it
lives in its own small shared module neither imports from the other.
"""

from __future__ import annotations

import typer

from create_forge.commands import _output


def _ensure_legacy_available(*, purpose: str = "to use --legacy") -> None:
    """Import `create_forge.runner`, failing closed if `copier` is absent.

    ADR 0040 decision 2 (CF-18.01) moves `copier` from a required dependency
    to the optional `legacy` extra: `runner.py` imports it at module scope
    (invariant 4), so this is now the lazy, guarded import -- reached only
    from `--legacy` and `update`, mirroring the shape `engine`/`pipeline`'s
    import had before the cutover. Decision 12 widens exit `3`'s
    provider-availability class to cover exactly this: a missing generator,
    not a usage error, so callers exit `3` rather than raising a bare
    `ImportError` traceback. Callers reached only after this succeeds import
    `create_forge.runner`'s names directly -- the module is already cached in
    `sys.modules`, so that second import is free.

    `purpose` distinguishes why the extra is needed (ADR 0047 rule 4): `new
    --legacy` reads "to use --legacy", while `update`'s file-routed Copier
    path -- reachable with no `--legacy` flag at all, whenever the project
    records `.copier-answers.yml` -- supplies its own project-specific
    wording instead.
    """
    try:
        import create_forge.runner  # noqa: F401, PLC0415
    except ImportError:
        _output.err.print(
            "[red]The legacy Copier route isn't installed.[/red] Run "
            r"`pip install 'create-forge\[legacy]'` (or `uv sync --all-extras` "
            f"in a create-forge checkout) {purpose}."
        )
        raise typer.Exit(3) from None
