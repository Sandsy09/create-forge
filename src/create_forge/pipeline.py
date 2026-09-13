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

from create_forge import compat, engine, lifecycle, staging, update
from create_forge.descriptors import DescriptorView
from create_forge.spec import (
    DESCRIPTOR_KIND,
    SelectionKind,
    SelectionProvenance,
    SelectionRequest,
    build_spec_payload,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from forge_template import ProjectSpec, RenderedProject, UpdatePlan

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
    inspects `DescriptorView.kind` or `.requires` itself -- it asks a
    `Catalogue` instead. `build_generation_request` accepts a `Catalogue` so a
    caller that has already discovered (`cli.py`'s default `new` flow) does
    not scan the installed catalogue a second time (ADR 0028).
    """

    descriptors: tuple[DescriptorView, ...]

    @property
    def archetypes(self) -> tuple[DescriptorView, ...]:
        """The `kind == "archetype"` descriptors, in discovery order."""
        return self.of_kind(SelectionKind.ARCHETYPE)

    def of_kind(self, kind: SelectionKind) -> tuple[DescriptorView, ...]:
        """Every descriptor of one selection kind, in discovery order."""
        wanted = DESCRIPTOR_KIND[kind]
        return tuple(d for d in self.descriptors if d.kind == wanted)

    def get(self, component_id: str) -> DescriptorView | None:
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

    def selected(self, selection: SelectionRequest) -> tuple[DescriptorView, ...]:
        """Every selected descriptor, in composition-tier then lexical order.

        Tier order is `DESCRIPTOR_KIND`'s declaration order -- archetype,
        capability, platform -- mirroring
        `forge_template.composition.COMPOSITION_TIER_ORDER`; within a tier,
        ids are sorted lexically. This is the order per-component options are
        prompted and serialised in (CF-13.04, ADR 0029). A selected id the
        catalogue does not contain is skipped -- the engine rejects it
        authoritatively.
        """
        result: list[DescriptorView] = []
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


def discover_archetypes() -> tuple[DescriptorView, ...]:
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


def finalise_files(
    files: Iterable[tuple[str, bytes]],
    destination: Path,
    *,
    metadata_json: str | None = None,
) -> tuple[str, ...]:
    """Stage, lock, finalise, and run the post-rename lifecycle for `files`.

    ADR 0021, ADR 0041, ADR 0044. Renders `files` into a directory adjacent
    to `destination`, then moves that directory into place atomically.
    `uv.lock` is created after the
    reviewed render is written and before the rename, so lock resolution
    cannot leave a partial destination. `metadata_json`, when given, is
    written into the staging tree at `engine.generation_metadata_target()`
    alongside the render -- through the same `staging.write_files`
    target-safety pass every other file gets -- so the atomic rename yields a
    project that already contains its provenance document; there is no
    window where `destination` exists without it. Omitted (the
    `--engine-source` override, ADR 0044 rule 29), no metadata document is
    written.

    Once the rename succeeds, `lifecycle.finalise_project` runs `git init`,
    an initial commit, and conditional `pre-commit` hook installation at
    `destination` -- never in staging, for the same absolute-path reason the
    direct-Copier `_tasks` cannot be staged either
    (`docs/filesystem-generation.md`). Its warnings, if any, are returned for
    the caller to print; `new` still exits `0` (ADR 0041 rule 4).

    Engine-free: `files` is already a plain `(target, content)` pair sequence
    by the time it reaches here, so this is the one finalisation body shared
    by both generation routes -- `finalise_generation_request` below (the
    default, in-process engine) and `engine_source.py`'s `--engine-source`
    override (out of process, ADR 0044), which cannot hand this function a
    real `RenderedProject` at all.
    """
    with staging.staged(destination) as staging_dir:
        all_files = (
            files
            if metadata_json is None
            else (
                *files,
                (
                    engine.generation_metadata_target(),
                    metadata_json.encode(),
                ),
            )
        )
        staging.write_files(staging_dir, all_files)
        staging.create_uv_lock(staging_dir)
    return lifecycle.finalise_project(destination)


def finalise_generation_request(
    request: GenerationRequest, destination: Path
) -> tuple[str, ...]:
    """Stage, lock, finalise, and run the post-rename lifecycle for `request`.

    ADR 0021, ADR 0041. `create-forge` does not call
    `forge_template.validate_rendered_project`
    itself -- `engine.render()` already did, as the last step inside
    `build_generation_request`. Reaching this function at all means that
    validation already passed; this function's only job is the filesystem and
    lifecycle half create-forge owns, all done by `finalise_files`.

    The engine is contractually required to return generation metadata for
    every render (`RenderedProject.metadata` is only ever `None` on a route
    that never asked for one -- `--engine-source`, which does not call this
    function). A `None` metadata document here is a provider-contract
    violation, not a normal failure mode: it fails closed with a
    `StagingError` before anything is written, since an un-updatable project
    with no diagnostic is worse than an exit `1`.
    """
    if request.rendered.metadata is None:
        msg = "the engine returned no generation metadata for this render"
        raise staging.StagingError(msg)
    return finalise_files(
        ((file.target, file.content) for file in request.rendered.files),
        destination,
        metadata_json=request.rendered.metadata.to_json(),
    )


class UnavailableRecordedReleaseError(Exception):
    """The recorded `forge-template` release could not be reproduced.

    ADR 0041 rules 21-22: the old render for an engine-native update could
    not be provisioned. Carries the recorded version so the caller can name
    it in the required
    "axis, detected value, required action" report and offer `--degraded`
    (`update.degraded_plan`) as the opt-in fallback -- this engine never
    performs that comparison itself (CF-ROADMAP-01-EX-01).
    """

    def __init__(self, recorded_version: str, reason: str) -> None:
        super().__init__(
            f"the recorded forge-template {recorded_version} is unavailable: {reason}"
        )
        self.recorded_version = recorded_version
        self.reason = reason


@dataclass(frozen=True, slots=True)
class UpdatePreparation:
    """One in-memory result of an engine-native update's classification.

    Reproduces the old/new render pair and asks the engine to classify the
    update (ADR 0041 rules 9-15). Ready for `update.apply_renames`/`apply_plan`
    to apply against the working tree; nothing here has touched `project` yet.
    """

    plan: UpdatePlan
    new: RenderedProject
    old: Mapping[str, bytes]
    recorded: update.RecordedDocument


def _effective_render(spec_payload: Mapping[str, object]) -> RenderedProject:
    """Re-parse, re-validate, and render a recorded spec on the installed engine.

    Decision 5: the effective spec for an update is always the recorded spec
    verbatim; `update` gains no selection flags.
    """
    spec = engine.build_project_spec(spec_payload)
    validated = engine.validate(spec)
    return engine.render(validated)


def _reproduce_old(
    recorded: update.RecordedDocument, new: RenderedProject
) -> dict[str, bytes]:
    """Reproduce the old render (ADR 0041 rule 9), decision 1's short-circuit.

    Renders in process when the recorded and installed provider versions
    already match. Decision 5 fixes the effective spec to the recorded spec
    verbatim, so a matching version means `old` and `new` are the *same*
    render -- there is nothing to reproduce, and no engine-source
    provisioning is needed at all. Otherwise the recorded release is
    provisioned out of process through the
    existing `--engine-source` machinery (ADR 0044) and rendered there; a
    provisioning or negotiation failure becomes
    `UnavailableRecordedReleaseError`, the client-detected "unavailable
    recorded release" signal ADR 0041 rules 21-22 handle.
    """
    installed_version = engine.get_info().package_version
    if recorded.provider_version == installed_version:
        return {file.target: file.content for file in new.files}

    from create_forge import engine_source  # noqa: PLC0415 - only on the drift path

    requirement = engine_source.released_requirement(recorded.provider_version)
    try:
        with engine_source.provision(requirement) as runtime:
            engine_source.negotiate(runtime)
            files = engine_source.render(runtime, dict(recorded.spec))
    except (engine_source.EngineSourceError, compat.EngineCompatibilityError) as exc:
        version = recorded.provider_version
        raise UnavailableRecordedReleaseError(version, str(exc)) from exc
    return dict(files)


def prepare_update(project: Path) -> UpdatePreparation:
    """Reproduce old/new and classify one engine-native update.

    The pure "what would change" half, shared by `--dry-run` and a real run.
    Raises `update.UpdateError` for a malformed metadata document,
    `UnavailableRecordedReleaseError` when the recorded release cannot be
    reproduced, and `engine.EngineCompatibilityError`/`engine.ForgeEngineError`
    for the installed-engine negotiation and classification calls.
    """
    metadata_filename = engine.generation_metadata_target()
    recorded = update.read_recorded(project, metadata_filename=metadata_filename)
    new = _effective_render(recorded.spec)
    old = _reproduce_old(recorded, new)
    plan = engine.plan_update(recorded.raw, old=old, new=new)
    return UpdatePreparation(plan=plan, new=new, old=old, recorded=recorded)


def prepare_degraded_update(
    project: Path,
) -> tuple[update.RecordedDocument, RenderedProject]:
    """The effective render and recorded document a degraded update needs.

    No old render is attempted at all -- `--degraded` (decision 4) never
    tries to reproduce the recorded release, whether or not it would in fact
    succeed; "pristine" is decided from the recorded per-target digests
    instead (`update.degraded_plan`).
    """
    metadata_filename = engine.generation_metadata_target()
    recorded = update.read_recorded(project, metadata_filename=metadata_filename)
    return recorded, _effective_render(recorded.spec)
