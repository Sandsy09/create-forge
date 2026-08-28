"""The single module that touches the `forge_template` engine.

Mirrors `runner.py`'s role for Copier's Python API (invariant 4): the engine
is imported in exactly one place, so it evolves without every module needing
attention. Importing this module requires the `engine` dependency group
(`uv sync --all-groups`) -- it is a `[tool.uv.sources]`-pinned development
dependency, not yet a runtime one, since `forge-template` 0.2.0 is unreleased
and no engine range is assigned (docs/engine-resolution.md). No module
reachable from create-forge's shipped CLI entry point may import this module;
`tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
enforces that.

`spec.py` builds the wire payload this module parses and validates, while this
module also exposes the discovery adapter used by the future CLI pipeline --
see ADR 0013, docs/project-spec-construction.md, and
docs/component-discovery.md for the full contracts.
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
# `cli.py`'s lazy `except engine.ForgeEngineError` (a direct import of this
# module, not merely an attribute chain) from typing against a name this
# module only imported rather than defined.
from forge_template import ForgeEngineError as ForgeEngineError  # noqa: PLC0414
from forge_template import discover_components as _discover_components
from forge_template import parse_project_spec as _parse_project_spec
from forge_template import render_project as _render_project
from forge_template import validate_project_spec as _validate_project_spec

if TYPE_CHECKING:
    from collections.abc import Mapping

TESTED_ENGINE_PACKAGE_VERSION = "0.2.0"
"""Exact forge-template package version in the Stage 06 development contract.

This is deliberately not a released compatibility range. The engine remains a
development-only dependency pinned to an immutable commit until #9 chooses an
installable distribution channel and CF-07.01 performs the atomic cutover.
"""

SUPPORTED_PROJECTSPEC_PROTOCOLS: tuple[int, ...] = (1,)
"""ProjectSpec wire protocols this create-forge release has implemented
against.

Deliberately not read from `forge_template.SUPPORTED_PROJECTSPEC_PROTOCOLS`
-- that constant is what the *installed engine* accepts, and this one is
what *create-forge* supports; negotiation compares the two rather than
assuming they agree. No released engine package range is assigned yet:
`negotiate_protocol` requires the exact development package above, then checks
the ProjectSpec wire protocol independently.
"""

SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS: tuple[int, ...] = (1,)
"""Component-manifest protocols this create-forge release understands.

Kept independent from the installed engine's advertised protocols for the
same reason as :data:`SUPPORTED_PROJECTSPEC_PROTOCOLS`: discovery must compare
the two sides rather than assume that installing an engine makes every data
protocol compatible.
"""


class EngineCompatibilityError(Exception):
    """An installed engine is outside the tested package/protocol contract.

    Carries exit status `3`'s meaning (docs/cli-conventions.md), reserved by
    ADR 0011 for exactly this failure class. Implemented here at the engine
    boundary but not yet raised from any shipped command -- no command calls
    `negotiate_protocol` or `discover` until CF-07.01 wires the engine into
    `new`.
    """


def _require_tested_package(info: EngineInfo) -> None:
    """Reject an engine package outside the exact Stage 06 development pair."""
    if info.package_version == TESTED_ENGINE_PACKAGE_VERSION:
        return

    msg = (
        f"Detected forge-template {info.package_version}, but this create-forge "
        f"development contract is tested only with forge-template "
        f"{TESTED_ENGINE_PACKAGE_VERSION}. No released engine range is assigned; "
        "install the pinned development dependency or validate and adopt the new "
        "pair through the cross-repository contract workflow."
    )
    raise EngineCompatibilityError(msg)


def _require_protocol_overlap(
    info: EngineInfo,
    *,
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
        f"forge-template {info.package_version} supports {protocol_name} "
        f"protocol(s) {sorted(detected_set)}, but this create-forge release "
        f"supports {sorted(supported_set)}."
    )
    raise EngineCompatibilityError(msg)


def _require_projectspec_protocol(info: EngineInfo) -> None:
    """Require a shared ProjectSpec protocol for every engine operation."""
    _require_protocol_overlap(
        info,
        protocol_name="ProjectSpec",
        supported=SUPPORTED_PROJECTSPEC_PROTOCOLS,
        detected=info.projectspec_protocols,
    )


def _require_component_manifest_protocol(info: EngineInfo) -> None:
    """Require a shared component-manifest protocol before discovery."""
    _require_protocol_overlap(
        info,
        protocol_name="component manifest",
        supported=SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS,
        detected=info.component_manifest_protocols,
    )


def negotiate_protocol() -> None:
    """Confirm the engine matches the tested package/ProjectSpec pair.

    Runs before any payload is parsed, validated, or rendered.
    """
    info = get_engine_info()
    _require_tested_package(info)
    _require_projectspec_protocol(info)


def discover() -> tuple[ComponentDescriptor, ...]:
    """Return engine-owned component descriptors after protocol negotiation.

    ProjectSpec and component-manifest compatibility are checked before the
    engine scans its installed catalogue. The descriptors are returned
    unchanged: their identifiers, presentation metadata, compatibility,
    relationships, and options remain owned and validated by `forge-template`.
    """
    info = get_engine_info()
    _require_tested_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
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

    Expected to fail with `EngineErrorCode.INVALID_COMPONENT_SELECTION` today:
    the installed `forge-template` 0.2.0 catalogue is intentionally empty
    until Stage 08 migrates the Library archetype. See
    `tests/test_engine_adapter.py::test_validate_fails_closed_against_the_empty_catalogue`,
    which documents this outcome and is expected to start passing once a real
    manifest exists.
    """
    info = get_engine_info()
    _require_tested_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    return _validate_project_spec(spec)


def render(spec: ProjectSpec) -> RenderedProject:
    """Render one spec to immutable in-memory files after compatibility checks.

    The public engine owns validation, composition, and rendering. This adapter
    deliberately accepts no destination path and performs no filesystem writes;
    CF-07.04 will own staging and finalisation around the returned files.
    """
    info = get_engine_info()
    _require_tested_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    return _render_project(spec)


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
