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

# Explicit self-reexport: mypy strict's no_implicit_reexport otherwise blocks
# `cli.py`'s `except engine.ForgeEngineError` (a direct import of this
# module, not merely an attribute chain) from typing against a name this
# module only imported rather than defined.
from forge_template import (
    ComponentDescriptor,
    EngineInfo,
    ProjectSpec,
    RenderedProject,
    get_engine_info,
)
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

    # `GenerationMetadata`/`ReproductionRecord`/`UpdatePlan` are 0.5.0-only
    # additions (FT-17.01/FT-17.04) -- unlike the names imported above, which
    # every supported and out-of-range engine alike has always had, these
    # cannot be imported at module scope (see `plan_update`/`metadata_json`
    # below, and `generation_metadata_target`'s own docstring for the
    # identical reasoning that first caught this class of bug, ADR 0045).
    # Only `GenerationMetadata`/`UpdatePlan` appear in a type annotation here;
    # `ReproductionRecord` is used only at runtime, inside `metadata_json`'s
    # own lazy import, after compatibility is confirmed.
    from forge_template import GenerationMetadata, UpdatePlan


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


def plan_update(
    recorded: str, *, old: Mapping[str, bytes], new: RenderedProject
) -> UpdatePlan:
    """Classify an engine-native update after compatibility checks.

    Delegates to `forge_template.plan_update` -- see its own docstring for
    the negotiation, fail-closed, and classification rules this exposes
    unchanged (CF-ROADMAP-01-EX-01: no re-implementation in the client).
    `recorded` is the raw JSON text `update.read_recorded` reads from
    `.forge/generation.json`; `old`/`new` are the reproduced and freshly
    rendered file sets `pipeline.prepare_update` already produced.

    `forge_template.plan_update` itself is imported lazily, inside this
    function body rather than at module scope: it is a `0.5.0`-only addition
    (FT-17.04), so an out-of-range engine that predates it would otherwise
    turn this module's own import into a misleading "engine not installed"
    `ImportError` before the compatibility checks below ever run -- the exact
    bug `generation_metadata_target()` already documents and ADR 0045 fixed
    for `DEFAULT_GENERATION_METADATA_TARGET`. The checks below run first, so
    by the time this import executes, compatibility is already confirmed.
    """
    info = get_engine_info()
    _require_supported_package(info)
    _require_projectspec_protocol(info)
    _require_component_manifest_protocol(info)
    _require_metadata_version(info)
    from forge_template import plan_update as _plan_update  # noqa: PLC0415

    return _plan_update(recorded, old=old, new=new)


def metadata_json(
    metadata: GenerationMetadata, *, degraded_reason: str | None = None
) -> str:
    """The canonical, persistable JSON for one generation-metadata document.

    Callers extract `metadata` from a `RenderedProject.metadata` they have
    already confirmed is not `None` -- `pipeline.finalise_generation_request`'s
    fail-closed check for the `new` path applies identically to the update
    path's own caller, which only ever calls this after a successful
    `pipeline.prepare_update`/`prepare_degraded_update` -- both already
    compatibility-gated. `degraded_reason`, when given, marks the document
    `reproduction.mode = "degraded"` (ADR 0041 rule 22) via `model_copy`:
    `GenerationMetadata` is frozen, so this is the documented way a client
    sets a field the engine itself never populates on a fresh render.
    `ReproductionRecord` is a `0.5.0`-only addition, so it is imported
    lazily here for the identical reason `plan_update` imports its own
    forge_template name lazily above.
    """
    if degraded_reason is None:
        return metadata.to_json()
    from forge_template import ReproductionRecord  # noqa: PLC0415

    reproduction = ReproductionRecord(mode="degraded", reason=degraded_reason)
    degraded = metadata.model_copy(update={"reproduction": reproduction})
    return degraded.to_json()


def generation_metadata_target() -> str:
    """The provider's documented default persisted-metadata path (ADR 0041
    rule 5) -- re-exported rather than duplicated as a second
    `.forge/generation.json` literal, so the two names can never drift apart.

    Imported lazily, not at module scope: an installed engine outside
    `compat.SUPPORTED_ENGINE_RANGE` may predate this constant entirely (it
    was published only at the `0.5.0` cutover, FT-17.01/ADR 0062) -- a
    module-level import would turn that mismatch into a misleading "engine
    not installed" `ImportError` raised before `negotiate_protocol`'s own
    compatibility check ever runs, instead of the intended
    `EngineCompatibilityError`. `pipeline.finalise_files` only calls this
    after a render has already succeeded through every compatibility-gated
    function above, so by the time this import runs, compatibility is
    already confirmed.
    """  # noqa: D205
    from forge_template import DEFAULT_GENERATION_METADATA_TARGET  # noqa: PLC0415

    return DEFAULT_GENERATION_METADATA_TARGET


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
