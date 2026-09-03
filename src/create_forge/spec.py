"""Pure ProjectSpec wire-payload construction.

This module places CLI answers into their canonical ProjectSpec position and
omits values that are absent. It performs no validation and imports nothing
from `forge_template` -- `engine.py` is the only module in this package that
touches the engine, matching invariant 4's rule for `runner.py` and Copier.
`spec.py` must stay importable and testable without the engine dependency
installed.

The one exception to "map, don't validate" is derivation: ProjectSpec's
`package_name` and `repository_name` are wire-required fields the engine
never derives, so create-forge derives them from `project_name` unless a
`--data` override supplies the matching Copier-style key (`package_name`,
`repo_name`). See docs/project-spec-construction.md for the full field
mapping and its rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from create_forge.prompts import slugify

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

PROJECT_SPEC_PROTOCOL_VERSION = 1
"""Mirrors `forge_template.PROJECT_SPEC_PROTOCOL_VERSION` without importing
the engine, since this module must stay importable without it installed.
"""

DEFAULT_PYTHON_MINIMUM = "3.11"
DEFAULT_PYTHON_DEVELOPMENT = "3.13"
"""Fallback `python` bounds, mirroring `copier.yml`'s own
`python_min_version`/`python_version` defaults (CF-08.02).

`ProjectSpec.python` is a required field, but `templates.toml` never prompts
either key -- they're on the deliberately-unasked list in this file's
sibling `templates.toml` header, same as every other question the Copier
path lets fall through to its own default. The engine path has no template
default to fall through to, so create-forge supplies the same values itself
here rather than leaving `--engine-preview` unusable without `--data`.
"""


class SelectionKind(StrEnum):
    """Which ProjectSpec `components` field a selection or policy rule names.

    Mirrors the three kinds the canonical
    [organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
    defines `defaults`/`required`/`forbidden` rules over -- see
    docs/organisation-policy-consumption.md (CF-09.01, ADR 0022).
    """

    ARCHETYPE = "archetype"
    CAPABILITIES = "capabilities"
    PLATFORMS = "platforms"


DESCRIPTOR_KIND: dict[SelectionKind, str] = {
    SelectionKind.ARCHETYPE: "archetype",
    SelectionKind.CAPABILITIES: "capability",
    SelectionKind.PLATFORMS: "platform",
}
"""The singular `ComponentDescriptor.kind` string each (plural) selection kind
maps to.

Declared in the engine's own `forge_template.composition.COMPOSITION_TIER_ORDER`
order — archetype, then capability, then platform — mirrored here rather than
imported, since that submodule is not part of the public facade. `spec.py`
stays engine-free (ADR 0013); this is a vocabulary map, not engine behaviour.
"""

SELECTABLE_KINDS: tuple[SelectionKind, ...] = (
    SelectionKind.CAPABILITIES,
    SelectionKind.PLATFORMS,
)
"""The kinds `--engine-preview` selects *alongside* the single archetype —
`components.capabilities` and `components.platforms`. Same tier order as
`DESCRIPTOR_KIND`.
"""


def _is_explicit(override: bool | None, value: Sequence[str] | None) -> bool:
    """Whether a selection kind counts as an explicit choice.

    `override` wins when set; otherwise a non-`None` `value` (including an
    empty sequence) is explicit and `None` is absent.
    """
    if override is not None:
        return override
    return value is not None


@dataclass(frozen=True, slots=True)
class SelectionRequest:
    """An effective component selection, plus which kinds were explicit.

    Deliberately not `forge_template.ComponentSelection`, which this is not:
    that type carries only the resolved result. Protocol v1 states plainly
    that ProjectSpec "cannot reconstruct" whether a selection kind was
    explicitly supplied or left to a policy default, so a policy-aware caller
    needs a place to keep that fact between resolving policy and calling
    `pipeline.build_generation_request` -- this is that place.

    Construct with `SelectionRequest.of(...)` rather than the constructor
    directly: it turns `None` (absent) versus `()`/`[]` (explicit and empty)
    into membership in `explicit`, which is easy to get backwards by hand.
    """

    archetype: str
    capabilities: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    explicit: frozenset[SelectionKind] = field(default_factory=frozenset)

    @classmethod
    def of(  # noqa: PLR0913 - one keyword per selection kind plus its explicitness override; collapsing them loses the absent-vs-empty distinction this method exists for
        cls,
        *,
        archetype: str,
        capabilities: Sequence[str] | None = None,
        platforms: Sequence[str] | None = None,
        archetype_explicit: bool = True,
        capabilities_explicit: bool | None = None,
        platforms_explicit: bool | None = None,
    ) -> SelectionRequest:
        """Build a request, inferring `explicit` from which args were passed.

        `archetype` has no absent form -- ProjectSpec always selects exactly
        one -- so its explicitness is a separate keyword rather than an
        `Optional`. `capabilities`/`platforms` follow protocol v1's rule
        directly: `None` means "no explicit choice for this kind" (a policy
        default may still apply); an empty sequence is itself an explicit
        choice of "none".

        `capabilities_explicit`/`platforms_explicit` override that inference
        for the one case it cannot express: a kind whose every discovered
        descriptor is required by the chosen archetype, so `create-forge`
        selects those ids without ever offering a choice (CF-13.03,
        [ADR 0028](adr/0028-discovery-driven-component-selection.md)). The ids
        are non-empty, but the kind was not an explicit user choice -- exactly
        `archetype_explicit=False`'s "a policy default could still have
        applied" reasoning, one tier down.
        """
        explicit = set()
        if archetype_explicit:
            explicit.add(SelectionKind.ARCHETYPE)
        if _is_explicit(capabilities_explicit, capabilities):
            explicit.add(SelectionKind.CAPABILITIES)
        if _is_explicit(platforms_explicit, platforms):
            explicit.add(SelectionKind.PLATFORMS)
        return cls(
            archetype=archetype,
            capabilities=tuple(capabilities or ()),
            platforms=tuple(platforms or ()),
            explicit=frozenset(explicit),
        )


@dataclass(frozen=True, slots=True)
class SelectionProvenance:
    """Provenance to record in `ProjectSpec.provenance` after policy resolution.

    Mirrors `forge_template.SelectionProvenance`'s field names without
    importing the engine (`spec.py` must stay importable without the `engine`
    extra installed). Deliberately holds only identifiers: protocol v1 is
    explicit that provenance "neither embeds a policy document nor grants
    rendering authority" -- there is no field here a policy document's
    content could ever populate.
    """

    profile: str | None = None
    policies: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """True when there is nothing to record -- the current CLI's case."""
        return self.profile is None and not self.policies


_PACKAGE_NAME_RE = re.compile(r"[^a-z0-9]+")


def _derive_package_name(project_name: str) -> str:
    """Lower-case, collapse non-alphanumeric runs to one underscore, trim ends.

    Deliberately not copier.yml's exact
    `{{ project_name | lower | replace(' ', '_') | replace('-', '_') }}` --
    ProjectSpec's `package_name` pattern (`^[a-z][a-z0-9_]*$`) is stricter
    than Copier's own default, and the two systems are allowed to diverge;
    the engine, not this derivation, is authoritative for validity.
    """
    return _PACKAGE_NAME_RE.sub("_", project_name.strip().lower()).strip("_")


def _string_answer(answers: Mapping[str, object], key: str) -> str | None:
    """A non-blank string answer, or None if absent/blank."""
    value = answers.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _authors(answers: Mapping[str, object]) -> list[dict[str, object]]:
    """Zero or one author -- today's registry collects at most one."""
    name = _string_answer(answers, "author_name")
    if name is None:
        return []
    author: dict[str, object] = {"name": name}
    email = _string_answer(answers, "author_email")
    if email is not None:
        author["email"] = email
    return [author]


def _project_metadata(answers: Mapping[str, object]) -> dict[str, object]:
    """Build the `project` sub-object, omitting fields with no source value.

    A missing required field (`name`, `licence`, ...) is left out rather than
    defaulted -- `engine.build_project_spec` reports it as a structured,
    field-located validation error instead of this module guessing.
    """
    metadata: dict[str, object] = {}

    project_name = _string_answer(answers, "project_name")
    if project_name is not None:
        metadata["name"] = project_name

    package_name = _string_answer(answers, "package_name")
    if package_name is None and project_name is not None:
        package_name = _derive_package_name(project_name)
    if package_name is not None:
        metadata["package_name"] = package_name

    repository_name = _string_answer(answers, "repo_name")
    if repository_name is None and project_name is not None:
        repository_name = slugify(project_name)
    if repository_name is not None:
        metadata["repository_name"] = repository_name

    description = answers.get("project_description")
    if isinstance(description, str):
        metadata["description"] = description

    licence = _string_answer(answers, "license")
    if licence is not None:
        metadata["licence"] = licence

    authors = _authors(answers)
    if authors:
        metadata["authors"] = authors

    return metadata


def _python_selection(answers: Mapping[str, object]) -> dict[str, object]:
    """Resolve both `python` bounds, falling back per-bound to the defaults.

    `ProjectSpec.python` is required, so unlike `_project_metadata`'s
    omit-if-absent fields, this always returns a value -- an explicit answer
    for one bound does not require the other, it just leaves the missing one
    at its own default (CF-08.02).
    """
    minimum = _string_answer(answers, "python_min_version") or DEFAULT_PYTHON_MINIMUM
    development = (
        _string_answer(answers, "python_version") or DEFAULT_PYTHON_DEVELOPMENT
    )
    return {"minimum": minimum, "development": development}


def legacy_library_answers(answers: Mapping[str, object]) -> dict[str, str] | None:
    """Resolve the legacy Library answer pair for `map_legacy_library_options`.

    Returns `None` if `build_backend` was never answered. Mirrors
    `copier.yml`'s own `versioning_resolved` computation: `static`
    when `build_backend` is `uv_build`, else whatever `versioning` says,
    defaulting to `static` when that question was skipped (CF-08.02). This
    stays pure and engine-free -- `engine.map_legacy_library_options` is the
    only caller that hands the result to `forge_template`.
    """
    build_backend = _string_answer(answers, "build_backend")
    if build_backend is None:
        return None
    versioning = _string_answer(answers, "versioning") or "static"
    versioning_resolved = "static" if build_backend == "uv_build" else versioning
    return {
        "build_backend": build_backend,
        "versioning_resolved": versioning_resolved,
    }


def build_spec_payload(  # noqa: PLR0913 - each keyword maps to one distinct ProjectSpec field; ~20 existing call sites already rely on archetype/capabilities/platforms staying separate rather than collapsing into one object here
    answers: Mapping[str, object],
    *,
    archetype: str,
    capabilities: Sequence[str] = (),
    platforms: Sequence[str] = (),
    component_options: Mapping[str, Mapping[str, object]] | None = None,
    provenance: SelectionProvenance | None = None,
) -> dict[str, object]:
    """Build a ProjectSpec wire payload from collected CLI answers.

    `archetype`/`capabilities`/`platforms`/`component_options` are always
    caller-supplied: create-forge mints no component identifiers of its own
    (ADR 0013). Until CF-06.02 supplies them from `discover_components`,
    callers are responsible for passing values a real manifest will accept.
    They are the *effective* selection only -- whether each kind was
    explicitly chosen or left to a policy default is `SelectionRequest`'s job
    upstream of this function, not this payload's; ProjectSpec has no field
    for that distinction (docs/organisation-policy-consumption.md).

    `provenance`, when given and non-empty, is emitted as
    `ProjectSpec.provenance` -- the applied policy IDs a resolved policy
    leaves behind, never the policy document itself. Omitted (like
    `component_options`) when there is nothing to record, so the engine's own
    empty default applies -- today's only caller.

    The same `answers` mapping produces the same payload regardless of
    whether it was collected interactively or via `--data`/config, since both
    paths already converge on one `dict[str, object]` before this function
    runs (see `cli._collect_answers`).
    """
    payload: dict[str, object] = {
        "protocol_version": PROJECT_SPEC_PROTOCOL_VERSION,
        "project": _project_metadata(answers),
        "python": _python_selection(answers),
        "components": {
            "archetype": archetype,
            "capabilities": list(capabilities),
            "platforms": list(platforms),
        },
    }

    if component_options:
        payload["component_options"] = {
            component_id: dict(options)
            for component_id, options in component_options.items()
        }

    if provenance is not None and not provenance.is_empty():
        payload["provenance"] = {
            "profile": provenance.profile,
            "policies": list(provenance.policies),
        }

    return payload
