"""The single module that touches the `forge_template` engine.

Mirrors `runner.py`'s role for Copier's Python API (invariant 4): the engine
is imported in exactly one place, so it evolves without every module needing
attention. Importing this module requires the `engine` extra
(`uv sync --all-extras`, or `pip install 'create-forge[engine]'`) -- since
[ADR 0018](../../docs/adr/0018-pypi-distribution-and-the-first-engine-range.md),
`forge-template` is a real, PyPI-installable, range-bounded optional
dependency rather than a `[tool.uv.sources]`-pinned development-only one. No
module reachable from create-forge's shipped CLI entry point may import this
module;
`tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
enforces that. `compat.py` holds the range and protocol constants this
module checks against -- it is engine-free, so `cli.py`'s `doctor` command
can report them without importing this module at all.

`spec.py` builds the wire payload this module parses and validates, while this
module also exposes the discovery adapter `pipeline.py` uses, reachable today
via the hidden `new --engine-preview` flag -- see ADR 0013,
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
# `cli.py`'s lazy `except engine.ForgeEngineError` (a direct import of this
# module, not merely an attribute chain) from typing against a name this
# module only imported rather than defined.
from forge_template import ForgeEngineError as ForgeEngineError  # noqa: PLC0414
from forge_template import discover_components as _discover_components
from forge_template import map_legacy_library_answers as _map_legacy_library_answers
from forge_template import parse_project_spec as _parse_project_spec
from forge_template import render_project as _render_project
from forge_template import validate_project_spec as _validate_project_spec
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from create_forge.compat import (
    ENGINE_DISTRIBUTION,
    SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS,
    SUPPORTED_ENGINE_RANGE,
    SUPPORTED_PROJECTSPEC_PROTOCOLS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_SUPPORTED_ENGINE_SPECIFIER = SpecifierSet(SUPPORTED_ENGINE_RANGE)


class EngineCompatibilityError(Exception):
    """An installed engine is outside the supported package/protocol range.

    Carries exit status `3`'s meaning (docs/cli-conventions.md), reserved by
    ADR 0011 for exactly this failure class. Reachable today only via the
    hidden `new --engine-preview` flag (ADR 0014); the default `new` path
    still cannot produce it.
    """


def _require_supported_package(info: EngineInfo) -> None:
    """Reject an engine package outside the declared, released range."""
    if Version(info.package_version) in _SUPPORTED_ENGINE_SPECIFIER:
        return

    msg = (
        f"Detected forge-template {info.package_version}, but this "
        f"create-forge release supports {ENGINE_DISTRIBUTION}"
        f"{SUPPORTED_ENGINE_RANGE}. Run "
        f"`pip install '{ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}'` "
        "(or the equivalent `uv add`/`uv sync` invocation) to install a "
        "compatible version."
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
    """Confirm the engine matches the supported package/ProjectSpec range.

    Runs before any payload is parsed, validated, or rendered.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)


def discover() -> tuple[ComponentDescriptor, ...]:
    """Return engine-owned component descriptors after protocol negotiation.

    ProjectSpec and component-manifest compatibility are checked before the
    engine scans its installed catalogue. The descriptors are returned
    unchanged: their identifiers, presentation metadata, compatibility,
    relationships, and options remain owned and validated by `forge-template`.
    """
    info = get_engine_info()
    _require_supported_package(info)
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

    The installed `forge-template` catalogue is production: `library` and
    `cli` are both real, validated archetypes.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
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
    return _render_project(spec)


def map_legacy_library_options(
    legacy_answers: Mapping[str, str],
) -> Mapping[str, object]:
    """Translate legacy Library answers into the `library` component option.

    Thin wrapper around the public `map_legacy_library_answers` facade after
    the same compatibility checks every other operation here runs, so this
    stays the only module that touches the mapping's implementation. The
    mapping itself -- `build_backend`/`versioning_resolved` to
    `packaging_mode` -- is engine-owned; see
    docs/library-archetype.md#legacy-copier-answer-mapping in forge-template.
    `pipeline.build_generation_request` is the only caller, and only for the
    `library` archetype (CF-08.02).
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    return _map_legacy_library_answers(legacy_answers)


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
