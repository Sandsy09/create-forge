"""The shared create pipeline: discover, build, validate, render -- in memory.

This is the one internal generation path CF-07.01 introduces (ADR 0014). It
depends on `create_forge.engine` -- and therefore, transitively, on
`forge-template`, a required dependency since ADR 0040 (CF-18.01) made the
engine the default `new` architecture -- but its own source never imports
`forge_template` directly: type annotations that need engine-owned types
import them only under `TYPE_CHECKING`, so this module's runtime behaviour
never requires the engine to be *type-checkable* in isolation. `engine.py`
remains the only module whose source touches `forge_template` at runtime, per
ADR 0013 and invariant 4.

`create_forge.cli` imports this module eagerly at module scope: unlike
`runner.py`'s Copier-touching calls, which now need the guarded, lazy import
`--legacy` requires (ADR 0040 inverts ADR 0014's old guard, since `copier` is
the optional dependency after the cutover), this module's only dependency is
the now-required engine.
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
)

if TYPE_CHECKING:
    from collections.abc import Mapping
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
    caller that has already discovered (`cli.py`'s default `new` flow) does
    not scan the installed catalogue a second time (ADR 0028).
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

    `engine.discover()` -- the one call per `new` invocation -- wrapped for
    kind-grouped access. `discover_archetypes()` is the archetype-only view
    of the same result.
    """
    return Catalogue(engine.discover())


def discover_archetypes() -> tuple[ComponentDescriptor, ...]:
    """Engine-owned archetype descriptors, for the engine `new` path's selection.

    The `kind == "archetype"` view of `discover_catalogue()`, kept as a named
    entry point because ADR 0017 and ADR 0019 refer to it. `cli.py` now
    discovers a whole `Catalogue` once and reads `.archetypes` off it, so the
    two never run back to back.
    """
    return discover_catalogue().archetypes


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
    merges no policy itself. `component_options` the caller supplies is passed
    through unchanged: ADR 0040 decision 10 (CF-18.01) retires the legacy
    `build_backend`/`versioning` -> `packaging_mode` `--data` fallback this
    function used to fill in; `library.packaging_mode` is now set only through
    `--component-option library.packaging_mode=<value>`, like any other
    component option.

    `catalogue`, when supplied, is the already-discovered `Catalogue` the
    caller holds (`cli.py`'s `new` flow discovers once for archetype and
    capability/platform selection, then hands it straight here); omitted,
    this function discovers its own. Either way `engine.discover()` runs
    exactly once per invocation (ADR 0028).

    Every downstream call (`build_project_spec`, `validate`, `render`)
    independently re-checks package/protocol compatibility before doing its
    own work, so there is no side effect -- in-memory or otherwise -- before
    every check has passed.
    """
    if catalogue is None:
        catalogue = discover_catalogue()
    payload = build_spec_payload(
        answers,
        archetype=selection.archetype,
        capabilities=selection.capabilities,
        platforms=selection.platforms,
        component_options=component_options,
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
