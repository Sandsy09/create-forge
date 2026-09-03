# Downstream Organisation-Policy Consumption

This is the living contributor contract for how `create-forge` supports a
downstream, policy-aware client applying organisation policy while
constructing a ProjectSpec through this repository's shared pipeline. The
canonical policy wire contract, resolution authority order, and future shared
validation semantics remain owned by
[`forge-template`](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md);
this document defines only the client-side hook and what `create-forge`
itself does and does not do with it. [ADR 0022](adr/0022-downstream-organisation-policy-hook.md)
records the decision this document keeps current.

## Status

`create-forge` accepts effective, already-resolved selections and applied
policy identifiers through `pipeline.build_generation_request`'s `selection`/
`provenance` parameters (CF-09.01). It ships no policy parser, resolver, or
merge logic of its own, and no command accepts a policy document or path
today. This is the delivered state, not an interim one awaiting a follow-up
issue — see "What `create-forge` does not own" below for why.

## The hook

`pipeline.build_generation_request` is create-forge's "construct the
effective ProjectSpec" step — the point every `--engine-preview` invocation
already passes through on the way to `engine.build_project_spec`. A
policy-aware client resolves organisation policy immediately before calling
it:

```python
from create_forge.pipeline import build_generation_request
from create_forge.spec import SelectionProvenance, SelectionRequest

selection = SelectionRequest.of(
    archetype=resolved_archetype,  # from policy default, explicit choice, or a required override
    capabilities=resolved_capabilities,  # None if never explicitly chosen; a list, possibly empty, if it was
    platforms=resolved_platforms,
    archetype_explicit=True,
)
provenance = SelectionProvenance(policies=applied_policy_ids)

request = build_generation_request(answers, selection=selection, provenance=provenance)
```

Nothing upstream of this call is create-forge's concern: sourcing a policy
document, deciding whether to trust it, merging multiple policies, applying
`defaults`/`required`/`forbidden` rules, and presenting a conflict to a user
are all resolution steps a client performs against the canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
before this function is ever called.

## The absent-vs-explicit-empty rule

Protocol v1 is explicit that ProjectSpec "cannot reconstruct" whether a
selection kind was explicitly supplied or left to a policy default — an
explicitly empty list of capabilities is a different fact than never having
chosen capabilities at all, and only the caller resolving policy knows which
one happened. `spec.SelectionRequest.of(...)` is where that fact is captured:

- `archetype` has no absent form — ProjectSpec always selects exactly one —
  so its explicitness is `archetype_explicit`, a plain keyword defaulting to
  `True`. `cli.py`'s own caller marks it `False` only when
  `prompts.choose_archetype`'s skip-when-only-one-exists shortcut fired: no
  alternative was ever offered, so a policy default could legitimately still
  apply there.
- `capabilities`/`platforms` follow the protocol directly: passing `None`
  means "no explicit choice for this kind" and membership in
  `SelectionRequest.explicit` is not recorded; passing a sequence — including
  an empty one — is itself an explicit choice and is recorded as such.

`explicit` is consumption-side bookkeeping only. It is never part of the
`ProjectSpec` wire payload; only the *effective* `archetype`/`capabilities`/
`platforms` values reach `spec.build_spec_payload`, exactly as they did
before this hook existed.

## What may cross the boundary

Only two things may cross from a resolved policy into ProjectSpec
construction:

1. The **effective selection** — one archetype id, and sets of capability and
   platform ids — via `SelectionRequest`.
2. The **applied policy identifiers** — never the policy document itself —
   via `SelectionProvenance.policies`, landing in `ProjectSpec.provenance`
   unchanged. Protocol v1 states this plainly: provenance "neither embeds a
   policy document nor grants rendering authority."

`SelectionRequest` and `SelectionProvenance` are deliberately narrow: every
field is a string, a tuple of strings, or `None`. Neither type can carry a
file path, file content, a component option, or a callable. This is a
containment property, not an incidental fact about today's fields —
`tests/test_policy_hook.py` asserts both types' field sets and field type
shapes exactly, so a future field that could smuggle any of those things
fails a test immediately rather than silently widening what "policy" is
allowed to be.

## What `create-forge` does not own

Deliberately, as of this hook:

