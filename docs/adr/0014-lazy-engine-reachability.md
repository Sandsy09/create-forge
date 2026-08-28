# 14. Reach the engine from a command through a lazy, opt-in preview flag

## Status

Accepted

## Context

[CF-07.01](https://github.com/Sandsy09/create-forge/issues/49) is the first
child of [CF-EPIC-07](https://github.com/Sandsy09/create-forge/issues/38),
unblocked by CF-06.01 (#46) and CF-06.02 (#47), with CF-06.03 (#48) since
proving the exact `forge-template==0.2.0` / ProjectSpec-protocol-1 /
component-manifest-protocol-1 development pair end to end. `src/create_forge/spec.py`
and `src/create_forge/engine.py` expose a complete, tested boundary —
negotiate → discover → build → validate → render — but nothing calls it: it
remains dormant, exactly as [ADR 0013](0013-projectspec-construction-boundary.md)
left it.

Two documents written during CF-06.02/CF-06.03
([`docs/project-spec-construction.md`](../project-spec-construction.md),
[`docs/cli-conventions.md`](../cli-conventions.md)) commit to a specific
claim about this issue: that it "wires this boundary into `create-forge
new`, making ProjectSpec construction, discovery, and exit status 3
reachable for the first time." Honouring that claim runs into a real
constraint. `forge-template` is still a **development-only** dependency —
absent from `[project.dependencies]`, no released range, gated on
[#9](https://github.com/Sandsy09/create-forge/issues/9) — because it cannot
yet be one: `forge-template` `0.2.0` has no PEP 440 tag, and a direct git
reference cannot express the bounded lower/upper range the integration
contract requires. `engine.py` performs a top-level `from forge_template
import ...`. If `cli.py` imported `engine.py` (directly or transitively) at
its own module level, then `create-forge --help`, `list`, `doctor`, and
ordinary `new` would all raise `ModuleNotFoundError` for every real `uvx
create-forge` install, which never receives the `engine` dependency group.
"Reachable from a command" and "the wheel must not depend on
`forge-template` to run" are both real requirements, and they are in
tension.

## Decision

**A hidden, opt-in flag, imported lazily.** `new` gains `--engine-preview`
(`hidden=True` — absent from `--help`, still a real, invokable option).
`cli.py`'s only reference to the pipeline is a local `from create_forge
import engine, pipeline` executed *inside* `--engine-preview`'s branch,
wrapped in `try/except ImportError`. Every other command, and `new` without
the flag, therefore never attempt this import and remain completely
unaffected by whether `forge-template` is installed. When it is not, the
`except ImportError` branch prints an actionable message — "run `uv sync
--all-groups` in a `create-forge` checkout" — and exits `1`, rather than
letting a raw traceback escape.

**Named to avoid a future collision.** `--engine-preview` is deliberately
not `--engine`: [ADR 0011](0011-engine-source-and-version-resolution.md)
already reserves `--engine-source`/`--engine-ref` as the *future* public
override interface at the coordinated atomic cutover. `--engine-preview` is
a different, temporary, development-only flag and must not be confused with
that reserved pair, nor promoted into it — it is retired, not renamed, once
the real cutover (gated on #9 and CF-07.04) ships.

**The shared pipeline runs through `render()`, still entirely in memory.**
A new module, `src/create_forge/pipeline.py`, is the second (and last)
module allowed to *depend on* the engine, but not a second module whose
*source* imports `forge_template` directly: its own top-level imports are
`create_forge.engine` and `create_forge.spec` (both `create_forge`, not
`forge_template`), and it uses `if TYPE_CHECKING: from forge_template import
ProjectSpec, RenderedProject` for its own type annotations only, so those
imports never execute at runtime. This keeps ADR 0013's "`engine.py` is the
only module whose source touches `forge_template`" literally true while
`pipeline.py` remains fully mypy-strict typed. `build_generation_request()`
runs `engine.discover()` → `spec.build_spec_payload()` →
`engine.build_project_spec()` → `engine.validate()` → `engine.render()` and
returns a `GenerationRequest` (the validated `ProjectSpec` plus the in-memory
`RenderedProject`). `render()` was already in-memory only — no destination
path, no filesystem write — so wiring it in here changes nothing about that
guarantee; CF-07.04 still owns staging, atomic move-into-place, and cleanup.

**`cli.py` never imports `forge_template` by name, lazily or not.** The
`except` clauses in `_run_engine_preview` reference
`engine.EngineCompatibilityError` and `engine.ForgeEngineError` as attribute
expressions on the locally-bound `engine` module, not as `from
create_forge.engine import ...` statements — this is what a
`from create_forge.engine import ForgeEngineError` statement would trigger
under `mypy --strict`'s `no_implicit_reexport` (since `ForgeEngineError` is
itself an import into `engine.py`, not something it defines), which attribute
access on an already-bound module reference does not. `ForgeEngineError`
still needed one explicit self-reexport line in `engine.py`
(`from forge_template import ForgeEngineError as ForgeEngineError`) to
satisfy the same check for the *direct* `from create_forge import engine`
`cli.py` performs — a mechanical mypy-strict requirement, not a change to
which module may import `forge_template`.

**It always fails today, by design.** `forge-template` `0.2.0`'s production
catalogue is intentionally empty until Stage 08. `--engine-preview` therefore
deterministically fails at `validate()` with `invalid-component-selection`
today, exactly the class of characterized failure ADR 0013 already
established for `engine.validate()`/`engine.render()` in isolation — this
decision makes that same failure reachable from a real command, not
resolves it.

**Component selection stays caller-supplied.** `--engine-preview` passes
`archetype=template.id` (today: `"library"`, the bundled registry's only
entry), empty capabilities/platforms/options — reusing today's
`_select_template`/`_collect_answers` machinery unchanged rather than adding
a parallel prompt system. `engine.discover()` still runs for real, proving
the compatibility ladder executes and surfacing real descriptors to future
callers, but its result does not yet drive selection: there is nothing
non-empty to select from until Stage 08, and building real selection UX
against permanently-empty data would be untestable.

## Consequences

- `create-forge --help`, `list`, `doctor`, and `new` without
  `--engine-preview` are provably unaffected by whether `forge-template` is
  installed — proven by building a wheel and running it in an isolated
  environment with the dependency absent, mirroring CF-06.01's equivalent
  verification.
- Exit status `3` becomes reachable from a real command for the first time,
  via `--engine-preview`'s `EngineCompatibilityError` branch — but only
  behind that hidden flag; the default `new` path still cannot produce it.
- `--engine-preview` is explicit development-only surface, not a preview of
  the eventual public flag names. It is retired, not renamed, at the actual
  cutover; the release notes for that cutover must say so.
- `docs/project-spec-construction.md`, `docs/cli-conventions.md`, and
  `docs/component-discovery.md`'s "what changes next" language, written
  before this issue landed, are corrected to describe what actually shipped
  rather than what was anticipated.
- Nothing about v0.1.x behaviour changes for a user who never passes
  `--engine-preview`. No engine range is assigned; that remains blocked on
  [#9](https://github.com/Sandsy09/create-forge/issues/9).
