"""Engine compatibility constants shared by shipped and engine-only modules.

Deliberately engine-free: nothing here imports `forge_template`, not even
under `TYPE_CHECKING`. That is what lets `cli.py`'s `doctor` command report
the declared engine range and supported protocols unconditionally --
independent of whether the `engine` extra is installed, and without
importing `engine.py` itself, which would break ADR 0014's rule that no
module reachable from `create-forge`'s shipped entry point may depend on
`forge_template` at its own import time.
`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` AST guard covers this
module for exactly that reason -- mirroring the role `staging.py` already
plays for the same rule (ADR 0015). See
[ADR 0018](../../docs/adr/0018-pypi-distribution-and-the-first-engine-range.md),
[ADR 0026](../../docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md),
and the canonical [engine resolution contract](../../docs/engine-resolution.md).
"""

from __future__ import annotations

ENGINE_DISTRIBUTION = "forge-template"
"""The PyPI distribution name `create-forge[engine]` declares."""

SUPPORTED_ENGINE_RANGE = ">=0.4,<0.5"
"""The supported `forge-template` compatibility range.

Pre-1.0, a supported range stays within one minor line -- see the
[integration contract](../../docs/integration-contract.md)'s
version-and-protocol-compatibility rule, so each minor bump is a deliberate,
human-authored line crossing (ADR 0012), never a Dependabot proposal. ADR
0018 assigned the first range, `>=0.3.1,<0.4`; ADR 0026 moves it here, to the
`forge-template` 0.4 line whose lower bound `0.4.0` is the first release
carrying the Data Science archetype and reusable capabilities. `engine.py`
checks an installed package against this range with
`packaging.specifiers.SpecifierSet`.

`0.4.0` preserved both protocol tuples below unchanged -- the public facade
diff from `0.3.2` is empty -- which is what makes this a range move rather
than a protocol migration.
"""

SUPPORTED_PROJECTSPEC_PROTOCOLS: tuple[int, ...] = (1,)
"""ProjectSpec wire protocols this create-forge release has implemented
against. Unchanged across the `0.3.x` and `0.4.x` engine lines (ADR 0026).

Deliberately not read from the installed engine's own advertised protocols
-- negotiation in `engine.py` compares the two sides rather than assuming
they agree.
"""

SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS: tuple[int, ...] = (1, 2)
"""Component-manifest protocols this create-forge release understands.
Unchanged across the `0.3.x` and `0.4.x` engine lines (ADR 0026).

Independent from the installed engine's advertised protocols for the same
reason as :data:`SUPPORTED_PROJECTSPEC_PROTOCOLS`.
"""
