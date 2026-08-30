# Cross-Repository Engine Contract Tests

This is the canonical executable contract for the development-only boundary
between `create-forge` and `forge-template`. It records what Stage 06 proved,
what CF-07.04 (ADR 0015) added on top of it, and what CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved the pin to,
before the public engine is installed by, or reachable from, a released CLI.

## Tested development pair

| Surface | Tested value |
| --- | --- |
| `forge-template` package | `0.3.0` |
| Source | `tag = "v0.3.0"` |
| ProjectSpec protocol | `1` |
| Component-manifest protocol | `1, 2` |

`pyproject.toml` declares `forge-template==0.3.0` only in the `engine`
development group and maps it to the tag above via `[tool.uv.sources]`. This
exact pair is not a released compatibility range: the runtime dependency
and its tested lower/upper bounds remain unassigned until
[PyPI/distribution issue #9](https://github.com/Sandsy09/create-forge/issues/9)
and the atomic CLI cutover in
[CF-07.04 / #50](https://github.com/Sandsy09/create-forge/issues/50).

The pinned source has moved twice. First, from Stage 06's original commit to
a later commit, adopted by
[CF-07.04 / #50](https://github.com/Sandsy09/create-forge/issues/50)
specifically to pick up `forge-template`'s
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md):
`render_project` now calls the public `validate_rendered_project` before
returning, so a `RenderedProject` this adapter receives has already passed
that check. Second, from that commit to the `v0.3.0` tag, adopted by
[CF-08.02 / #10](https://github.com/Sandsy09/create-forge/issues/10) to reach
the first tagged, production-catalogue release — a tag rather than a commit
SHA this time, since `v0.3.0` is a real independent release and the reason
ADR 0013 gave for pinning `0.2.0` to a commit (no tag existed to move to) no
longer applies. The package version and both protocol numbers moved with it;
`[project.dependencies]` remains unaffected — no engine range is assigned by
either move.

Any other package version fails closed. Adopting even a nominally compatible
`0.3.x` development version requires updating the pin, this table, and the
contract tests together.

## What the executable contract proves

[`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
exercises the installed engine through `src/create_forge/engine.py`. Together
with the focused adapter and guard suites, it proves that:

- the installed package advertises the exact package and protocol pair above;
- package and relevant protocol compatibility are checked before parsing,
  discovery, validation, or rendering calls reach the engine;
- malformed ProjectSpec and invalid component selections remain structured,
  engine-owned failures;
- discovery returns the installed production catalogue without registry
  fallback;
- rendering returns immutable in-memory files, already validated by
  `forge_template.validate_rendered_project`, and never owns destination
  writes; and
- the adapter imports only names re-exported by the top-level public
  `forge_template` facade.

The production catalogue ships both `library` and `cli`, since
[forge-template FT-08.02 / #41](https://github.com/Sandsy09/forge-template/issues/41)
migrated the Library archetype and FT-08.04 added the CLI Application
archetype in the same `0.3.0` release. Therefore the current client-side
rendering assertion is a real public-facade call that now succeeds for
either archetype and returns real files. `create-forge` still does not
import `forge-template`'s private fixture-catalogue seam or its own
[`tests/test_composition_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/test_composition_contract.py)
goldens; this contract proves the public facade only.

That non-empty catalogue is also what CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) needed to make
`--engine-preview` generate a real project for the first time. It does not,
by itself, close
[CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51)'s
[end-to-end suite](end-to-end-tests.md) engine-path gap: that suite still
covers the Copier path only, since **CF-08.04**, under
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39), needs a
*released, range-assigned* engine, not merely a non-empty development
catalogue — it remains blocked on
[#9](https://github.com/Sandsy09/create-forge/issues/9).

## Validate a sibling checkout

The normal fast suite uses the immutable Git source in `uv.lock`. To validate
pending sibling changes, install both working trees into an isolated
environment and run the same focused contract file:

```bash
uv run --no-project --isolated --with . --with ../forge-template --with pytest python -m pytest -o addopts= tests/test_engine_cross_repository.py
```

Local path builds include current working-tree source, including uncommitted
changes. The sibling package must still declare version `0.3.0`; a version
bump is a new development pair and must be adopted explicitly. The broader
[cross-repository contributor workflow](cross-repository-workflow.md) defines
the remaining validation and release order.

If the sibling checkout has moved (a new commit, or edited source files)
since the last time this command ran in the same environment, add
`--no-cache` -- `uv run --with <local-path>` has been observed reusing a
previously built archive for that path without detecting the source change,
which silently tests against old sibling code rather than the one intended.

## Cutover boundary

The atomic cutover -- replacing this exact development assertion with the
first installable, bounded engine dependency -- happens only after #9
selects a distribution channel, in whichever future issue does that work.
That change must test the declared lower bound and a representative latest
compatible release, update the integration compatibility table, and keep the
same fail-before-side-effects behavior. Neither Stage 06, CF-07.04, nor
CF-08.02 pre-assigns those values -- each only moves the development pin
forward, most recently to the first tagged release.
