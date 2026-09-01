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
- [0012 — Adopt engine updates within one compatibility line behind a review gate](0012-engine-dependency-update-policy.md)
- [0013 — Build ProjectSpec as a wire payload behind a single engine adapter](0013-projectspec-construction-boundary.md)
- [0014 — Reach the engine from a command through a lazy, opt-in preview flag](0014-lazy-engine-reachability.md)
- [0015 — Render into an adjacent staging directory and finalise by rename](0015-staged-filesystem-generation.md)
- [0016 — Test the reference client end to end against the released template](0016-end-to-end-reference-client-tests.md)
- [0017 — Expose the CLI Application archetype through discovery-driven selection](0017-cli-application-archetype-exposure.md)
- [0018 — Publish to PyPI and assign the first bounded engine range](0018-pypi-distribution-and-the-first-engine-range.md)
- [0019 — CLI archetype-parity review](0019-cli-archetype-parity-review.md)
- [0020 — Test the public engine path end to end](0020-engine-path-end-to-end-tests.md)
- [0021 — Finalise engine-generated lockfiles in the client](0021-client-finalises-engine-lockfiles.md)
- [0022 — Downstream organisation-policy consumption hook](0022-downstream-organisation-policy-hook.md)
- [0023 — Downstream client reference](0023-downstream-client-reference.md)
- [0024 — Keep create-forge a reference client, not a framework dependency](0024-reference-client-not-framework-dependency.md)
- [0025 — Prompt the engine path from discovery, not the Copier registry](0025-engine-native-prompt-flow.md)

Add a new record by copying the most recent one and incrementing the number.
Records are immutable: supersede them rather than editing.

`uv run poe check:adr` (and the fast test suite, via `tests/test_adr.py`)
verifies the set stays consistent — filenames match `NNNN-slug.md`, numbers
are contiguous with no gaps or duplicates, every record is linked here, and
each has all four Nygard headings. See
[scripts/adr.py](../../scripts/adr.py).
