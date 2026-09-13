"""The single module that touches the `forge_template` engine.

Mirrors `runner.py`'s role for Copier's Python API (invariant 4): the engine
is imported in exactly one place, so it evolves without every module needing
attention. Since ADR 0040 (CF-18.01) made the engine the default `new` path,
`forge-template` is a required dependency
([ADR 0018](../../docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)
first published it to PyPI as a range-bounded package; ADR 0040 moved it out
of the optional `engine` extra) -- a plain `pip install create-forge` /
`uvx create-forge` resolves it, so this module is reachable from `cli.py`'s
default `new` path, not only a hidden development flag. `compat.py` holds the
range and protocol constants this module checks against -- it is engine-free,
so `cli.py`'s `doctor` command can report them without a negotiation
round-trip through this module.

`spec.py` builds the wire payload this module parses and validates, while this
module also exposes the discovery adapter `pipeline.py` uses -- see ADR 0013,
docs/project-spec-construction.md, and docs/component-discovery.md for the
full contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_template import (
    ComponentDescriptor,
    EngineInfo,
    ProjectSpec,
    RenderedProject,
    get_engine_info,
)

# Explicit self-reexport: mypy strict's no_implicit_reexport otherwise blocks
# `cli.py`'s `except engine.ForgeEngineError` (a direct import of this
# module, not merely an attribute chain) from typing against a name this
# module only imported rather than defined.
from forge_template import ForgeEngineError as ForgeEngineError  # noqa: PLC0414
from forge_template import discover_components as _discover_components
from forge_template import parse_project_spec as _parse_project_spec
from forge_template import render_project as _render_project
from forge_template import validate_project_spec as _validate_project_spec

from create_forge import compat

# Explicit self-reexport, same reason as `ForgeEngineError` above: `cli.py`
# and `engine_source.py` both type against `engine.EngineCompatibilityError`
# / `compat.EngineCompatibilityError` -- the same class either way (ADR
# 0044) -- and mypy strict's no_implicit_reexport otherwise blocks that
# direct-module attribute access.
from create_forge.compat import (
    EngineCompatibilityError as EngineCompatibilityError,  # noqa: PLC0414
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def _require_supported_package(info: EngineInfo) -> None:
    """Reject an engine package outside the declared, released range.

    Delegates to `compat.py`'s plain-value check (ADR 0044) so the installed
    engine (here) and a provisioned `--engine-source` engine
    (`engine_source.py`) share one compatibility rule instead of two that
    could drift apart. This wrapper -- and the three below it -- exist only
    to unpack the `EngineInfo` this module's callers already hold.
    """
    compat.require_supported_package(info.package_version)


def _require_projectspec_protocol(info: EngineInfo) -> None:
    """Require a shared ProjectSpec protocol for every engine operation."""
    compat.require_projectspec_protocol(
        info.package_version, info.projectspec_protocols
    )


def _require_component_manifest_protocol(info: EngineInfo) -> None:
    """Require a shared component-manifest protocol before discovery."""
    compat.require_component_manifest_protocol(
        info.package_version, info.component_manifest_protocols
    )


def _require_metadata_version(info: EngineInfo) -> None:
    """Require a supported generation-metadata schema version.

    ADR 0040 decision 11/12 widens exit `3` to cover an out-of-range
    `metadata_version`, the ninth versioned compatibility axis (ADR 0059,
    published by the `0.5.0` engine cutover) -- checked the same way as the
    two protocol tuples, via `compat.require_metadata_version`.
    """
    compat.require_metadata_version(info.package_version, info.metadata_version)


def negotiate_protocol() -> None:
    """Confirm the engine matches the supported package/ProjectSpec range.

    Runs before any payload is parsed, validated, or rendered.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)


def discover() -> tuple[ComponentDescriptor, ...]:
    """Return engine-owned component descriptors after protocol negotiation.

    ProjectSpec, component-manifest, and generation-metadata compatibility
    are checked before the engine scans its installed catalogue. The
    descriptors are returned unchanged: their identifiers, presentation
    metadata, compatibility, relationships, and options remain owned and
    validated by `forge-template`.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    _require_metadata_version(info)
    return _discover_components()


def build_project_spec(payload: Mapping[str, object]) -> ProjectSpec:
    """Negotiate the protocol, then strictly parse a ProjectSpec payload.

    Negotiation runs before `parse_project_spec` ever inspects `payload`,
    satisfying #46's "negotiate the supported ProjectSpec protocol before any
    side effect" criterion independent of what the payload itself contains.
    """
    negotiate_protocol()
    return _parse_project_spec(payload)


def validate(spec: ProjectSpec) -> ProjectSpec:
    """Validate a parsed ProjectSpec against the installed component catalogue.

    The installed `forge-template` catalogue is production: `library`, `cli`,
    and `data-science` are all real, validated archetypes.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    _require_metadata_version(info)
    return _validate_project_spec(spec)


def render(spec: ProjectSpec) -> RenderedProject:
    """Render one spec to immutable in-memory files after compatibility checks.

    The public engine owns validation, composition, rendering, and
    generated-project validation -- the `RenderedProject` returned here has
    already passed `forge_template.validate_rendered_project`. This adapter
    deliberately accepts no destination path and performs no filesystem
    writes; `pipeline.finalise_generation_request` (ADR 0015) owns staging and
    finalisation around the returned files.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    _require_metadata_version(info)
    return _render_project(spec)


def get_info() -> EngineInfo:
    """Return the installed engine's version/protocol facts, unchecked.

    Unlike every operation above, this performs no compatibility check --
    `doctor` uses it to report what is installed and detected even when it
    falls outside the supported range, surfacing the mismatch as one failed
    diagnostic row instead of raising `EngineCompatibilityError`
    (ADR 0040 decision 6).
    """
    return get_engine_info()


def explain(exc: ForgeEngineError) -> str:
    """Translate a structured `ForgeEngineError` into terminal-ready text.

    Mirrors `runner._explain()`'s job for Copier's freeform messages, but
    from a structured source: `ForgeEngineError` already carries a stable
    code and located details, so this formats them rather than pattern
    matching on message text.
    """
    lines = [f"{exc.message} ({exc.code.value})"]
    for detail in exc.details:
        location = ".".join(str(part) for part in detail.path) or exc.operation
        lines.append(f"  {location}: {detail.message}")
    return "\n".join(lines)
