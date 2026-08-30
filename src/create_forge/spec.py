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


def build_spec_payload(
    answers: Mapping[str, object],
    *,
    archetype: str,
    capabilities: Sequence[str] = (),
    platforms: Sequence[str] = (),
    component_options: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build a ProjectSpec wire payload from collected CLI answers.

    `archetype`/`capabilities`/`platforms`/`component_options` are always
    caller-supplied: create-forge mints no component identifiers of its own
    (ADR 0013). Until CF-06.02 supplies them from `discover_components`,
    callers are responsible for passing values a real manifest will accept.

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

    return payload
