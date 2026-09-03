r"""A minimal Blueprint-style downstream client (CF-09.02, ADR 0023).

This module is a second, independent CLI over the public `forge_template`
facade. It imports nothing from `create_forge` -- not `create_forge.engine`,
not `create_forge.pipeline`, not `create_forge.spec` -- and no
`forge_template.*` submodule, only the top-level package. That boundary is
the point of this file: it demonstrates that a downstream client reuses the
engine directly rather than depending on this repository, and
`tests/test_downstream_reference.py::test_imports_no_create_forge_module`
holds it with an AST guard rather than a comment alone.

Deliberately not a shipped `create-forge` capability: it lives under
`examples/`, is excluded from the wheel and the sdist, and is not imported by
any module under `src/`. See docs/downstream-client-reference.md for the full
contract this file characterizes, and
docs/organisation-policy-consumption.md for the create-forge-side hook this
is *not* using.

Deliberately minimal on policy: this resolver implements protocol v1's
authority order and enough of its merge/validation rules to demonstrate them
working end to end, not the exhaustive 17-detail-code surface. That
exhaustive proof belongs to forge-template's own
`tests/organisation_policy_contract.py`
(docs/organisation-policy-fixtures.md) -- duplicating it here would be
exactly what CF-09.02's own final acceptance criterion forbids.

Run it:

    uv run python examples/downstream_cli.py --name "Example Service" \\
        --policy examples/policies/example-baseline.json

    uv run python examples/downstream_cli.py --name "Example Service" \\
        --policy examples/policies/example-baseline.json \\
        --output ./example-service
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from forge_template import (
    ComponentDescriptor,
    EngineInfo,
    ForgeEngineError,
    ProjectSpec,
    RenderedProject,
    discover_components,
    get_engine_info,
    parse_project_spec,
    plan_generation,
    render_project,
    validate_project_spec,
)
from packaging.specifiers import SpecifierSet
from packaging.version import Version

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# -- This client's own compatibility bounds -----------------------------------
# Deliberately not imported from `create_forge.compat`: a second client
# declares its own supported range against the same published engine
# surface (docs/compatibility-policy.md), which is the point being
# demonstrated. It happens to match create-forge's own range today; nothing
# requires that to stay true.

SUPPORTED_ENGINE_RANGE = ">=0.4,<0.5"
SUPPORTED_PROJECTSPEC_PROTOCOLS = (1,)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_UNSUPPORTED_ENGINE = 3


class UnsupportedEngineError(Exception):
    """The installed `forge-template` is outside this client's own range.

    Reserves exit status 3, mirroring create-forge's own ADR 0011 reservation
    by independent choice -- compatibility-policy.md leaves presentation
    entirely client-owned; this client picks the same number because it is a
    sensible one, not because it imported it from anywhere.
    """


def negotiate(info: EngineInfo) -> None:
    """Confirm the installed engine matches this client's own range.

    Takes `info` as a parameter rather than calling `get_engine_info()`
    itself, so the failure path is unit-testable with a constructed
    `EngineInfo` -- no monkeypatching, no second isolated install.
    """
    specifier = SpecifierSet(SUPPORTED_ENGINE_RANGE)
    if Version(info.package_version) not in specifier:
        msg = (
            f"forge-template package: detected {info.package_version}, "
            f"this client supports {SUPPORTED_ENGINE_RANGE}. Install a "
            f"compatible version: pip install 'forge-template{SUPPORTED_ENGINE_RANGE}'."
        )
        raise UnsupportedEngineError(msg)

    supported = set(SUPPORTED_PROJECTSPEC_PROTOCOLS)
    detected = set(info.projectspec_protocols)
    if not supported & detected:
        msg = (
            f"ProjectSpec protocol: detected {sorted(detected)}, this "
            f"client supports {sorted(supported)}. No compatible protocol "
            "is shared -- upgrade or downgrade forge-template to a release "
            "that publishes a shared protocol integer."
        )
        raise UnsupportedEngineError(msg)


# -- A minimal organisation-policy resolver (protocol v1) --------------------
#
# Authority order (docs/organisation-policy.md):
#
#   profile default
#     < merged organisation-policy default
#       < explicit user choice          (an explicitly empty list included)
#         < required or forbidden constraint   (validates; never mutates)


@dataclass(frozen=True)
class Policy:
    """One parsed organisation-policy document -- protocol v1's wire shape."""

    id: str
    default_archetype: str | None = None
    default_capabilities: frozenset[str] = frozenset()
    default_platforms: frozenset[str] = frozenset()
    required_archetype: str | None = None
    required_capabilities: frozenset[str] = frozenset()
    required_platforms: frozenset[str] = frozenset()
    forbidden_archetypes: frozenset[str] = frozenset()
    forbidden_capabilities: frozenset[str] = frozenset()
    forbidden_platforms: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MergedPolicy:
    """The union of zero or more `Policy` documents."""

    policy_ids: tuple[str, ...] = ()
    default_archetype: str | None = None
    default_capabilities: frozenset[str] = frozenset()
    default_platforms: frozenset[str] = frozenset()
    required_archetype: str | None = None
    required_capabilities: frozenset[str] = frozenset()
    required_platforms: frozenset[str] = frozenset()
    forbidden_archetypes: frozenset[str] = frozenset()
    forbidden_capabilities: frozenset[str] = frozenset()
    forbidden_platforms: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ExplicitSelection:
    """What the user explicitly chose, before any policy is applied.

    `None` for `capabilities`/`platforms` means absent -- a policy default
    may fill it; an empty tuple is an explicit choice of "none" and is never
    overwritten. Mirrors `create_forge.spec.SelectionRequest`'s rule
    independently, on a client that does not import it.
    """

    archetype: str | None = None
    capabilities: tuple[str, ...] | None = None
    platforms: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ResolvedSelection:
    """The effective selection after policy resolution."""

    archetype: str
    capabilities: tuple[str, ...]
    platforms: tuple[str, ...]
    applied_policy_ids: tuple[str, ...]


