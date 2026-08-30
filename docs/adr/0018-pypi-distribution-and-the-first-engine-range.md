# 18. Publish to PyPI and assign the first bounded engine range

## Status

Accepted

## Context

[Issue #9](https://github.com/Sandsy09/create-forge/issues/9) has always
owned two things its own body separates: publishing `create-forge` itself to
PyPI, and the installable-distribution decision ADR 0010 deferred for the
engine — "`forge-template` remains `Private :: Do Not Upload` and has no
installable index release, so create-forge cannot yet declare the bounded
runtime engine dependency required by ADRs 0010-0012." The second half is
[#85 / CF-08.04](https://github.com/Sandsy09/create-forge/issues/85)'s sole
remaining native blocker: its acceptance criteria need proof "against the
released range," and no released range could exist while `forge-template`
was git-only — PyPI rejects `@ git+...` direct references, and
`[tool.uv.sources]` is workspace-local `uv` configuration, stripped from
published package metadata entirely. Assigning a range therefore requires
`forge-template` to be installable first.

Both names were unclaimed on PyPI, confirmed directly (`/pypi/create-forge/json`
and `/pypi/forge-template/json` both `404`) before any of this work began.

Scoping surfaced a real defect on the `forge-template` side:
`src/forge_template/render.py` and `schema.py` import `yaml` at module level,
but `pyyaml` was never declared in `[project.dependencies]` — harmless only
because nothing had ever installed the package standalone
([forge-template#8](https://github.com/Sandsy09/forge-template/issues/8)).
Those two modules, plus `adr.py` and `github_actions.py`, are this
repository's own CI tooling: they inspect `copier.yml`, `docs/adr/`, and
`template/` — paths that do not exist once the package is installed
elsewhere. `forge_template/__init__.py` never imports them; the public
facade itself needs only `jinja2`, `packaging`, and `pydantic`, exactly what
was already declared.

## Decision

**Publish both packages to PyPI via Trusted Publishing (OIDC).** No stored
token; each repository's `release.yml` gains a `publish` job gated by a
`pypi` GitHub Environment, running only on a real (non-`dry_run`) dispatch,
after the tag/release step succeeds. Sequenced `forge-template` first, since
`create-forge[engine]`'s declared range needs a real release to point at —
see [forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md)
for that repository's side, including how it resolves the `pyyaml` defect by
**excluding** `adr.py`/`render.py`/`schema.py`/`github_actions.py` from the
built wheel rather than declaring `pyyaml` a runtime dependency for four
modules that cannot function outside that checkout regardless.
`forge-template` publishes `0.3.1` — a packaging-only patch over the same
`0.3.0` production catalogue CF-08.02 already adopted, not a behaviour
change. `create-forge` publishes `0.2.0`, reflecting the real feature surface
added since `v0.1.0` (the engine construction boundary, `pipeline.py`,
`staging.py`, `--engine-preview`, `--archetype`).

**Declare the range as an optional extra, not a hard dependency:**

```toml
[project.optional-dependencies]
engine = ["forge-template>=0.3.1,<0.4"]
```

The alternative — moving `forge-template` into `[project.dependencies]` —
would make every `uvx create-forge` invocation resolve and download an
engine the default `new` path never calls, and would turn ADR 0014's
guarded `try/except ImportError` in `cli.py` into dead code contradicting
its own record: that decision's entire premise is that `forge-template`
"stays a development-only dependency" (now: an optional one) so no module
reachable at `cli.py`'s own import time may depend on it. An extra preserves
that boundary exactly while finally giving it a real, installable target —
`pip install 'create-forge[engine]'` or `uv sync --all-extras`.

**Delete the development-only `[tool.uv.sources]` pin and `engine`
dependency group entirely.** They are not layered underneath the new range;
they are replaced by it. Cross-repository development against an unreleased
`forge-template` checkout still works, unchanged, via a local (uncommitted)
`[tool.uv.sources]` override or the sibling-checkout command in
`docs/cross-repository-workflow.md` — that mechanism was never the committed
pin itself, just what the pin's presence in this file made convenient to
demonstrate.

**Add `src/create_forge/compat.py`**, engine-free by construction (no
`forge_template` import, not even under `TYPE_CHECKING` — the same rule
`staging.py` already follows), holding `SUPPORTED_ENGINE_RANGE`,
`SUPPORTED_PROJECTSPEC_PROTOCOLS`, and `SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS`.
`engine.py` imports these to check an installed package with
`packaging.specifiers.SpecifierSet` instead of the exact-equality check the
development-only pair used before a real release existed. `cli.py`'s
`doctor` command imports the same constants — never `engine.py` itself — so
it can report `integration.engine_range` and
`integration.projectspec_protocol.supported` unconditionally, and
`integration.engine_package` via `importlib.metadata` alone, all without
violating ADR 0014's reachability rule. `integration.projectspec_protocol.detected`
stays `null`: populating it needs a real `get_engine_info()` call, which only
`--engine-preview` makes.

**Add a second Dependabot compatibility-line gate.** `forge-template` joins
`copier` as a dependency ADR 0012 governs: pre-1.0, a minor bump is itself a
breaking line, so `.github/dependabot.yml`'s `uv` entry ignores both
`semver-major` and `semver-minor` for it, not just `semver-major` as for
`copier`.

## Consequences

- `pip install create-forge` and `pip install 'create-forge[engine]'` both
  work from PyPI for the first time. `#85 / CF-08.04`'s sole remaining native
  blocker — a released, range-assigned engine to test against — is cleared;
  writing that end-to-end coverage remains its own separate work.
- `docs/engine-resolution.md`'s "Assigning the first engine range" checklist,
  written by ADR 0014 with no owning issue, is executed here and folded into
  the document's ordinary "Normal installed resolution" section rather than
  kept as a standing future-work list.
- This is **not** the CLI cutover ADR 0010/0011 describe. The default `new`
  command remains the v0.1.x direct-Copier path, `--template-url` is
  unchanged, and `--engine-source`/`--engine-ref` still do not exist. Every
  living contract this decision touches (`docs/engine-resolution.md`,
  `docs/integration-contract.md`, `docs/engine-contract-tests.md`,
  `docs/component-discovery.md`, `docs/project-spec-construction.md`,
  `docs/cli-conventions.md`, `docs/engine-updates.md`,
  `docs/cross-repository-workflow.md`, `docs/end-to-end-tests.md`,
  `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`) says so explicitly, to keep
  "a range is assigned" from being misread as "the engine is now the default
  path."
- `tests/test_engine_contract.py`'s exact-pin assertions
  (`test_development_engine_pair_is_exact_and_immutable`, the
  no-engine-dependency guard) are replaced by range assertions; the adapter
  and cross-repository suites gain explicit below-lower-bound and
  at-or-above-upper-bound rejection cases, since a range — unlike an exact
  pin — has two edges to characterize.
- `create-forge`'s own CI (`ci.yml`, `release.yml`) adds `--all-extras` to
  every `uv sync` so the fast suite's real engine-adapter tests keep running
  unattended; `forge-template`'s CI gains a `wheel` job proving the
  facade/tooling split holds on every push, mirroring `create-forge`'s own
  `invariant 5` wheel check that this ADR's authors reused as the pattern.
