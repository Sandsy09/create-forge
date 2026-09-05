# 31. Adopt the reviewed forge-template 0.4.1 release

## Status

Accepted

## Context

[Issue #111 / CF-14.01](https://github.com/Sandsy09/create-forge/issues/111)
opens create-forge's final Data Science validation and rollout stage. Stage 13
proved the preview pipeline against `forge-template 0.4.0`, the first release
to contain the Data Science archetype and reusable capabilities. Provider
Stage 14 has since reviewed the three-archetype composition boundary, validated
the two repositories together, and published the accepted result as
[`forge-template 0.4.1`](https://github.com/Sandsy09/forge-template/releases/tag/v0.4.1).

The provider's canonical
[reviewed-release record](https://github.com/Sandsy09/forge-template/blob/main/docs/reviewed-engine-release.md)
proves that `src/forge_template`, the component catalogue, Foundation and
component content, public signatures, protocol integers, component versions,
and rendered bytes are unchanged from `0.4.0`. Only package and documentation
metadata changed. The client therefore needs to adopt the reviewed release as
its minimum supported engine, not migrate an API or reproduce provider-owned
catalogue semantics.

This adoption also prepares the first create-forge release line containing
generic Data Science selection. The package version must become `0.3.0`, but
tagging, publishing, release verification, and the complete changelog remain
CF-14.04.

## Decision

1. **Raise the engine lower bound to `forge-template>=0.4.1,<0.5`.**
   `pyproject.toml`, `create_forge.compat.SUPPORTED_ENGINE_RANGE`, the
   independent downstream reference, diagnostics, tests, and living
   compatibility contracts move together. The strict `<0.5` upper bound is
   unchanged.

2. **Resolve the released provider exactly in development.** `uv.lock` is
   regenerated from PyPI and records `forge-template 0.4.1`. The real-engine
   contract asserts that exact installed version before exercising the public
   facade.

3. **Retain both protocol tuples.** ProjectSpec remains `(1,)`; component
   manifests remain `(1, 2)`. `engine.py`, `spec.py`, and `pipeline.py` need no
   change because the reviewed provider surface and rendered output are
   unchanged.

4. **Prepare create-forge `0.3.0` without releasing it.** `pyproject.toml` and
   the editable package entry in `uv.lock` move to `0.3.0`. CF-14.04 owns the
   final changelog, tag, GitHub release, PyPI publication, and installed-release
   verification after CF-14.02 and CF-14.03 complete.

5. **Keep the engine optional and preview-only.** `forge-template` and `uv`
   remain exclusively in the `engine` extra. Plain installs and the default
   direct-Copier `new` path stay independent of the engine; the reviewed engine
   remains reachable only through hidden `--engine-preview` delivery.

6. **Reject the unreviewed floor before engine work.** Synthetic `0.4.0` and
   excluded-upper-bound `0.5.0` engine versions fail package negotiation before
   parsing, discovery, validation, rendering, or filesystem generation. The
   established exit-status and no-fallback contracts are unchanged.

7. **Copy no catalogue knowledge into create-forge.** Existing discovery,
   descriptor-shape, relationship-shape, and shipped-source AST guards remain
   the acceptance proof. No component identifier, file manifest, selection
   rule, or scientific semantic is added.

## Consequences

- `create-forge --version` reports `0.3.0`; `doctor` and `doctor --json` report
  `forge-template>=0.4.1,<0.5` without importing the engine.
- The normal all-extras development environment and fast compatibility suite
  exercise the immutable PyPI `0.4.1` package. `0.4.0` remains documented as
  the release that introduced Data Science, but it is no longer accepted by
  this client line.
- The optional-extra, lazy-import, protocol negotiation, catalogue ownership,
  filesystem staging, and default-Copier invariants are unchanged.
- Installed-console Data Science E2E expansion is CF-14.02; existing-path and
  failure regressions are CF-14.03. This issue adds neither.
- No create-forge tag or release is created, and `CHANGELOG.md` remains
  untouched until CF-14.04 can include the complete Stage 14 history.
