"""Engine compatibility constants shared by shipped and engine-only modules.

Deliberately engine-free: nothing here imports `forge_template`, not even
under `TYPE_CHECKING`. That lets `cli.py`'s `doctor` command report the
declared range and supported protocols with no negotiation round-trip.
Since ADR 0040 (CF-18.01) made the engine the default `new` path, `engine.py`
is no longer the module ADR 0014's shipped-entry-point guard protects --
`forge-template` is a required dependency now, reachable from `cli.py` at
module scope. The guard's *shape* moved rather than disappeared: `runner.py`
(and `sources.py`'s `--template-url` validation) is the module the `--legacy`
route now imports lazily, since `copier` is the optional dependency after the
cutover. `tests/test_engine_contract.py`'s `_SHIPPED_MODULES` AST guard still
covers this module, mirroring the role `staging.py` plays for the same
reason (ADR 0015). See
[ADR 0018](../../docs/adr/0018-pypi-distribution-and-the-first-engine-range.md),
[ADR 0026](../../docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md),
[ADR 0031](../../docs/adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md),
[ADR 0040](../../docs/adr/0040-engine-default-selection-and-source-resolution.md),
and the canonical [engine resolution contract](../../docs/engine-resolution.md).
"""

from __future__ import annotations

ENGINE_DISTRIBUTION = "forge-template"
"""The PyPI distribution name the engine dependency declares."""

INTEGRATION_LINE = "v0.3.x-engine"
"""The create-forge release line and its default generation architecture.

This is explicit rather than derived from installed metadata so a new release
line requires a deliberate compatibility review. ADR 0040 (CF-18.01) makes the
engine the default `new` architecture; `new` is Copier-backed only under the
explicit `--legacy` flag. `tests/test_engine_contract.py`'s
`test_diagnostic_integration_line_matches_package_release_line` checks this
literal against `pyproject.toml`'s own `major.minor`.
"""

SUPPORTED_ENGINE_RANGE = ">=0.5,<0.6"
"""The supported `forge-template` compatibility range.

Pre-1.0, a supported range stays within one minor line -- see the
[integration contract](../../docs/integration-contract.md)'s
version-and-protocol-compatibility rule, so each minor bump is a deliberate,
human-authored line crossing (ADR 0012), never a Dependabot proposal. ADR
0018 assigned the first range, `>=0.3.1,<0.4`; ADR 0026 moved it to the
`forge-template` 0.4 line; ADR 0031 raised the lower bound to the reviewed
`0.4.1` release. ADR 0040/0042 (CF-18.01) adopt the reviewed `0.5.0`
engine-default cutover release, the first to publish `metadata_version` and
component-manifest protocol `3`. `engine.py` checks an installed package
against this range with `packaging.specifiers.SpecifierSet`.
"""

SUPPORTED_PROJECTSPEC_PROTOCOLS: tuple[int, ...] = (1,)
"""ProjectSpec wire protocols this create-forge release has implemented
against. Unchanged across the `0.3.x` through `0.5.x` engine lines
(ADR 0026, ADR 0042).

Deliberately not read from the installed engine's own advertised protocols
-- negotiation in `engine.py` compares the two sides rather than assuming
they agree.
"""

SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS: tuple[int, ...] = (1, 2, 3)
"""Component-manifest protocols this create-forge release understands.

Widened to include protocol `3` (owner-declared `[[renames]]` /
`[[regeneration]]` records) at the `0.5.0` engine cutover (ADR 0042 /
FT-17.01); protocols `1` and `2` are unchanged (ADR 0026).

Independent from the installed engine's advertised protocols for the same
reason as :data:`SUPPORTED_PROJECTSPEC_PROTOCOLS`.
"""

SUPPORTED_GENERATION_METADATA_VERSIONS: tuple[int, ...] = (1,)
"""Generation-metadata schema versions this create-forge release understands.

The ninth versioned compatibility axis (ADR 0059 / FT-17.01), first published
by the `0.5.0` engine cutover -- negotiated exactly like the protocol tuples
above, via `EngineInfo.metadata_version`. See docs/generation-provenance.md
in `forge-template` and docs/engine-project-lifecycle.md here.
"""