@dataclass(frozen=True)
class PolicyErrorDetail:
    """One sorted `(code, path, message)` triple -- protocol v1's shape."""

    code: str
    path: str
    message: str


class PolicyError(Exception):
    """A structured organisation-policy failure.

    Deliberately its own type, not `forge_template.ForgeEngineError`: policy
    resolution is entirely client-side, so the engine's structured-error
    surface must stay unchanged by it (docs/organisation-policy-fixtures.md).
    `category` is one of protocol v1's three: `invalid-organisation-policy`,
    `organisation-policy-conflict`, `organisation-policy-violation`.
    """

    def __init__(self, category: str, details: Sequence[PolicyErrorDetail]) -> None:
        self.category = category
        self.details = tuple(sorted(details, key=lambda d: (d.path, d.code)))
        summary = "; ".join(f"{d.path}: {d.message}" for d in self.details)
        super().__init__(f"{category}: {summary}")


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _string_set(value: object, *, field_name: str) -> frozenset[str]:
    if value is None:
        return frozenset()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "invalid-field-type", field_name, "must be a list of strings"
                )
            ],
        )
    result = frozenset(value)
    if len(result) != len(value):
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "duplicate-selection-id", field_name, "contains a duplicate id"
                )
            ],
        )
    for item in result:
        if not _IDENTIFIER_RE.match(item):
            raise PolicyError(
                "invalid-organisation-policy",
                [
                    PolicyErrorDetail(
                        "invalid-policy-id",
                        field_name,
                        f"{item!r} is not a valid identifier",
                    )
                ],
            )
    return result


