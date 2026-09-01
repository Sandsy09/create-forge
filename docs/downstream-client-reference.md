# Downstream Client Reference

This is the living contributor contract for
[`examples/downstream_cli.py`](../examples/downstream_cli.py) — a second,
independent Blueprint-style CLI over the public `forge_template` facade,
delivered for CF-09.02 / [#54](https://github.com/Sandsy09/create-forge/issues/54).
[ADR 0023](adr/0023-downstream-client-reference.md) records the decision this
document keeps current. CF-09.03's final
[reference-client boundary decision](adr/0024-reference-client-not-framework-dependency.md)
uses this example as executable proof that `create-forge` is one client, not
a framework dependency for every client.

## Status

The reference ships from `examples/`, is excluded from the wheel and the
sdist, and is imported by no module under `src/`. It is not a `create-forge`
capability — it exists to prove and demonstrate that a second client needs
none of this repository to reuse `forge-template`.

## What it demonstrates, and in what order

Every run of `examples/downstream_cli.py` proceeds through the same strict
order, matching
[compatibility-policy.md](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md#reporting-an-unsupported-forge-version)'s
"fail closed... before any component discovery, planning, rendering, or
destination write" rule:

1. **Negotiate** its own declared compatibility range
   (`SUPPORTED_ENGINE_RANGE`, `SUPPORTED_PROJECTSPEC_PROTOCOLS`) against
   `get_engine_info()` — declared independently of `create_forge.compat`,
   proving a second client sets its own bounds against the same published
   surface.
2. **Discover** the installed catalogue via `discover_components()`.
3. **Resolve organisation policy** — see below.
4. **Construct** a ProjectSpec payload and **parse**, **validate**, and
   **plan** it through the public facade.
5. **Render and write**, only when `--output` was given.

A failure at any step before 5 leaves the filesystem untouched; a failure at
step 5 (a non-empty destination) leaves it exactly as it was found.

## The policy resolver

`examples/downstream_cli.py` implements
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)'s
authority order:

```text
profile default
  < merged organisation-policy default
    < explicit user choice          (an explicitly empty list included)
      < required or forbidden constraint   (validates; never mutates)
```

`apply_authority_order()` is the pure step: no validation, no catalogue
lookup, so it is directly testable independent of what the installed
catalogue happens to contain — the real production catalogue has zero
capability or platform components, so a test exercising the authority order
over capabilities cannot go through the catalogue-validated `resolve()`
without every non-empty capability being rejected first.
`_validate_against_policy()` and `_validate_against_catalogue()` are the two
steps after it: required/forbidden rules validate the resolved selection
without ever silently adding, removing, or replacing an explicit choice, and
the catalogue check confirms every referenced id exists and has the expected
kind — the one catalogue lookup that genuinely belongs client-side, since the
engine itself never sees policy *rules*, only the already-resolved selection.

`PolicyError` is the resolver's own structured-failure type, carrying one of
protocol v1's three categories (`invalid-organisation-policy`,
`organisation-policy-conflict`, `organisation-policy-violation`) and sorted
`(code, path, message)` details — never `forge_template.ForgeEngineError`,
whose surface stays engine-owned.

## What it deliberately does not implement

- **The full 17-detail-code taxonomy.** This resolver implements enough of
  protocol v1's merge and validation rules to demonstrate the authority order
  working end to end, not an exhaustive reference implementation.
  `forge-template`'s own
  [`tests/organisation_policy_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/organisation_policy_contract.py)
  ([organisation-policy-fixtures.md](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md))
  owns that proof. Duplicating it here would be exactly what CF-09.02's own
  final acceptance criterion — "no `forge-template` responsibility is
  duplicated in `create-forge`" — forbids.
- **Staged, atomic finalisation.** `write_rendered_project()` writes plainly
  into `--output`, refusing a non-empty destination first. `create-forge`'s
  own [`staging.py`](../src/create_forge/staging.py)
  ([ADR 0015](adr/0015-staged-filesystem-generation.md)) is a more careful
  implementation of that one step; this reference points at it rather than
  reimplementing it.
- **Any `create-forge` import.** Not `create_forge.engine`, not
  `create_forge.pipeline`, not `create_forge.spec` — see "The boundary" below.

## The boundary

`examples/downstream_cli.py` imports only `argparse`/`json`/`re`/`sys` from
the standard library, `dataclasses`/`pathlib`/`typing` likewise, the
top-level `forge_template` package, and `packaging` (already one of
`forge-template`'s own requirements). No `create_forge` module, and no
`forge_template.*` submodule.

This is a containment property, not an incidental fact about today's
imports — `tests/test_downstream_reference.py` parses the file's AST and
asserts both facts directly, mirroring the equivalent guards
`tests/test_engine_contract.py` already runs against
[`src/create_forge/engine.py`](../src/create_forge/engine.py). A future
edit that adds either import fails a test immediately.

## Executable examples

- [`tests/test_downstream_reference.py`](../tests/test_downstream_reference.py) —
  negotiation acceptance and rejection (both axes, with all four required
  facts in the message); `main()` exiting `3` with nothing written on a
  failed negotiation; the authority order, including the
  explicit-empty-vs-omitted distinction on both the resolver and the CLI's
  own argument parsing; an explicitly forbidden selection and the shipped
  policy pair's documented conflict under both input orders; malformed and
  empty policy documents; a real write producing a project with no
  `forge-template` or `create-forge` reference anywhere in it; a non-empty
  destination refused with nothing else written; the AST boundary guard; and
  fixture neutrality (every shipped policy is `example-`-prefixed and
  references only real catalogue components).
- [`examples/policies/`](../examples/policies/) — the two neutral policy
  documents the tests and the manual walkthrough both use, including the
  documented irreconcilable pair.
- [`examples/README.md`](../examples/README.md) — how to run the reference by
  hand, both as a dry run and with a real write.

When a change alters what this reference demonstrates or how it is bounded,
update this document, `examples/README.md`, and the characterization tests in
the same pull request.
