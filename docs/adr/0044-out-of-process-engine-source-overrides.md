# 44. Run `--engine-source` overrides out of process

## Status

Accepted

## Context

ADR 0011 reserved `--engine-source <local-path|vcs-url>` and `--engine-ref
<ref>` as the engine cutover's local-development escape hatch; ADR 0040
(CF-18.01) specified the interface further -- an isolated ephemeral
environment, `--template-url`'s source validation, an unconditional
code-execution warning, and the same public compatibility check the
installed engine passes, failing closed at exit `3` with no fallback. CF-18.01
adopted the engine as the default, required `new` path but reserved these two
flags without implementing them (`tests/test_engine_default_contract.py`'s
`test_tripwire_new_has_no_engine_source_override_flags`). CF-18.02 (#159) is
that implementation.

The load-bearing constraint is rule 25: "the installed engine is never
imported, shadowed, or modified. There is no in-process `sys.path`
injection." `engine.py` is the one module that imports `forge_template`
(invariant 4, ADR 0013) -- and it imports the *installed* distribution, at
Python's own module-cache granularity. There is no supported way to ask
CPython's import system for "this same module name, but a second,
differently-versioned copy" in one process: `importlib` caches by module
name in `sys.modules`, and a second `forge_template` shadowing the first
either fails outright (name collision) or succeeds by replacing the first,
which is exactly the "shadow the installed engine" rule 25 forbids. A
`--engine-source` render therefore cannot share a process with `cli.py`'s own
`forge_template` import, whatever mechanism provisions it.

## Decision

1. **The provisioned engine runs in a separate process, communicating over a
   JSON request/response protocol on stdin/stdout.** `--engine-source
   <path|vcs-url>` (+ optional `--engine-ref`) is resolved to a `uv pip
   install` requirement (`engine_source.build_requirement`) and installed
   with `uv venv` + `uv pip install --python <venv>` into a throwaway
   environment under the system temp directory, containing *only* that
   engine and its own dependencies -- deliberately never `create-forge`
   itself. `engine_source.py` (engine-free, like `sources.py`/`staging.py`/
   `compat.py`) provisions the environment, invokes the worker three times
   (`info`, `discover`, `render`), and translates its structured JSON
   response; it never imports `forge_template`.

2. **`_engine_worker.py` is the out-of-process mirror of `engine.py`.** It is
   a plain script -- located on disk with `importlib.resources` and run as
   `<venv-python> _engine_worker.py <op>`, never imported as
   `create_forge._engine_worker` by the parent, since the provisioned
   environment does not have `create-forge` installed to import it *into*.
   It imports only the stdlib and the public `forge_template` facade
   (mirroring `engine.py`'s own "public facade only" rule), and is the
   second and only other module invariant 4 (ADR 0013) permits to touch
   `forge_template` -- amended from "engine.py is the only module" to
   "engine.py in process, `_engine_worker.py` out of process," since the two
   can never run in the same interpreter and therefore never collide.

3. **The compatibility check lives once, in `compat.py`, as plain-value
   functions.** `EngineCompatibilityError` and the four `require_*` checks
   moved out of `engine.py` into `compat.py`, taking a package version and
   protocol tuples directly rather than an `EngineInfo` instance.
   `engine.py`'s existing `_require_*` wrappers now delegate to them,
   unchanged in behaviour, message text, and exception identity.
   `engine_source.negotiate` calls the identical functions against the
   worker's `info` response. This is what makes rule 28 literal -- "the
   resolved engine passes the same compatibility check" -- rather than two
   independently written checks that could quietly drift apart across a
   future protocol change.

4. **Descriptors cross the process boundary as data, not as a shared type.**
   `pipeline.Catalogue.descriptors` is retyped from the concrete
   `forge_template.ComponentDescriptor` to `create_forge.descriptors
   .DescriptorView`, a structural `Protocol` (extending the
   `id`/`name`/`description`/`options` shape `prompts.ArchetypeChoice`
   already defines with the `kind`/`requires` `Catalogue` also needs). The
   engine's own `ComponentDescriptor` satisfies it unchanged; `--engine
   -source`'s worker JSON is deserialised into a new frozen, `extra=
   "forbid"` `Descriptor` model in the same module, which also satisfies it.
   Every selection/prompt function in `prompts.py`/`cli.py` already types
   against `ArchetypeChoice`, a subset of `DescriptorView` -- so both
   generation routes reuse archetype selection, capability/platform
   selection, and per-component-option prompting verbatim, with no branch
   in any of that shared code for which route is active.

5. **Finalisation is shared through a new `pipeline.finalise_files`, not a
   `RenderedProject`.** The override route cannot construct a real
   `forge_template.RenderedProject` (that would require importing
   `forge_template` in the parent, which rule 25 forbids). `engine_source
   .render` instead returns plain `(target, content)` byte pairs;
   `pipeline.finalise_files` is the staging/lock/atomic-rename body
   `finalise_generation_request` already had, lifted out and applied to
   either shape.

6. **No generation-metadata document is produced for this route (rule 29).**
   The worker's `render` operation never asks `forge_template` for one, so
   there is nothing to omit at the boundary -- not "produced, then
   discarded." `cli._report_created(..., engine_source=True)` prints its own
   not-eligible line, distinct from the plain "not yet update-eligible"
   wording the default route uses.

## Consequences

- `create_forge.compat` gains `EngineCompatibilityError` and four
  `require_*` functions as public API; `engine.py`'s private wrappers keep
  their names, call sites, and error text, so every existing
  `engine.EngineCompatibilityError`-typed test is unaffected.
- Two new engine-free modules ship: `create_forge.descriptors` (the
  `DescriptorView`/`OptionView`/`RelationView` protocols and their concrete
  `Descriptor`/`Option`/`Relation` mirror models) and `create_forge
  .engine_source` (provisioning, worker invocation, compatibility
  negotiation). `create_forge._engine_worker` ships as a third new module,
  excluded from `tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard
  (which asserts a module *never* imports `forge_template`) exactly as
  `engine.py` already is, since both are now permitted to.
- `pipeline.Catalogue.descriptors`'s type changes from `ComponentDescriptor`
  to `DescriptorView`; `pipeline.finalise_generation_request` becomes a
  one-line wrapper over the new `pipeline.finalise_files`. Neither changes
  either function's runtime behaviour or the shape of `GenerationRequest`,
  so the default engine `new` path is unaffected in every test that already
  exercises it.
- `staging._remove_tree` and `sources._url_source` become the public
  `staging.remove_tree`/`sources.url_source`, reused by `engine_source.py`
  for ephemeral-environment cleanup and source classification respectively
  -- the same rule, applied consistently, rather than a second copy.
- Every `--engine-source`/`--engine-ref` render still writes no
  `.forge/generation.json` and is reported not update-eligible at generation
  time, unchanged from ADR 0040 decision 5.
- This introduces no new runtime dependency for generated projects, no
  provider-side change, and no widened trust boundary beyond what ADR 0011
  and ADR 0040 already accepted: the code-execution warning, `--yes`'s
  confirmation-only skip, and `--template-url`'s credential/query/fragment
  restrictions all apply unchanged.