- **Parsing** an organisation-policy document. No JSON schema for protocol v1
  is implemented here.
- **Merging** multiple policies, or detecting conflicts between them. Protocol
  v1's merge and conflict rules (duplicate policy ids, a default that
  conflicts with a requirement, a required selection that is also forbidden,
  and so on) are `forge-template`'s stated future responsibility, not
  something this repository reimplements ahead of it.
- **Catalogue validation** of a selection against installed components. The
  engine already performs this: an unknown component id is rejected by
  `engine.validate()` as a structured `invalid-component-selection` error
  before any render is attempted, regardless of whether the selection came
  from a policy default or a direct `--archetype` flag.
- **Sourcing** a policy document at all. `create-forge` accepts no `--policy`
  flag and no `[policy]` config section; it reads no policy input of its own.

This is a considered decision, not an unfinished slice of CF-09.01. A
resolver living in `create-forge` would duplicate catalogue validation the
engine already performs — including the archetype-to-capability requirement
the `>=0.4,<0.5` line's catalogue now declares (ADR 0026) — and would compete
with the shared validation semantics `forge-template` states it intends to
own. Building one here is exactly what
[#53](https://github.com/Sandsy09/create-forge/issues/53)'s own final
acceptance criterion and
[#55](https://github.com/Sandsy09/create-forge/issues/55) forbid: "no
`forge-template` responsibility is duplicated in `create-forge`."

## The sanctioned source shape for a client that does read policy

A downstream client that chooses to accept policy input should keep the same
shape this repository already relies on for its own trust boundary
([ADR 0005](adr/0005-execute-template-tasks.md),
[ADR 0006](adr/0006-bundled-registry-over-remote.md)):

- An explicit, local policy document a user or operator supplies — a file
  path, not a URL fetched at runtime.
- Never remote-fetched and never implicitly discovered from an ambient
  location; the trust decision belongs to whoever runs the client, made
  explicit at invocation time.
- Resolved and validated **before** any ProjectSpec is constructed and before
  any side effect — matching protocol v1's own rule that "a violation fails
  before ProjectSpec construction, rendering, or filesystem work."

`create-forge` implements none of this itself; it is recorded here so a
downstream client has a documented shape to follow rather than inventing one
independently. [`examples/downstream_cli.py`](../examples/downstream_cli.py)
(CF-09.02, [ADR 0023](adr/0023-downstream-client-reference.md), the canonical
[downstream client reference](downstream-client-reference.md)) is a worked
example of this shape — an explicit, local `--policy PATH`, resolved before
any ProjectSpec is constructed. It is a second, independent client, not a
`create-forge` usage example: it imports no `create_forge` module at all.

## The fork path

[ADR 0008](adr/0008-fork-model-for-organisations.md) named forking this
repository as the supported path for organisation-specific behaviour. ADR
0022 supersedes it: forking remains appropriate for genuinely custom
executable template content — a scanner, an approval workflow, house
conventions with no equivalent in the reviewed public engine — but it is no
longer the preferred route for organisation defaults, required selections, or
forbidden selections. Those now belong to a downstream client of the public
`forge-template` engine, using the hook this document describes. See
[README.md](../README.md#using-this-at-work) for the user-facing statement of
both paths.

## Executable examples

- [`tests/test_policy_hook.py`](../tests/test_policy_hook.py) — the
  absent-vs-explicit-empty distinction on both `capabilities` and `platforms`,
  `archetype_explicit`'s override, provenance omission when empty and
  emission as bare identifiers when not, and the containment guard on both
  types' field sets and field type shapes.
- [`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py)'s
  `test_provenance_survives_parse_and_validate_canonicalised` — the real
  round trip: a payload carrying `provenance.policies` parses and validates
  against the real installed engine, coming back canonicalised in lexical
  order, proving this hook actually reaches `ProjectSpec.provenance` the way
  protocol v1 describes rather than merely asserting it should.
- [`tests/test_pipeline.py`](../tests/test_pipeline.py) and
  [`tests/test_archetype_parity.py`](../tests/test_archetype_parity.py) —
  `build_generation_request`'s `selection=` keyword exercised for both
  archetypes, unchanged in substance from before this hook existed.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
