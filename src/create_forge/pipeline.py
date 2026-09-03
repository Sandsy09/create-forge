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
from create_forge.spec import (
    DESCRIPTOR_KIND,
    SelectionKind,
    SelectionProvenance,
    SelectionRequest,
    build_spec_payload,
    legacy_library_answers,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from forge_template import ComponentDescriptor, ProjectSpec, RenderedProject

_KIND_BY_DESCRIPTOR: Mapping[str, SelectionKind] = {
    descriptor_kind: selection_kind
    for selection_kind, descriptor_kind in DESCRIPTOR_KIND.items()
}


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One in-memory result of the shared create pipeline.

    Ready for CF-07.04 to stage and finalise. No filesystem write happens
    here or in anything this wraps -- `engine.render()` is in-memory only.
    """

    spec: ProjectSpec
    rendered: RenderedProject


@dataclass(frozen=True, slots=True)
class Catalogue:
    """One `engine.discover()` result, grouped and queried by kind.

    The single place descriptor *shape* is interpreted (CF-08.02's rule):
    `cli.py` reads component ids and human text off descriptors but never
    inspects `ComponentDescriptor.kind` or `.requires` itself -- it asks a
    `Catalogue` instead. `build_generation_request` accepts a `Catalogue` so a
    caller that has already discovered (the `--engine-preview` flow) does not
    scan the installed catalogue a second time (ADR 0028).
    """

    descriptors: tuple[ComponentDescriptor, ...]

    @property
    def archetypes(self) -> tuple[ComponentDescriptor, ...]:
        """The `kind == "archetype"` descriptors, in discovery order."""
        return self.of_kind(SelectionKind.ARCHETYPE)

    def of_kind(self, kind: SelectionKind) -> tuple[ComponentDescriptor, ...]:
        """Every descriptor of one selection kind, in discovery order."""
        wanted = DESCRIPTOR_KIND[kind]
        return tuple(d for d in self.descriptors if d.kind == wanted)

    def get(self, component_id: str) -> ComponentDescriptor | None:
        """The descriptor with this id, or `None` if the catalogue has none."""
        return next((d for d in self.descriptors if d.id == component_id), None)

    def kind_of(self, component_id: str) -> SelectionKind | None:
        """The selection kind of a discovered id, or `None` if unknown."""
        descriptor = self.get(component_id)
        if descriptor is None:
            return None
        return _KIND_BY_DESCRIPTOR.get(descriptor.kind)

    def required_ids(self, component_id: str, kind: SelectionKind) -> tuple[str, ...]:
        """Direct requirements of one component that are themselves of `kind`.

        No transitive closure: only the descriptor's own `requires` tuple. A
        `ComponentRelation` carries only an `id`, so its kind is resolved by
        looking that id up here; a relation naming an id this catalogue does
        not contain is dropped -- the engine rejects it authoritatively, and
        `create-forge` computes no requirement closure of its own
        ([ADR 0028](../../docs/adr/0028-discovery-driven-component-selection.md)).
        `()` when `component_id` is not in the catalogue.
        """
        descriptor = self.get(component_id)
        if descriptor is None:
            return ()
        return tuple(
            relation.id
            for relation in descriptor.requires
            if self.kind_of(relation.id) == kind
        )

    def selected(self, selection: SelectionRequest) -> tuple[ComponentDescriptor, ...]:
        """Every selected descriptor, in composition-tier then lexical order.

        Tier order is `DESCRIPTOR_KIND`'s declaration order -- archetype,
        capability, platform -- mirroring
        `forge_template.composition.COMPOSITION_TIER_ORDER`; within a tier,
        ids are sorted lexically. This is the order per-component options are
        prompted and serialised in (CF-13.04, ADR 0029). A selected id the
        catalogue does not contain is skipped -- the engine rejects it
        authoritatively.
        """
        result: list[ComponentDescriptor] = []
        for kind in DESCRIPTOR_KIND:
            for component_id in sorted(selection.ids_for(kind)):
                descriptor = self.get(component_id)
                if descriptor is not None:
                    result.append(descriptor)
        return tuple(result)


def discover_catalogue() -> Catalogue:
    """The full discovered catalogue, after protocol negotiation (ADR 0028).

    `engine.discover()` -- the one call per `--engine-preview` invocation --
    wrapped for kind-grouped access. `discover_archetypes()` is the
    archetype-only view of the same result.
    """
    return Catalogue(engine.discover())


def discover_archetypes() -> tuple[ComponentDescriptor, ...]:
    """Engine-owned archetype descriptors, for `--engine-preview` selection.

    The `kind == "archetype"` view of `discover_catalogue()`, kept as a named
    entry point because ADR 0017 and ADR 0019 refer to it. `cli.py` now
    discovers a whole `Catalogue` once and reads `.archetypes` off it, so the
    two never run back to back.
    """
    return discover_catalogue().archetypes


def _legacy_archetype_options(
    answers: Mapping[str, object], descriptor: ComponentDescriptor | None
) -> Mapping[str, object] | None:
    """The legacy `build_backend`/`versioning` -> `packaging_mode` mapping,
    or `None` when it does not apply.

    `library` predates the engine, so its legacy answers need translating into
    the production `packaging_mode` option or a user's choice silently reverts
    to the engine's own default. CF-08.03's archetype-parity review
    (ADR 0019) generalised the gate off a hardcoded `archetype == "library"`
    check: `engine.map_legacy_library_options` names the option it produces,
    and the selected archetype's own discovered `ComponentDescriptor.options`
    declares whether it accepts that name -- so no archetype id appears here,
    and a future archetype that wants the mapping (or `library` renamed) needs
    no change. An archetype that declares no options at all (`cli`) never
    reaches `map_legacy_library_options`.
    """  # noqa: D205
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
    return mapped


def _resolved_component_options(
    answers: Mapping[str, object],
    archetype: str,
    component_options: Mapping[str, Mapping[str, object]] | None,
    descriptors: Sequence[ComponentDescriptor],
) -> Mapping[str, Mapping[str, object]] | None:
    """Merge the legacy archetype-option fallback beneath the caller's map.

    CF-13.04 (ADR 0029) makes the legacy derivation *per option name* rather
    than all-or-nothing: it fills a declared archetype option the caller left
    unset, and never overrides one they did supply -- rule 3 of
    docs/component-selection.md's precedence (`--component-option` > `--data` >
    legacy > default). Before CF-13.04 the whole derivation was skipped the
    moment `component_options` was non-`None`, which a selected capability's
    namespace alone would trigger -- silently defeating the archetype's own
    `--data build_backend=...` fallback.

    `map_legacy_library_options` is only consulted when the archetype declares
    an option name the caller has not filled, so the caller-supplies-everything
    and no-options (`cli`) cases still never call it.
    """
    supplied = component_options or {}
    supplied_archetype = dict(supplied.get(archetype, {}))
    descriptor = next((d for d in descriptors if d.id == archetype), None)
    declared = {option.name for option in descriptor.options} if descriptor else set()

    unset = declared - supplied_archetype.keys()
    if not unset:
        return component_options

    legacy = _legacy_archetype_options(answers, descriptor)
    if legacy is None:
        return component_options
    additions = {name: value for name, value in legacy.items() if name in unset}
    if not additions:
        return component_options

    result: dict[str, Mapping[str, object]] = {
        component_id: dict(options) for component_id, options in supplied.items()
    }
    result[archetype] = {**additions, **supplied_archetype}
    return result


def build_generation_request(
    answers: Mapping[str, object],
    *,
    selection: SelectionRequest,
    component_options: Mapping[str, Mapping[str, object]] | None = None,
    provenance: SelectionProvenance | None = None,
    catalogue: Catalogue | None = None,
) -> GenerationRequest:
    """Run the shared pipeline: discover -> build -> validate -> render.

    Interactive and non-interactive `new` invocations both converge here once
    they've collected the same `answers` mapping `cli._collect_answers`
    already produces today -- nothing about answer collection changes.

    This is create-forge's "construct the effective ProjectSpec" step
    (docs/organisation-policy-consumption.md, CF-09.01, ADR 0022): a
    policy-aware caller resolves policy immediately before calling this
    function and passes the result as `selection`/`provenance`. `selection`
    stays caller-supplied (ADR 0013): this pipeline mints no component
    identifiers of its own, and today's only caller (`cli.py`) always marks
    its archetype explicit. `provenance`, when given, is threaded straight
    through to `build_spec_payload` -- this function resolves no policy and
    merges no policy itself. `component_options` the caller supplies is kept
    as given; `_resolved_component_options` only fills a declared archetype
    option the caller left unset, from the legacy `build_backend`/`versioning`
    fallback this repository still owns -- per option name since CF-13.04
    (ADR 0029), gated on the selected archetype's own discovered descriptor
    rather than a hardcoded id (CF-08.03, ADR 0019).

    `catalogue`, when supplied, is the already-discovered `Catalogue` the
    caller holds (`cli.py`'s `--engine-preview` flow discovers once for
    archetype and capability/platform selection, then hands it straight
    here); omitted, this function discovers its own. Either way
    `engine.discover()` runs exactly once per invocation (ADR 0028). The
    catalogue is used only for the legacy-option gate above -- selection
    itself is already resolved into `selection` upstream.

    Every downstream call (`build_project_spec`, `validate`, `render`)
    independently re-checks package/protocol compatibility before doing its
    own work, so there is no side effect -- in-memory or otherwise -- before
    every check has passed.
    """
    if catalogue is None:
        catalogue = discover_catalogue()
    resolved_options = _resolved_component_options(
        answers, selection.archetype, component_options, catalogue.descriptors
    )
    payload = build_spec_payload(
        answers,
        archetype=selection.archetype,
        capabilities=selection.capabilities,
        platforms=selection.platforms,
        component_options=resolved_options,
        provenance=provenance,
    )
    spec = engine.build_project_spec(payload)
    validated = engine.validate(spec)
    rendered = engine.render(validated)
    return GenerationRequest(spec=validated, rendered=rendered)


def finalise_generation_request(request: GenerationRequest, destination: Path) -> None:
    """Stage, lock, and finalise `request`'s rendered files (ADR 0021).

    Renders them into a directory adjacent to `destination`, then moves that
    directory into place atomically. ``uv.lock`` is created after the reviewed
    render is written and before the rename, so lock resolution cannot leave a
    partial destination.

    `create-forge` does not call `forge_template.validate_rendered_project`
    itself -- `engine.render()` already did, as the last step inside
    `build_generation_request`. Reaching this function at all means that
    validation already passed; this function's only job is the filesystem
    half create-forge owns: staging, target-safety, lock finalisation, and an
    atomic rename.
    """
    with staging.staged(destination) as staging_dir:
        staging.write_files(
            staging_dir,
            ((file.target, file.content) for file in request.rendered.files),
        )
        staging.create_uv_lock(staging_dir)