def load_policy(path: Path) -> Policy:
    """Parse one organisation-policy document from disk.

    Only the rules this example's authority order actually exercises are
    checked -- `policy_version`, `id`, and the three rule objects. This is
    not a conformant protocol-v1 validator; see this module's own docstring.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "invalid-field-type", str(path), f"could not read or parse: {exc}"
                )
            ],
        ) from exc

    if raw.get("policy_version") != 1:
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "unsupported-policy-version", str(path), "policy_version must be 1"
                )
            ],
        )
    policy_id = raw.get("id")
    if not isinstance(policy_id, str) or not _IDENTIFIER_RE.match(policy_id):
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "invalid-policy-id",
                    str(path),
                    "id must be a lower-case kebab-case string",
                )
            ],
        )

    defaults = raw.get("defaults") or {}
    required = raw.get("required") or {}
    forbidden = raw.get("forbidden") or {}
    if not defaults and not required and not forbidden:
        raise PolicyError(
            "invalid-organisation-policy",
            [
                PolicyErrorDetail(
                    "empty-policy", policy_id, "at least one rule is required"
                )
            ],
        )

    return Policy(
        id=policy_id,
        default_archetype=defaults.get("archetype"),
        default_capabilities=_string_set(
            defaults.get("capabilities"),
            field_name=f"{policy_id}.defaults.capabilities",
        ),
        default_platforms=_string_set(
            defaults.get("platforms"), field_name=f"{policy_id}.defaults.platforms"
        ),
        required_archetype=required.get("archetype"),
        required_capabilities=_string_set(
            required.get("capabilities"),
            field_name=f"{policy_id}.required.capabilities",
        ),
        required_platforms=_string_set(
            required.get("platforms"), field_name=f"{policy_id}.required.platforms"
        ),
        forbidden_archetypes=_string_set(
            forbidden.get("archetypes"), field_name=f"{policy_id}.forbidden.archetypes"
        ),
        forbidden_capabilities=_string_set(
            forbidden.get("capabilities"),
            field_name=f"{policy_id}.forbidden.capabilities",
        ),
        forbidden_platforms=_string_set(
            forbidden.get("platforms"), field_name=f"{policy_id}.forbidden.platforms"
        ),
    )


def merge_policies(policies: Sequence[Policy]) -> MergedPolicy:
    """Union zero or more policies. Order never affects the result.

    Raises `organisation-policy-conflict` for the three contradictions this
    example demonstrates: duplicate ids, distinct archetype defaults or
    requirements, and a default/required selection that is also forbidden.
    Protocol v1 defines more; see this module's own docstring.
    """
    if not policies:
        return MergedPolicy()

    ids = [p.id for p in policies]
    if len(set(ids)) != len(ids):
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "duplicate-policy-id",
                    "policies",
                    "the same policy id was applied twice",
                )
            ],
        )

    default_archetypes = {
        p.default_archetype for p in policies if p.default_archetype is not None
    }
    if len(default_archetypes) > 1:
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "conflicting-archetype-default",
                    "policies",
                    f"distinct archetype defaults: {sorted(default_archetypes)}",
                )
            ],
        )
    required_archetypes = {
        p.required_archetype for p in policies if p.required_archetype is not None
    }
    if len(required_archetypes) > 1:
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "conflicting-archetype-requirement",
                    "policies",
                    f"distinct required archetypes: {sorted(required_archetypes)}",
                )
            ],
        )
    merged_default_archetype = next(iter(default_archetypes), None)
    merged_required_archetype = next(iter(required_archetypes), None)
    if (
        merged_default_archetype is not None
        and merged_required_archetype is not None
        and merged_default_archetype != merged_required_archetype
    ):
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "default-requirement-conflict",
                    "policies",
                    "an archetype default differs from a required archetype",
                )
            ],
        )

    merged_default_capabilities = frozenset().union(
        *(p.default_capabilities for p in policies)
    )
    merged_default_platforms = frozenset().union(
        *(p.default_platforms for p in policies)
    )
    merged_required_capabilities = frozenset().union(
        *(p.required_capabilities for p in policies)
    )
    merged_required_platforms = frozenset().union(
        *(p.required_platforms for p in policies)
    )
    merged_forbidden_archetypes = frozenset().union(
        *(p.forbidden_archetypes for p in policies)
    )
    merged_forbidden_capabilities = frozenset().union(
        *(p.forbidden_capabilities for p in policies)
    )
    merged_forbidden_platforms = frozenset().union(
        *(p.forbidden_platforms for p in policies)
    )

    if (
        merged_default_archetype is not None
        and merged_default_archetype in merged_forbidden_archetypes
    ):
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "default-forbidden-conflict",
                    "policies.archetype",
                    f"default archetype {merged_default_archetype!r} is also forbidden",
                )
            ],
        )
    if (
        merged_required_archetype is not None
        and merged_required_archetype in merged_forbidden_archetypes
    ):
        raise PolicyError(
            "organisation-policy-conflict",
            [
                PolicyErrorDetail(
                    "required-forbidden-conflict",
                    "policies.archetype",
                    f"required archetype {merged_required_archetype!r} is also "
                    "forbidden",
                )
            ],
        )
    for kind, defaults_set, forbidden_set in (
        ("capabilities", merged_default_capabilities, merged_forbidden_capabilities),
        ("platforms", merged_default_platforms, merged_forbidden_platforms),
    ):
        overlap = defaults_set & forbidden_set
        if overlap:
            raise PolicyError(
                "organisation-policy-conflict",
                [
                    PolicyErrorDetail(
                        "default-forbidden-conflict",
                        f"policies.{kind}",
                        f"default and forbidden overlap: {sorted(overlap)}",
                    )
                ],
            )
    for kind, required_set, forbidden_set in (
        ("capabilities", merged_required_capabilities, merged_forbidden_capabilities),
        ("platforms", merged_required_platforms, merged_forbidden_platforms),
    ):
        overlap = required_set & forbidden_set
        if overlap:
            raise PolicyError(
                "organisation-policy-conflict",
                [
                    PolicyErrorDetail(
                        "required-forbidden-conflict",
                        f"policies.{kind}",
                        f"required and forbidden overlap: {sorted(overlap)}",
                    )
                ],
            )

    return MergedPolicy(
        policy_ids=tuple(sorted(ids)),
        default_archetype=merged_default_archetype,
        default_capabilities=merged_default_capabilities,
        default_platforms=merged_default_platforms,
        required_archetype=merged_required_archetype,
        required_capabilities=merged_required_capabilities,
        required_platforms=merged_required_platforms,
        forbidden_archetypes=merged_forbidden_archetypes,
        forbidden_capabilities=merged_forbidden_capabilities,
        forbidden_platforms=merged_forbidden_platforms,
    )


def apply_authority_order(
    merged: MergedPolicy,
    *,
    explicit: ExplicitSelection,
    profile_default_archetype: str | None,
) -> tuple[str | None, frozenset[str], frozenset[str]]:
    """Resolve archetype/capabilities/platforms by authority order alone.

    Pure selection logic: no validation, no catalogue lookup. Kept separate
    from `resolve()` so it is directly testable independent of what the
    installed catalogue happens to contain -- docs/organisation-policy.md is
    explicit that "policy syntax alone cannot prove that a component
    exists"; that is a later, separate step.
    """
    archetype = (
        explicit.archetype or merged.default_archetype or profile_default_archetype
    )
    capabilities = (
        frozenset(explicit.capabilities)
        if explicit.capabilities is not None
        else merged.default_capabilities
    )
    platforms = (
        frozenset(explicit.platforms)
        if explicit.platforms is not None
        else merged.default_platforms
    )
    return archetype, capabilities, platforms


def _validate_against_policy(
    merged: MergedPolicy,
    *,
    archetype: str,
    capabilities: frozenset[str],
    platforms: frozenset[str],
) -> None:
    """Required/forbidden rules validate the resolved selection.

    They never silently add, remove, or replace an explicit choice --
    `apply_authority_order` has already produced the final selection by the
    time this runs.
    """
    details: list[PolicyErrorDetail] = []
    if archetype in merged.forbidden_archetypes:
        details.append(
            PolicyErrorDetail(
                "forbidden-selection-selected",
                "components.archetype",
                f"{archetype!r} is forbidden",
            )
        )
    if merged.required_archetype is not None and archetype != merged.required_archetype:
        details.append(
            PolicyErrorDetail(
                "required-selection-missing",
                "components.archetype",
                f"policy requires {merged.required_archetype!r}",
            )
        )
    missing_capabilities = merged.required_capabilities - capabilities
    if missing_capabilities:
        details.append(
            PolicyErrorDetail(
                "required-selection-missing",
                "components.capabilities",
                f"missing required: {sorted(missing_capabilities)}",
            )
        )
    forbidden_capabilities_selected = capabilities & merged.forbidden_capabilities
    if forbidden_capabilities_selected:
        details.append(
            PolicyErrorDetail(
                "forbidden-selection-selected",
                "components.capabilities",
                f"forbidden but selected: {sorted(forbidden_capabilities_selected)}",
            )
        )
    missing_platforms = merged.required_platforms - platforms
    if missing_platforms:
        details.append(
            PolicyErrorDetail(
                "required-selection-missing",
                "components.platforms",
                f"missing required: {sorted(missing_platforms)}",
            )
        )
    forbidden_platforms_selected = platforms & merged.forbidden_platforms
    if forbidden_platforms_selected:
        details.append(
            PolicyErrorDetail(
                "forbidden-selection-selected",
                "components.platforms",
                f"forbidden but selected: {sorted(forbidden_platforms_selected)}",
            )
        )
    if details:
        raise PolicyError("organisation-policy-violation", details)


def _validate_against_catalogue(
    catalogue: Iterable[ComponentDescriptor],
    *,
    archetype: str,
    capabilities: frozenset[str],
    platforms: frozenset[str],
) -> None:
    """Confirm every referenced id exists and the archetype has the right kind.

    Policy syntax alone cannot prove a component exists or has the declared
    kind (docs/organisation-policy.md) -- this is the one catalogue lookup
    that genuinely belongs client-side, since the engine never sees policy
    rules, only the resolved selection.
    """
    catalogue_by_id = {d.id: d for d in catalogue}
    unknown = [
        c for c in (archetype, *capabilities, *platforms) if c not in catalogue_by_id
    ]
    if unknown:
        raise PolicyError(
            "organisation-policy-violation",
            [
                PolicyErrorDetail(
                    "unknown-component",
                    "components",
                    f"not in the installed catalogue: {sorted(unknown)}",
                )
            ],
        )
    if catalogue_by_id[archetype].kind != "archetype":
        raise PolicyError(
            "organisation-policy-violation",
            [
                PolicyErrorDetail(
                    "component-kind-mismatch",
                    "components.archetype",
                    f"{archetype!r} is not an archetype",
                )
            ],
        )


def resolve(
    merged: MergedPolicy,
    *,
    explicit: ExplicitSelection,
    profile_default_archetype: str | None,
    catalogue: Iterable[ComponentDescriptor],
) -> ResolvedSelection:
    """Apply the full authority order, then validate against policy and catalogue."""
    archetype, capabilities, platforms = apply_authority_order(
        merged,
        explicit=explicit,
        profile_default_archetype=profile_default_archetype,
    )
    if archetype is None:
        raise PolicyError(
            "organisation-policy-violation",
            [
                PolicyErrorDetail(
                    "no-permitted-archetype",
                    "components.archetype",
                    "no explicit choice, policy default, or profile default "
                    "resolved an archetype",
                )
            ],
        )

    _validate_against_policy(
        merged, archetype=archetype, capabilities=capabilities, platforms=platforms
    )
    _validate_against_catalogue(
        catalogue, archetype=archetype, capabilities=capabilities, platforms=platforms
    )

    return ResolvedSelection(
        archetype=archetype,
        capabilities=tuple(sorted(capabilities)),
        platforms=tuple(sorted(platforms)),
        applied_policy_ids=merged.policy_ids,
    )


# -- ProjectSpec construction --------------------------------------------------

_PACKAGE_NAME_RE = re.compile(r"[^a-z0-9]+")
_REPOSITORY_NAME_RE = re.compile(r"[^a-z0-9]+")


def _derive_package_name(name: str) -> str:
    return _PACKAGE_NAME_RE.sub("_", name.strip().lower()).strip("_")


def _derive_repository_name(name: str) -> str:
    return _REPOSITORY_NAME_RE.sub("-", name.strip().lower()).strip("-")


def build_project_spec(
    args: argparse.Namespace, selection: ResolvedSelection
) -> ProjectSpec:
    """Construct the wire payload and parse it through the public facade.

    This client builds its own payload dict directly -- it has no equivalent
    of create-forge's `spec.build_spec_payload`, and does not need one for a
    single, fixed set of CLI flags.
    """
    payload: dict[str, object] = {
        "protocol_version": 1,
        "project": {
            "name": args.name,
            "package_name": _derive_package_name(args.name),
            "repository_name": _derive_repository_name(args.name),
            "description": args.description or "",
            "licence": args.licence,
            "authors": (
                [{"name": args.author_name, "email": args.author_email}]
                if args.author_name
                else []
            ),
        },
        "python": {"minimum": "3.11", "development": "3.13"},
        "components": {
            "archetype": selection.archetype,
            "capabilities": list(selection.capabilities),
            "platforms": list(selection.platforms),
        },
    }
    if selection.applied_policy_ids:
        payload["provenance"] = {"policies": list(selection.applied_policy_ids)}

    return parse_project_spec(payload)


def write_rendered_project(project: RenderedProject, destination: Path) -> None:
    """Write a rendered project to `destination`, refusing a non-empty one.

    Deliberately not staged or atomic: create-forge's own
    `staging.py`/ADR 0015 is the more careful implementation of this same
    step, referenced rather than reimplemented here (see
    docs/downstream-client-reference.md).
    """
    if destination.exists() and any(destination.iterdir()):
        msg = f"destination is not empty: {destination}"
        raise FileExistsError(msg)
    destination.mkdir(parents=True, exist_ok=True)
    for file in project.files:
        target = destination / file.target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.content)


# -- CLI -----------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "A minimal downstream CLI over the public forge_template facade "
            "(CF-09.02, ADR 0023). See examples/README.md."
        ),
    )
    parser.add_argument("--name", required=True, help="project name")
    parser.add_argument("--description", default="", help="project description")
    parser.add_argument(
        "--licence", default="mit", help="SPDX-style licence identifier"
    )
    parser.add_argument("--author-name", default=None)
    parser.add_argument("--author-email", default=None)
    parser.add_argument("--archetype", default=None, help="explicit archetype choice")
    parser.add_argument(
        "--capability",
        action="append",
        default=None,
        dest="capabilities",
        help="explicit capability choice (repeatable)",
    )
    parser.add_argument(
        "--platform",
        action="append",
        default=None,
        dest="platforms",
        help="explicit platform choice (repeatable)",
    )
    parser.add_argument(
        "--no-capabilities",
        action="store_true",
        help="explicitly choose zero capabilities (distinct from omitting "
        "--capability)",
    )
    parser.add_argument(
        "--no-platforms",
        action="store_true",
        help="explicitly choose zero platforms (distinct from omitting --platform)",
    )
    parser.add_argument(
        "--policy",
        action="append",
        default=[],
        dest="policies",
        type=Path,
        help="path to an organisation-policy JSON document (repeatable)",
    )
    parser.add_argument(
        "--profile-archetype", default=None, help="lowest-authority profile default"
    )
    parser.add_argument(
        "--output", default=None, type=Path, help="write the rendered project here"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911 - one return per distinct exit-status branch (negotiate/policy/engine/write failures, dry run, and a completed write); mirrors create_forge.cli's own accepted entry-point complexity
    """Parse arguments, negotiate, resolve policy, and render or dry-run.

    Strict order: negotiate before anything else, then discover, resolve
    policy, construct and validate the ProjectSpec, and only render/write
    last -- matching compatibility-policy.md's "fail closed... before any
    component discovery, planning, rendering, or destination write" rule.
    """
    args = _build_parser().parse_args(argv)

    try:
        info = get_engine_info()
        negotiate(info)

        catalogue = discover_components()

        capabilities = args.capabilities
        if args.no_capabilities:
            capabilities = []
        platforms = args.platforms
        if args.no_platforms:
            platforms = []
        explicit = ExplicitSelection(
            archetype=args.archetype,
            capabilities=tuple(capabilities) if capabilities is not None else None,
            platforms=tuple(platforms) if platforms is not None else None,
        )

        policies = [load_policy(path) for path in args.policies]
        merged = merge_policies(policies)
        selection = resolve(
            merged,
            explicit=explicit,
            profile_default_archetype=args.profile_archetype,
            catalogue=catalogue,
        )

        spec = build_project_spec(args, selection)
        validated = validate_project_spec(spec)
        plan = plan_generation(validated)
    except UnsupportedEngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_UNSUPPORTED_ENGINE
    except PolicyError as exc:
        print(f"error: {exc.category}", file=sys.stderr)
        for detail in exc.details:
            print(f"  {detail.path}: {detail.message} ({detail.code})", file=sys.stderr)
        return EXIT_FAILURE
    except ForgeEngineError as exc:
        print(f"error: {exc.message} ({exc.code.value})", file=sys.stderr)
        for engine_detail in exc.details:
            path = ".".join(str(p) for p in engine_detail.path)
            print(f"  {path}: {engine_detail.message}", file=sys.stderr)
        return EXIT_FAILURE

    print(
        f"engine forge-template {info.package_version} "
        f"(ProjectSpec protocol {validated.protocol_version}) OK"
    )
    if selection.applied_policy_ids:
        print(f"applied policies: {', '.join(selection.applied_policy_ids)}")
    print(
        f"archetype: {selection.archetype}  "
        f"capabilities: {list(selection.capabilities)}  "
        f"platforms: {list(selection.platforms)}"
    )
    print(f"{len(plan.files)} files planned")

    if args.output is None:
        return EXIT_OK

    try:
        rendered = render_project(validated)
        write_rendered_project(rendered, args.output)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    except ForgeEngineError as exc:
        print(f"error: {exc.message} ({exc.code.value})", file=sys.stderr)
        return EXIT_FAILURE

    print(f"wrote {len(rendered.files)} files to {args.output}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
