# 19. CLI archetype-parity review

## Status

Accepted

## Context

[Issue #52 / CF-08.03](https://github.com/Sandsy09/create-forge/issues/52)
is a `type:decision` review, not a feature: verify `create-forge` remains
generic after driving the materially different Library and CLI Application
archetypes through the accepted public engine. It was blocked on
[#10 / CF-08.02](https://github.com/Sandsy09/create-forge/issues/10), which
exposed `cli` behind `--engine-preview --archetype`
([ADR 0017](0017-cli-application-archetype-exposure.md)). #10 closed complete,
and [#9](https://github.com/Sandsy09/create-forge/issues/9)
([ADR 0018](0018-pypi-distribution-and-the-first-engine-range.md)) then made
both archetypes reachable from a plain `pip install 'create-forge[engine]'`,
so this review finally has two real, installable archetypes to compare
instead of a hypothesis about a catalogue that did not yet exist.

The issue's eight acceptance criteria reduce to five questions, each answered
empirically against the installed `forge-template>=0.3.1,<0.4` engine:

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | Compare prompt and flag code paths for both archetypes | deviation found |
| 2 | Remove archetype-specific branching that belongs in forge-template | one branch found |
| 3 | Both modes build valid ProjectSpec through one generic construction path | confirmed |
| 4 | Discovery and compatibility remain engine-owned | confirmed |
| 5 | `repository_name` is the only CLI Application command identity | confirmed |

**Criteria 3, 4, 5.** `spec.build_spec_payload` and
`pipeline.build_generation_request` take the same `answers` mapping and
`archetype` string for both archetypes; the payloads they build are
structurally identical apart from `components.archetype` and
`component_options`. `pipeline.discover_archetypes()` filters
`engine.discover()`'s result on `kind == "archetype"` and returns the
engine's own `ComponentDescriptor` values unchanged —
`tests/test_engine_adapter.py::test_discover_preserves_public_component_descriptors`
already proves that pass-through. No `command_name` field exists anywhere in
`src/`, `templates.toml`, or the Pydantic registry models; a real `cli`
render's `[project.scripts]` entry is exactly `ProjectSpec.project.repository_name`
(confirmed against the installed engine: `project_name` "Credit Risk Utils"
→ `repository_name` `credit-risk-utils` → script name `credit-risk-utils`).

**Criterion 2.** [`pipeline._resolved_component_options`](../../src/create_forge/pipeline.py)
gated the legacy Library option mapping on:

```python
if component_options is not None or archetype != "library":
```

[ADR 0017](0017-cli-application-archetype-exposure.md) accepted this
deliberately and named it "the one archetype-specific branch in this
codebase" — this is exactly the branch criterion 2 asks this review to
adjudicate.

**Criterion 1.** `--engine-preview` deliberately reuses the Copier registry's
answer collection ([ADR 0014](0014-lazy-engine-reachability.md)), and
`templates.toml` has one template whose eight questions are Library
questions. Measured for both archetypes:

| Registry question | Reaches ProjectSpec? |
| --- | --- |
| `project_name`, `project_description`, `license` | both |
| `build_backend`, `versioning` | `library` only — silently discarded for `cli` |
| `github_org`, `type_checking`, `use_docs` | discarded for both |

The archetype is also selected *after* these answers are collected, so a
user building a CLI Application still answers `build_backend`. This is real,
but it is a consequence of the v0.1.x registry seam the coordinated engine
cutover ([ADR 0010](0010-public-engine-integration-contract.md),
[ADR 0011](0011-engine-source-and-version-resolution.md)) is what retires —
not of archetype-specific code in this repository. `cli`'s own discovered
descriptor already declares no options at all, so nothing is silently
misapplied to it; the defect is unused prompts and a hardcoded skip, not
incorrect ProjectSpec construction.

## Decision

**Confirm the generic path (criteria 3, 4, 5) as-is** — no code changes were
needed to satisfy them; this record is their proof.

**Generalise criterion 2's branch to be descriptor-driven, not
archetype-id-driven.** `engine.map_legacy_library_options` already names the
option it produces (`packaging_mode`); the selected archetype's own
discovered `ComponentDescriptor.options` already declares whether it accepts
that name. `_resolved_component_options` now looks up the selected
archetype's descriptor (from the `engine.discover()` result
`build_generation_request` already fetched and had been discarding) and
applies the mapping only when the descriptor declares every option name the
mapping produces:

```python
descriptor = next((d for d in descriptors if d.id == archetype), None)
if descriptor is None or not descriptor.options:
    return None
...
if not set(mapped) <= {o.name for o in descriptor.options}:
    return None
return {archetype: mapped}
```

`library` declares `packaging_mode` and `initial_version`, so it applies;
`cli` declares no options at all, so the mapping call is skipped before it
ever runs — matching the old code's behaviour of never invoking
`map_legacy_library_options` for a non-`library` archetype, without naming
either archetype to get there. The result: zero archetype-id literals remain
in `src/create_forge/`, verified by a new AST guard
(`tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id`)
that fails if any shipped module ever compares a string literal against a
currently-discovered component id again.

**Leave criterion 1's deviation in place, and record it rather than fix it
here.** Making the engine path prompt from `ComponentDescriptor.options`
instead of the Copier registry means it stops sharing the Copier path's
answer collection — a change to `docs/cli-conventions.md`'s explicit "reuses
the same answer collection ... no parallel prompt flow" — and moves
discovery ahead of the destination-conflict check, changing "rejects a
non-empty destination before any engine call" too. Both are `--engine-preview`
contract changes, which a `type:decision`, `size:s` review is the wrong place
to make unilaterally.
[Issue #91](https://github.com/Sandsy09/create-forge/issues/91) tracks it
instead.

**No `forge-template` change.** This review is create-forge-only; it found
no responsibility to hand back to the engine — `forge-template` already
returns descriptors with exactly the shape this generalisation needed.

## Consequences

- `pipeline._resolved_component_options` no longer contains the string
  `"library"` in a comparison; `tests/test_pipeline.py` gains two cases the
  old branch made inexpressible — a non-`library` id that declares
  `packaging_mode` still receives the mapping, and an archetype that
  declares options but not the mapped ones is skipped.
- `tests/test_archetype_parity.py` is this review's executable record:
  shared-payload-shape, shared-pipeline, `cli`'s empty-options descriptor
  driving an empty `component_options`, the no-`command_name` sweep, the
  `repository_name`-is-the-command proof, and the AST regression guard.
- ADR 0017's "the one archetype-specific branch in this codebase" is
  superseded in fact by this decision. ADRs are immutable
  ([ADR 0001](0001-record-architecture-decisions.md)) — ADR 0017 is not
  edited; this record is what documents the change.
- `docs/project-spec-construction.md` and `docs/cli-conventions.md` are
  updated to describe the descriptor-gated derivation and the
  consumed/discarded prompt table above.
- [Issue #91, "Prompt engine component options from discovery, not the
  Copier registry,"](https://github.com/Sandsy09/create-forge/issues/91) is
  filed as standalone backlog (alongside #8, #9, #25, #26) rather than a new
  roadmap item, since it is cutover-adjacent rather than a bounded piece of
  Stage 08.
- Stage 08's only remaining open item is
  [#85 / CF-08.04](https://github.com/Sandsy09/create-forge/issues/85).
