# Downstream client reference

`downstream_cli.py` is a minimal, second, independent CLI over the public
[`forge_template`](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
facade. It answers [CF-09.02 / #54](https://github.com/Sandsy09/create-forge/issues/54):
*"a minimal example showing how another CLI consumes `forge-template` without
depending on `create-forge` internals."*

It imports nothing from `create_forge` and no `forge_template.*` submodule —
only the top-level `forge_template` package, `packaging` (already one of its
own requirements), and the standard library. See
[docs/downstream-client-reference.md](../docs/downstream-client-reference.md)
for the full contract this file characterizes, and
[`tests/test_downstream_reference.py`](../tests/test_downstream_reference.py)
for the tests that hold its boundary and behaviour.

This is **not** a `create-forge` capability. It ships from `examples/`, is
excluded from the wheel and the sdist, and no module under `src/` imports it.

## What it demonstrates

- Compatibility negotiation before any other call
  ([compatibility-policy.md](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md)),
  with its own declared range — not `create-forge`'s.
- A minimal, worked resolver for
  [organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)'s
  authority order: `profile default < policy default < explicit choice <
  required/forbidden constraint`, including the "an explicitly empty list is
  still an explicit choice" rule.
- Structured, categorised failures — for an unsupported engine, an invalid or
  conflicting policy set, and a selection that violates one — all reported
  before any component discovery, planning, rendering, or destination write.
- Real `ProjectSpec` construction, validation, planning, and rendering
  through the public facade only, ending in a plain (non-atomic) write when
  `--output` is given.

Deliberately **not** exhaustive: this resolver implements enough of protocol
v1 to demonstrate it working end to end, not its full 17-detail-code surface.
That belongs to forge-template's own
[`tests/organisation_policy_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/organisation_policy_contract.py)
([organisation-policy-fixtures.md](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md)).
And it writes a rendered project directly, with no staging directory or
atomic rename — `create-forge`'s own
[`staging.py`](../src/create_forge/staging.py) ([ADR 0015](../docs/adr/0015-staged-filesystem-generation.md))
is a more careful implementation of that one step, referenced here rather
than reimplemented.

## Running it

Dry run — negotiates, resolves policy, and prints the plan; writes nothing:

```bash
uv run python examples/downstream_cli.py --name "Example Service" \
    --policy examples/policies/example-baseline.json
```

With a real write:

```bash
uv run python examples/downstream_cli.py --name "Example Service" \
    --policy examples/policies/example-baseline.json \
    --output ./example-service
```

An explicit choice overriding a policy default, and choosing zero platforms
explicitly (distinct from never asking):

```bash
uv run python examples/downstream_cli.py --name "Example CLI Tool" \
    --archetype cli --policy examples/policies/example-restricted.json \
    --no-platforms
```

The two shipped policies also demonstrate the documented irreconcilable
pair — applied together, in either order, they fail identically with
`organisation-policy-conflict` / `default-requirement-conflict`:

```bash
uv run python examples/downstream_cli.py --name "Example Service" \
    --policy examples/policies/example-baseline.json \
    --policy examples/policies/example-restricted.json
```

Run `uv run python examples/downstream_cli.py --help` for the full flag list.

## The policy fixtures

Both `examples/policies/*.json` documents are `example-`-prefixed and
reference only identifiers the real installed catalogue has (`library`,
`cli`) — `tests/test_downstream_reference.py` asserts both properties, so
neutrality is a checked fact rather than a promise.
