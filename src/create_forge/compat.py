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

from packaging.specifiers import SpecifierSet
from packaging.version import Version

ENGINE_DISTRIBUTION = "forge-template"
"""The PyPI distribution name the engine dependency declares."""

INTEGRATION_LINE = "v0.4.x-engine"
"""The create-forge release line and its default generation architecture.

This is explicit rather than derived from installed metadata so a new release
line requires a deliberate compatibility review. ADR 0040 (CF-18.01) makes the
engine the default `new` architecture; `new` is Copier-backed only under the
explicit `--legacy` flag. ADR 0049 (CF-18.07) moved this from `v0.3.x-engine`
to `v0.4.x-engine` for the published cutover release -- a shipped diagnostic
surface (`doctor --json`'s `integration.line`) reviewed by hand, not derived.
`tests/test_engine_contract.py`'s
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

_SUPPORTED_ENGINE_SPECIFIER = SpecifierSet(SUPPORTED_ENGINE_RANGE)


class EngineCompatibilityError(Exception):
    """An engine is outside the supported package/protocol range.

    Carries exit status `3`'s meaning (docs/cli-conventions.md), reserved by
    ADR 0011 for exactly this failure class and widened by ADR 0040 decision
    12 to cover an out-of-range component-manifest protocol or
    `metadata_version` too. Reachable from the default `new` path since ADR
    0040 (CF-18.01) made the engine the default architecture, and from the
    `--engine-source` override path since ADR 0044 (CF-18.02) -- the same
    class either way, raised against plain version/protocol values rather
    than an `EngineInfo` instance, so both `engine.py` (the installed engine,
    in process) and `engine_source.py` (a provisioned engine, out of process)
    share one compatibility check instead of two that could drift apart.
    """


def require_supported_package(package_version: str) -> None:
    """Reject an engine package outside the declared, released range."""
    if Version(package_version) in _SUPPORTED_ENGINE_SPECIFIER:
        return

    msg = (
        f"Detected forge-template {package_version}, but this "
        f"create-forge release supports {ENGINE_DISTRIBUTION}"
        f"{SUPPORTED_ENGINE_RANGE}. Run "
        f"`pip install '{ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}'` "
        "(or the equivalent `uv add`/`uv sync` invocation) to install a "
        "compatible version."
    )
    raise EngineCompatibilityError(msg)


def require_protocol_overlap(
    *,
    package_version: str,
    protocol_name: str,
    supported: tuple[int, ...],
    detected: tuple[int, ...],
) -> None:
    """Reject an engine with no protocol version in common with this CLI."""
    supported_set = set(supported)
    detected_set = set(detected)
    if supported_set & detected_set:
        return

    msg = (
        f"forge-template {package_version} supports {protocol_name} "
        f"protocol(s) {sorted(detected_set)}, but this create-forge release "
        f"supports {sorted(supported_set)}."
    )
    raise EngineCompatibilityError(msg)


def require_projectspec_protocol(
    package_version: str, detected: tuple[int, ...]
) -> None:
    """Require a shared ProjectSpec protocol for every engine operation."""
    require_protocol_overlap(
        package_version=package_version,
        protocol_name="ProjectSpec",
        supported=SUPPORTED_PROJECTSPEC_PROTOCOLS,
        detected=detected,
    )


def require_component_manifest_protocol(
    package_version: str, detected: tuple[int, ...]
) -> None:
    """Require a shared component-manifest protocol before discovery."""
    require_protocol_overlap(
        package_version=package_version,
        protocol_name="component manifest",
        supported=SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS,
        detected=detected,
    )


def require_metadata_version(package_version: str, detected: int) -> None:
    """Require a supported generation-metadata schema version.

    ADR 0040 decision 11/12 widens exit `3` to cover an out-of-range
    `metadata_version`, the ninth versioned compatibility axis (ADR 0059,
    published by the `0.5.0` engine cutover) -- checked the same way as the
    two protocol tuples, via set overlap against a single-element "detected"
    tuple so `require_protocol_overlap`'s message shape is reused as-is.
    """
    require_protocol_overlap(
        package_version=package_version,
        protocol_name="generation-metadata",
        supported=SUPPORTED_GENERATION_METADATA_VERSIONS,
        detected=(detected,),
    )
