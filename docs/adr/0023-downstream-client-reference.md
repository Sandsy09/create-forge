# 23. Downstream client reference

## Status

Accepted

## Context

[Issue #54 / CF-09.02](https://github.com/Sandsy09/create-forge/issues/54) is
the second child of [CF-EPIC-09](https://github.com/Sandsy09/create-forge/issues/40),
unblocked when [#53 / CF-09.01](https://github.com/Sandsy09/create-forge/issues/53)
landed ([ADR 0022](0022-downstream-organisation-policy-hook.md)). It asks for
*"a minimal example showing how another CLI consumes `forge-template`
**without depending on create-forge internals**."*

That last clause decides the shape of this record. ADR 0022's own
Consequences section anticipated #54 demonstrating create-forge's
`SelectionRequest`/`SelectionProvenance`/`build_generation_request` seam
directly — but #54's own acceptance criteria explicitly forbid depending on
`create-forge` internals or generated-project runtime hooks. The reference
this record adopts is therefore **not** a create-forge usage example. It is a
second, independent Blueprint-style client that talks to the public
`forge_template` facade on its own, which is exactly the evidence
[#55 / CF-09.03](https://github.com/Sandsy09/create-forge/issues/55) needs for
its own claim that *"create-forge is a reference client, not a framework
dependency."*

Every cross-repository prerequisite is complete: FT-09.02's
[extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
FT-09.03's
[policy reference fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
FT-09.04's
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and FT-09.05's
[no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md).
The last of these assigns the client side of the boundary explicitly:

> A downstream client still owns policy-source discovery, authenticity, and
> trust; tracking whether each selection was explicitly supplied; policy
> parsing and resolution until a public resolver is accepted; construction of
> the effective ProjectSpec and its provenance; compatibility negotiation and
> user-facing unsupported-version reporting; destination selection, staging,
> atomic replacement, and cleanup.

A reference client is expected to carry its own resolver. This does not
revisit ADR 0022: that record governs what the *shipped `create-forge`
package* does, and this change adds no `src/create_forge` code at all.

Before deciding anything, the full public-API path was verified against the
real installed `forge-template 0.3.1`:

| Question | Answer |
| --- | --- |
| Does the full client path work through public API only? | Yes — `get_engine_info` → `discover_components` → `parse_project_spec` → `validate_project_spec` → `plan_generation` → `render_project` runs clean, producing a real 13-file project. |
| Does `provenance` survive and canonicalise? | Yes — applied policy IDs come back sorted lexically, unchanged in content. |
| Is a bad selection structurally reported? | Yes — an unknown component id is rejected as `invalid-component-selection` before any render. |
| What does the real catalogue contain? | `library` and `cli`, both archetypes. Zero capabilities, zero platforms. |
| Can the example avoid new dependencies? | Yes — `packaging` is already a direct `forge-template` requirement, so an `argparse` + `forge_template` + `packaging` client installs nothing extra. |

## Decision

**The reference lives in `examples/downstream_cli.py`, as runnable code, not
prose.** A single file using only `argparse`, the standard library, the
top-level `forge_template` facade, and `packaging`. It is excluded from the
wheel and the sdist and no module under `src/` imports it — repository-only,
like `docs/` and `scripts/`. `pyproject.toml` adds `examples` to ruff's `src`,
mypy's `files`, and pytest's `pythonpath`, mirroring the existing `scripts`
entry that already lets `tests/test_adr.py` do `import adr`.

**It carries its own compatibility bounds, declared independently of
`create_forge.compat`.** A second client negotiating its own supported range
against the same published engine surface is the point being demonstrated,
even though the range happens to match `create-forge`'s own today.

**It carries a minimal, worked organisation-policy resolver, not an exhaustive
one.** It implements protocol v1's authority order (`profile default <
merged policy default < explicit user choice < required/forbidden
constraint`, including "an explicitly empty list is still an explicit
choice") and enough of the merge/conflict rules to demonstrate them working
end to end against two neutral, `example-`-prefixed policy documents.
Deliberately not the full 17-detail-code surface: that exhaustive proof
belongs to `forge-template`'s own
[`tests/organisation_policy_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/organisation_policy_contract.py),
and reimplementing it here would be exactly what #54's own final acceptance
criterion ("no `forge-template` responsibility is duplicated in
`create-forge`") forbids.

**It writes only on an explicit `--output`, and refuses a non-empty
destination.** Without `--output` it negotiates, resolves policy, and prints
the plan — writing nothing. The write itself is plain, not staged or atomic:
`create-forge`'s own `staging.py` ([ADR 0015](0015-staged-filesystem-generation.md))
is a more careful implementation of that one step, referenced from the
example's documentation rather than reimplemented in it.

**Its own structured error type, not `forge_template.ForgeEngineError`.**
Policy resolution is entirely client-side, so a `PolicyError` carrying one of
protocol v1's three failure categories keeps the engine's own structured-error
surface unchanged, matching how `organisation-policy-fixtures.md` describes
its own test-only reference resolver.

**A boundary guard, not just a docstring claim.**
`tests/test_downstream_reference.py` parses `examples/downstream_cli.py`'s AST
and asserts it imports no `create_forge` module and no `forge_template.*`
submodule, mirroring the equivalent guards `tests/test_engine_contract.py`
already runs against `src/create_forge/engine.py`. This is the executable
form of #54's fifth acceptance criterion, standing protection against the
reference quietly acquiring a `create-forge` import later.

## Consequences

- [#55 / CF-09.03](https://github.com/Sandsy09/create-forge/issues/55) gains
  concrete, tested evidence that a second client can reuse `forge-template`
  without any `create-forge` dependency — the AST guard and the real,
  no-Forge-reference generated project are both directly citable.
- [ADR 0022](0022-downstream-organisation-policy-hook.md) is unaffected: no
  `src/create_forge` module changes, and its own hook remains the seam a
  policy-aware client of *this* repository's pipeline uses, distinct from
  the reference client this record adds.
- `docs/downstream-client-reference.md` is the living contract this record
  establishes; unlike this ADR, it is expected to change as the example
  itself evolves.
- `docs/organisation-policy-consumption.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
  and `README.md` are updated to point at the delivered example rather than
  forward-reference #54.
- No `forge-template` change resulted from this work; nothing here hands a
  responsibility back to the engine.
