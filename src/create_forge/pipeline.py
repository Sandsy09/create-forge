"""The shared create pipeline: discover, build, validate, render -- in memory.

This is the one internal generation path CF-07.01 introduces (ADR 0014).
It depends on `create_forge.engine` -- and therefore, transitively, on the
optional `forge-template` engine extra (ADR 0018) -- but its own source never
imports `forge_template` directly: type annotations that need engine-owned
types import them only under `TYPE_CHECKING`, so this module's runtime
behaviour never requires the engine to be *type-checkable*, only to be
*installed* when one of its functions is actually called. `engine.py` remains
the only module whose source touches `forge_template` at runtime, per ADR
0013 and invariant 4.

`create_forge.cli` imports this module lazily, inside `--engine-preview`'s
branch only, guarded by `try/except ImportError` -- see ADR 0014 for why:
`forge-template` is not installed by a plain `pip install create-forge`, so
no module reachable at `cli.py`'s own import time may depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from create_forge import engine, staging
from create_forge.spec import build_spec_payload, legacy_library_answers

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from forge_template import ComponentDescriptor, ProjectSpec, RenderedProject


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One in-memory result of the shared create pipeline.

    Ready for CF-07.04 to stage and finalise. No filesystem write happens
    here or in anything this wraps -- `engine.render()` is in-memory only.
    """

    spec: ProjectSpec
    rendered: RenderedProject


def discover_archetypes() -> tuple[ComponentDescriptor, ...]:
    """Engine-owned archetype descriptors, for `--engine-preview` selection.

    Filters `engine.discover()` to `kind == "archetype"` so `cli.py` never
    branches on engine-defined `kind` values itself (CF-08.02) -- discovery
    stays the one place that interprets descriptor shape.
    """
    return tuple(d for d in engine.discover() if d.kind == "archetype")


def _resolved_component_options(
    answers: Mapping[str, object],
    archetype: str,
    component_options: Mapping[str, Mapping[str, object]] | None,
    descriptors: Sequence[ComponentDescriptor],
) -> Mapping[str, Mapping[str, object]] | None:
    """Derive `component_options` when the caller supplied none.

    `library` predates the engine, so its legacy `build_backend`/`versioning`
    answers need translating into the production `packaging_mode` option or a
    user's choice silently reverts to the engine's own default. CF-08.03's
    archetype-parity review (ADR 0019) found this derivation keyed on a
    hardcoded `archetype != "library"` check -- the one archetype-specific
    branch in this codebase -- and generalised it: `engine.map_legacy_library_options`
    already names the option it produces (`packaging_mode`), and the
    selected archetype's own discovered `ComponentDescriptor.options` already
    declares whether it accepts that name. Applying the mapping only when the
    descriptor declares it needs no archetype id anywhere in this function,
    so a future archetype that also wants the legacy mapping (or `library`
    itself being renamed) needs no change here -- only in the engine's own
    manifest.

    The descriptor lookup runs before the mapping call, not after: an
    archetype that declares no options at all (`cli`) never needs
    `engine.map_legacy_library_options` invoked on its behalf, matching the
    old code's behaviour of never calling it for a non-`library` archetype.
    """
    if component_options is not None:
        return component_options
    descriptor = next((d for d in descriptors if d.id == archetype), None)
    if descriptor is None or not descriptor.options:
        return None
    legacy = legacy_library_answers(answers)
    if legacy is None:
        return None
    mapped = engine.map_legacy_library_options(legacy)
    if not mapped:
        return None
    declared = {option.name for option in descriptor.options}
    if not set(mapped) <= declared:
        return None
    return {archetype: mapped}


def build_generation_request(
    answers: Mapping[str, object],
    *,
    archetype: str,
    capabilities: Sequence[str] = (),
    platforms: Sequence[str] = (),
    component_options: Mapping[str, Mapping[str, object]] | None = None,
) -> GenerationRequest:
    """Run the shared pipeline: discover -> build -> validate -> render.

    Interactive and non-interactive `new` invocations both converge here once
    they've collected the same `answers` mapping `cli._collect_answers`
    already produces today -- nothing about answer collection changes.

    `archetype`/`capabilities`/`platforms` stay caller-supplied (ADR 0013):
    this pipeline mints no component identifiers of its own. An explicit
    `component_options` is likewise passed through unchanged; when the
    caller supplies none, `_resolved_component_options` derives the one
    legacy mapping this repository still owns, gated on the selected
    archetype's own discovered descriptor rather than a hardcoded id
    (CF-08.03, ADR 0019). `discover()`'s result is reused for exactly that
    gate; `discover_archetypes()` is the separate, `kind`-filtered view that
    actually drives selection, from `cli.py`.

    Every downstream call (`build_project_spec`, `validate`, `render`)
    independently re-checks package/protocol compatibility before doing its
    own work, so there is no side effect -- in-memory or otherwise -- before
    every check has passed.
    """
    descriptors = engine.discover()
    resolved_options = _resolved_component_options(
        answers, archetype, component_options, descriptors
    )
    payload = build_spec_payload(
        answers,
        archetype=archetype,
        capabilities=capabilities,
        platforms=platforms,
        component_options=resolved_options,
    )
    spec = engine.build_project_spec(payload)
    validated = engine.validate(spec)
    rendered = engine.render(validated)
    return GenerationRequest(spec=validated, rendered=rendered)


def finalise_generation_request(request: GenerationRequest, destination: Path) -> None:
    """Stage and finalise `request`'s rendered files (ADR 0015).

    Renders them into a directory adjacent to `destination`, then moves that
    directory into place atomically.

    `create-forge` does not call `forge_template.validate_rendered_project`
    itself -- `engine.render()` already did, as the last step inside
    `build_generation_request`. Reaching this function at all means that
    validation already passed; this function's only job is the filesystem
    half create-forge owns: staging, target-safety, and an atomic rename.
    """
    with staging.staged(destination) as staging_dir:
        staging.write_files(
            staging_dir,
            ((file.target, file.content) for file in request.rendered.files),
        )
