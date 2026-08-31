# 21. Finalise engine-generated lockfiles in the client

## Status

Accepted

## Context

The public `forge-template` engine is intentionally side-effect free. It
validates, plans, and renders an immutable project in memory, but it neither
runs commands nor writes dynamic resolution results. The Stage 08 composition
review confirmed that `uv.lock` is required by the Foundation restoration and
quality guarantees while remaining unsuitable for `GenerationPlan` or
`RenderedProject`: its bytes depend on dependency resolution at generation
time rather than reviewed component content.

Before this decision, `create-forge --engine-preview` wrote the reviewed files
to an adjacent staging directory and renamed it atomically, but produced no
lockfile. The resulting project could run `uv run poe check` only by resolving
and creating a lock implicitly after handoff. That was weaker than the
Foundation contract and unlike the direct-Copier path, whose existing tasks
already create a lock. Lock creation must happen without exposing a partial
destination, and failures must use the existing actionable CLI error surface.

## Decision

`create-forge` owns `uv.lock` as a client-finalisation artefact on the engine
path. After writing every `RenderedFile` to the adjacent staging directory,
`pipeline.finalise_generation_request` calls:

```text
uv lock --directory <staging-directory>
```

Only after that command succeeds does the existing staging context atomically
rename the directory into place. The engine facade, ProjectSpec protocol,
component protocols, render plan, and rendered result remain unchanged.

`staging.create_uv_lock` invokes the fixed executable and arguments directly,
without a shell. A missing executable, launch failure, or non-zero exit becomes
an actionable `StagingError`. The surrounding staging context removes the
incomplete tree and preserves the destination exactly as it was found. Raw
subprocess output is not copied into the error because index URLs or resolver
diagnostics can contain credentials.

The optional `engine` extra gains `uv>=0.12,<0.13` alongside
`forge-template>=0.3.1,<0.4`; plain `create-forge` and the default Copier path
remain unchanged. Dry runs return before staging and therefore never invoke
uv. Engine-generated projects document `uv run --locked poe check` as their
canonical validation command and are tested with both `uv lock --check` and
that locked aggregate gate.

## Consequences

- Successful engine generation now returns a project with a current
  version-controlled `uv.lock`, without adding `.git`, `.venv`, hooks, or
  pre-commit installation.
- Dependency resolution can add latency and require configured package-index
  access, but it occurs before the atomic rename and cannot expose a partial
  destination.
- Installing `create-forge[engine]` also installs the bounded uv executable;
  the plain package remains free of the engine and uv additions.
- `forge-template` remains responsible for deterministic reviewed content;
  `create-forge` remains responsible for filesystem orchestration and dynamic
  client finalisation.
- `create-forge` moves to `0.2.1` and consumes compatible
  `forge-template 0.3.2` without changing the existing engine range or any
  protocol support.
