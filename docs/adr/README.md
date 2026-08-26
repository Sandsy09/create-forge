# Architecture Decision Records

Records of significant decisions, in [Nygard
format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

- [0001 — Record architecture decisions](0001-record-architecture-decisions.md)
- [0002 — Copier over Cookiecutter](0002-copier-over-cookiecutter.md)
- [0003 — Two-repo split](0003-two-repo-split.md)
- [0004 — Copier's Python API over subprocess](0004-copier-python-api-over-subprocess.md)
- [0005 — Execute template tasks (`unsafe=True`)](0005-execute-template-tasks.md)
- [0006 — Bundled registry over remote](0006-bundled-registry-over-remote.md)
- [0007 — Scaffold-only scope](0007-scaffold-only-scope.md)
- [0008 — Fork model for organisations](0008-fork-model-for-organisations.md)
- [0009 — `pyproject.toml` as the single version source](0009-pyproject-as-the-single-version-source.md)
- [0010 — Adopt the forge-template public engine contract](0010-public-engine-integration-contract.md)
- [0011 — Resolve the template engine from a bounded installed dependency](0011-engine-source-and-version-resolution.md)

Add a new record by copying the most recent one and incrementing the number.
Records are immutable: supersede them rather than editing.

`uv run poe check:adr` (and the fast test suite, via `tests/test_adr.py`)
verifies the set stays consistent — filenames match `NNNN-slug.md`, numbers
are contiguous with no gaps or duplicates, every record is linked here, and
each has all four Nygard headings. See
[scripts/adr.py](../../scripts/adr.py).
