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
[ADR 0018](../../docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)
and the canonical [engine resolution contract](../../docs/engine-resolution.md).
"""

from __future__ import annotations

ENGINE_DISTRIBUTION = "forge-template"
"""The PyPI distribution name `create-forge[engine]` declares."""

SUPPORTED_ENGINE_RANGE = ">=0.3.1,<0.4"
"""The first assigned, released compatibility range (ADR 0018).

Pre-1.0, a supported range stays within one minor line -- see the
[integration contract](../../docs/integration-contract.md)'s
version-and-protocol-compatibility rule. `0.3.1` is the first PyPI release of
`forge-template` (forge-template ADR 0036); `engine.py` checks an installed
package against this range with `packaging.specifiers.SpecifierSet`,
replacing the prior exact-pin development check.
"""

SUPPORTED_PROJECTSPEC_PROTOCOLS: tuple[int, ...] = (1,)
"""ProjectSpec wire protocols this create-forge release has implemented
against.

Deliberately not read from the installed engine's own advertised protocols
-- negotiation in `engine.py` compares the two sides rather than assuming
they agree.
"""

SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS: tuple[int, ...] = (1, 2)
"""Component-manifest protocols this create-forge release understands.

Independent from the installed engine's advertised protocols for the same
reason as :data:`SUPPORTED_PROJECTSPEC_PROTOCOLS`.
"""
