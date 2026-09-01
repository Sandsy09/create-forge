# 22. Downstream organisation-policy consumption hook

## Status

Accepted

## Context

[Issue #53 / CF-09.01](https://github.com/Sandsy09/create-forge/issues/53)
opens [CF-EPIC-09](https://github.com/Sandsy09/create-forge/issues/40)
(Blueprint Compatibility). It is a `type:decision` issue: document how a
future Blueprint-style CLI applies organisation policy while reusing the same
`forge-template` engine contract. It blocks #54 and, transitively, #55 — the
whole remaining epic.

`forge-template`'s side of Stage 09 is complete: FT-09.01–09.05 published the
canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md),
the
[safe extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
a
[policy reference fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
a
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and a
[no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md)
(ADRs 0038–0042). The protocol document assigns the remaining half
explicitly: *"A downstream client owns its own resolver implementation,
policy-source trust, and ProjectSpec construction."* Today `create-forge`
leaves `ProjectSpec.provenance` empty and has no way to represent whether a
selection was explicitly supplied — a gap
[docs/project-spec-construction.md](../project-spec-construction.md) already
names #53 as owning.

Before deciding anything, the following was verified against the real
installed `forge-template 0.3.1` engine:

| Question | Answer |
| --- | --- |
| Does the installed engine ship any policy API? | No. No `organisation_policy` module, no parser, no policy `EngineErrorCode`. The protocol document says outright that "no parser, resolver, or public Python API is implemented yet." |
| Does `ProjectSpec.provenance` work today? | Yes — `provenance.policies` survives `parse_project_spec` → `validate_project_spec` unchanged, and comes back canonicalised in lexical order. |
| What does the real catalogue contain? | Only two archetypes, `library` and `cli`. No capability or platform components exist yet. |
| Does the engine already validate selections against the catalogue? | Yes — an unknown component id is rejected as `invalid-component-selection` before any render is attempted. |
| Are forge-template's policy fixtures installable? | No — `tests/fixtures/organisation_policies/` is repository-only test data, not package data. |

Those findings rule out one candidate shape directly: a policy parser and
merge resolver living in `create-forge` would reimplement catalogue
validation the engine already performs, could exercise no real
capability/platform rule against any actual component, and would duplicate
work the protocol document says `forge-template` intends to own as *"the
future shared validation semantics."* #53's own final acceptance criterion,
and #55's, both forbid exactly that duplication.

[ADR 0008](0008-fork-model-for-organisations.md) named forking this
repository as the supported path for organisation-specific behaviour, before
the public-engine target existed. [ADR 0010](0010-public-engine-integration-contract.md)
already narrows this in prose for the target architecture; this record
documents that narrowing formally rather than leaving ADR 0008 to keep
reading as current, unqualified guidance.

## Decision

**The hook is `pipeline.build_generation_request`.** This is create-forge's
existing "construct the effective ProjectSpec" step — the shared
discover → build → validate → render pipeline every `--engine-preview`
invocation already runs through. A policy-aware client resolves organisation
policy immediately before calling it and passes the result in through two new
parameters:

- `selection: SelectionRequest` — the effective archetype/capabilities/
  platforms selection, plus which of those kinds were explicitly supplied.
- `provenance: SelectionProvenance | None` — the applied policy IDs to record,
  threaded straight through to `ProjectSpec.provenance` with no merging or
  interpretation performed on this side.

**A typed seam, not optional parameters and not documentation alone.**
`src/create_forge/spec.py` (engine-free, as always) gains `SelectionKind`, a
frozen `SelectionRequest` with a `SelectionRequest.of(...)` constructor, and a
frozen `SelectionProvenance`. Protocol v1 states that ProjectSpec "cannot
reconstruct" whether a selection kind was explicit or left to a policy
default; that distinction has to live somewhere between policy resolution and
ProjectSpec construction, and a typed value the type checker can hold a
caller to is more durable than a documented convention on two `Optional`
keywords. `SelectionRequest.of` turns `None` (absent — a policy default may
still apply) versus an empty sequence (an explicit choice of "none") into
membership in a `frozenset[SelectionKind]`, matching the protocol's own
wording exactly: *"An explicitly empty list is still an explicit choice."*

`build_spec_payload`'s existing `archetype`/`capabilities`/`platforms`
parameters are unchanged in shape — they already carried the *effective*
selection, which is all a pure payload mapper needs — so its roughly twenty
existing call sites needed no change beyond the new keyword-only
`provenance`, emitted only when non-empty, matching the module's existing
omit-when-absent convention for `component_options`.

**`create-forge` ships no resolver and reads no policy document.** It stays
policy-free: no new CLI option, no new `config.toml` key, no exit status. Only
effective selections and applied policy IDs may ever cross into
`build_generation_request` — never a policy document, a file path, or
anything resembling one. This is deliberate, not an oversight the next issue
must fill in: `forge-template` owns the wire contract and intends to own
shared validation semantics; duplicating a resolver here would create a
second implementation to keep in sync with a protocol this repository does
not control, exactly what #53's own final criterion and #55 forbid. A
Blueprint-style downstream client is free to source policy documents however
it chooses — an explicit local path, a fetched and locally-trusted document,
whatever fits that client's own trust model — but that choice belongs to the
client, not to `create-forge`.

**A containment guard stands in place of a design review for every future
change to this seam.** `SelectionRequest` and `SelectionProvenance` hold only
identifiers: strings, tuples of strings, or `None`. `tests/test_policy_hook.py`
asserts both types' field sets and field type shapes exactly, in the spirit
of `tests/test_archetype_parity.py`'s AST guard against a hardcoded component
id. A future field that could smuggle a path, file content, a component
option, or a callable hook fails that test immediately rather than silently
widening what "policy" is allowed to carry — the executable form of #53's
"prevent policy from becoming an arbitrary file or code-execution overlay"
criterion.

**ADR 0008 is superseded, not merely narrowed in prose.** Its Status becomes
`Superseded by ADR 0022`; its body is left untouched, per
[ADR 0001](0001-record-architecture-decisions.md)'s immutability rule. The
fork path it names remains real but narrower: appropriate for genuinely
custom executable template content, not for organisation defaults, required
selections, or forbidden selections, which the downstream-client path this
record defines is now the preferred route for.

## Consequences

- [#54 / CF-09.02](https://github.com/Sandsy09/create-forge/issues/54) has a
  concrete seam to demonstrate: a minimal example can call
  `SelectionRequest.of(...)`/`SelectionProvenance(...)` with neutral
  placeholder policy data and show the whole path end to end, without
  inventing its own construction API.
- If `forge-template` later ships public policy-resolution semantics of its
  own, `create-forge` adopts them at that boundary rather than retiring a
  competing implementation it never built.
- `docs/organisation-policy-consumption.md` is the living contract this
  record establishes; unlike this ADR, it is expected to change as the
  Blueprint-compatibility story continues.
- `docs/project-spec-construction.md`, `docs/integration-contract.md`,
  `docs/cli-conventions.md`, `README.md`, `CLAUDE.md`, and `CONTRIBUTING.md`
  are updated to describe the delivered hook rather than a future one.
- No `forge-template` change resulted from this work; nothing here hands a
  responsibility back to the engine.
