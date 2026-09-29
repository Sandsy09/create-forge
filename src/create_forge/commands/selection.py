"""Archetype/capability/platform/option resolution for the default engine
`new` path (CF-13.03/CF-13.04, ADR 0027-0029).

Used by `commands/new.py`, module-qualified (`_selection.ComponentFlags`,
`_selection._resolve_engine_selection`, ...) -- the same "one patch point"
principle `commands/_output.py` uses.
"""  # noqa: D205

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from create_forge.commands import _output
from create_forge.prompts import (
    COMPONENT_PROMPTS,
    ArchetypeChoice,
    PromptAbortedError,
    ask_project_answers,
    choose_archetype,
    choose_components,
    resolve_component_options,
)
from create_forge.spec import (
    DESCRIPTOR_KIND,
    SELECTABLE_KINDS,
    SelectionKind,
    SelectionRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from create_forge.pipeline import Catalogue


@dataclass(frozen=True, slots=True)
class ComponentFlags:
    """The engine `new` path's component-selection flags, normalised.

    `capabilities`/`platforms` are the *effective* value for one selectable
    kind: `tuple[str, ...]` from one or more `--capability`/`--platform`, `()`
    from `--no-capabilities`/`--no-platforms` (an explicit empty choice), and
    `None` when neither was given (absent -- resolve interactively or leave to
    a policy default). `new()` rejects a `--capability` + `--no-capabilities`
    contradiction before building this (CF-13.03, ADR 0028).

    `options` is the owner-namespaced `--component-option ID.OPTION=VALUE` map
    (CF-13.04, ADR 0029), empty when the flag was not given. A repeated
    `ID.OPTION` has already collapsed to its last value in `_parse_component_options`.
    """

    capabilities: tuple[str, ...] | None
    platforms: tuple[str, ...] | None
    options: Mapping[str, Mapping[str, str]]

    def for_kind(self, kind: SelectionKind) -> tuple[str, ...] | None:
        """The normalised flag value for one selectable kind."""
        if kind is SelectionKind.CAPABILITIES:
            return self.capabilities
        return self.platforms


def _normalise_kind_flag(
    values: list[str] | None, *, none_flag: bool
) -> tuple[str, ...] | None:
    """One `--capability`/`--platform` list + its `--no-*` bool → effective value."""
    if values:
        return tuple(values)
    return () if none_flag else None


def _flag_name(kind: SelectionKind) -> str:
    """The user-facing flag that selects one kind: `--capability` etc."""
    return f"--{DESCRIPTOR_KIND[kind]}"


def _validate_flag_ids(
    catalogue: Catalogue, kind: SelectionKind, ids: Sequence[str]
) -> tuple[str, ...]:
    """De-duplicate flag-supplied ids and reject unknown or wrong-kind ones.

    Shape-only, answerable from the descriptor list alone (ADR 0027): an id
    the catalogue does not contain, or one whose discovered kind is not
    `kind`. Everything semantic -- requirements, conflicts, option domains --
    stays engine-owned. Exits `1`, phrased like `_select_archetype`'s own
    unknown-archetype message.
    """
    seen: list[str] = []
    for component_id in ids:
        if component_id in seen:
            continue
        actual = catalogue.kind_of(component_id)
        if actual is None:
            valid = ", ".join(sorted(d.id for d in catalogue.of_kind(kind)))
            _output.err.print(
                f"[red]Unknown {_flag_name(kind)} {component_id!r}. "
                f"Available: {valid or 'none'}[/red]"
            )
            raise typer.Exit(1)
        if actual is not kind:
            _output.err.print(
                f"[red]{_flag_name(kind)} {component_id!r} is not a "
                f"{DESCRIPTOR_KIND[kind]} (it is the {DESCRIPTOR_KIND[actual]} "
                f"{component_id!r}).[/red]"
            )
            raise typer.Exit(1)
        seen.append(component_id)
    return tuple(seen)


def _resolve_kind(
    catalogue: Catalogue,
    descriptor: ArchetypeChoice,
    kind: SelectionKind,
    flag_value: tuple[str, ...] | None,
    *,
    yes: bool,
) -> tuple[tuple[str, ...], bool]:
    """Resolve one selectable kind to `(ids, explicit)` (CF-13.03, ADR 0028).

    Flag given → validated ids, explicit. No descriptors of this kind, or
    `--yes` with no flag → `((), False)` (absent; never prompted). Every
    descriptor required by the archetype → those ids, *not* explicit (no
    choice was offered, mirroring `_select_archetype`'s skip-when-one).
    Otherwise a multi-select with the required entries pre-locked → explicit,
    even when nothing extra is ticked.
    """
    if flag_value is not None:
        return _validate_flag_ids(catalogue, kind, flag_value), True

    available = catalogue.of_kind(kind)
    if not available:
        return (), False

    required = catalogue.required_ids(descriptor.id, kind)
    if all(d.id in set(required) for d in available):
        return required, False

    if yes:
        return (), False

    picked = choose_components(
        COMPONENT_PROMPTS[kind.value],
        available,
        required=required,
        required_by=descriptor.id,
    )
    return picked, True


def _resolve_selection(
    catalogue: Catalogue,
    descriptor: ArchetypeChoice,
    flags: ComponentFlags,
    *,
    archetype_explicit: bool,
    yes: bool,
) -> SelectionRequest:
    """Build the full `SelectionRequest` for the chosen archetype.

    Runs `_resolve_kind` for each selectable kind in tier order and threads
    each kind's own explicitness into `SelectionRequest.of` -- so a kind whose
    ids were selected without a choice being offered stays non-explicit
    (CF-13.03, ADR 0028).
    """
    resolved = {
        kind: _resolve_kind(catalogue, descriptor, kind, flags.for_kind(kind), yes=yes)
        for kind in SELECTABLE_KINDS
    }
    caps, caps_explicit = resolved[SelectionKind.CAPABILITIES]
    platforms, platforms_explicit = resolved[SelectionKind.PLATFORMS]
    return SelectionRequest.of(
        archetype=descriptor.id,
        archetype_explicit=archetype_explicit,
        capabilities=caps,
        platforms=platforms,
        capabilities_explicit=caps_explicit,
        platforms_explicit=platforms_explicit,
    )


def _resolve_engine_selection(
    catalogue: Catalogue,
    archetype: str | None,
    flags: ComponentFlags,
    *,
    yes: bool,
) -> tuple[ArchetypeChoice, SelectionRequest]:
    """Pick the archetype, then resolve capabilities and platforms around it.

    All component selection happens here, before any project answer is
    collected (ADR 0025's ordering, extended by ADR 0028). A cancelled
    multi-select exits `130` with nothing written.
    """
    descriptor, archetype_explicit = _select_archetype(
        catalogue.archetypes, archetype, yes=yes
    )
    try:
        selection = _resolve_selection(
            catalogue, descriptor, flags, archetype_explicit=archetype_explicit, yes=yes
        )
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None
    return descriptor, selection


def _missing_requirement_hint(
    catalogue: Catalogue, descriptor: ArchetypeChoice, selection: SelectionRequest
) -> str:
    """Flag hints for direct requirements the selection still omits.

    The `--yes` half of ADR 0027's asymmetric required-component rule:
    `create-forge` adds nothing, but when the engine is about to reject a
    missing hard requirement, it says which flag supplies it. Empty when the
    selection is complete.
    """
    chosen = {*selection.capabilities, *selection.platforms}
    hints = [
        f"Add {_flag_name(kind)} {req_id}."
        for kind in SELECTABLE_KINDS
        for req_id in catalogue.required_ids(descriptor.id, kind)
        if req_id not in chosen
    ]
    return " ".join(hints)


def _validate_component_option_owners(
    catalogue: Catalogue,
    selection: SelectionRequest,
    options: Mapping[str, Mapping[str, str]],
) -> None:
    """Reject a `--component-option` owner that is unknown or unselected.

    Both checks are answerable from the discovered catalogue and the resolved
    selection alone (ADR 0027), and both exit `1` before any prompt or write.
    An option *name* the owner does not declare, a value outside `choices`, a
    wrong type, a missing `required` one -- all stay engine verdicts.
    """
    selected = {
        component_id
        for kind in DESCRIPTOR_KIND
        for component_id in selection.ids_for(kind)
    }
    for owner in options:
        if catalogue.kind_of(owner) is None:
            available = ", ".join(sorted(d.id for d in catalogue.descriptors))
            _output.err.print(
                f"[red]Unknown --component-option component {owner!r}. "
                f"Available: {available}[/red]"
            )
            raise typer.Exit(1)
        if owner not in selected:
            _output.err.print(
                f"[red]--component-option component {owner!r} is not selected. "
                f"Selected: {', '.join(sorted(selected))}[/red]"
            )
            raise typer.Exit(1)


def _select_archetype(
    archetypes: Sequence[ArchetypeChoice], archetype: str | None, *, yes: bool
) -> tuple[ArchetypeChoice, bool]:
    """Resolve which archetype to build: explicit, --yes, then a prompt.

    CF-08.02. Mirrors `_select_template`'s resolution shape for the Copier
    path, but
    with no config- or registry-supplied default: the engine declares no
    default archetype, and `templates.toml`'s `default_template` is a
    Copier-path concept the engine path deliberately does not inherit.

    Returns the chosen descriptor alongside whether the choice was explicit
    (CF-09.01, ADR 0022): `--archetype` and an actually-prompted answer both
    are; `choose_archetype`'s own skip-when-only-one-exists shortcut is not,
    since no alternative was ever offered and a policy default could
    legitimately still apply there. Returning the descriptor itself, not just
    its id, is what lets the caller prompt for its declared `options` (#91,
    ADR 0025) without a second discovery lookup.
    """
    by_id = {a.id: a for a in archetypes}

    if archetype is not None:
        if archetype not in by_id:
            _output.err.print(
                f"[red]Unknown archetype {archetype!r}. Available: "
                f"{', '.join(sorted(by_id))}[/red]"
            )
            raise typer.Exit(1)
        return by_id[archetype], True

    if yes:
        _output.err.print(
            "[red]--yes requires --archetype. "
            f"Available: {', '.join(sorted(by_id))}[/red]"
        )
        raise typer.Exit(1)

    try:
        chosen = choose_archetype(archetypes)
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None
    # `choose_archetype` itself skips the prompt when there is exactly one
    # archetype (mirroring `choose_template`) -- no alternative was ever
    # offered, so that case is not an explicit choice.
    return chosen, len(archetypes) > 1


def _collect_engine_answers(  # noqa: PLR0913 - project answers plus per-component options need the archetype, the full selected set, both preset sources, config, and the yes switch
    descriptor: ArchetypeChoice,
    selected: Sequence[ArchetypeChoice],
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    option_flags: Mapping[str, Mapping[str, str]],
    *,
    yes: bool,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Gather identity answers and every selected component's declared options.

    Collected from --yes/--data/--component-option, or by prompting (#91,
    ADR 0025; CF-13.04, ADR 0029). Mirrors `_collect_answers`'s shape.

    `preset` (from `--data`) is split by the *archetype's* own declared option
    names: a match is an archetype-option answer (precedence rule 2 -- an
    unqualified `--data` name never targets a capability), everything else is a
    project-identity answer, including keys with no ProjectSpec home at all
    (`github_org`) and the legacy `build_backend`/`versioning` pair
    `pipeline._resolved_component_options` still inspects.

    `option_flags` is the owner-qualified `--component-option` map (rule 1),
    layered over the archetype `--data` presets. `resolve_component_options`
    then walks `selected` in composition-tier order, collecting each declared
    option the namespace did not already supply -- prompting only when not
    `--yes`, and omitting a component whose namespace stays empty.
    """
    archetype_option_names = {option.name for option in descriptor.options}
    archetype_preset = {k: v for k, v in preset.items() if k in archetype_option_names}
    project_preset = {
        k: v for k, v in preset.items() if k not in archetype_option_names
    }

    presets: dict[str, Mapping[str, object]] = {}
    for owner, values in option_flags.items():
        presets[owner] = dict(values)
    if archetype_preset:
        presets[descriptor.id] = {
            **archetype_preset,
            **presets.get(descriptor.id, {}),
        }

    if yes:
        if "project_name" not in project_preset:
            _output.err.print("[red]--yes requires a project name.[/red]")
            raise typer.Exit(1)
        project_answers = {**cfg_answers, **project_preset}
        component_options = resolve_component_options(
            selected, presets=presets, prompt=False
        )
        return project_answers, component_options

    try:
        project_answers = {
            **cfg_answers,
            **ask_project_answers(preset=project_preset, defaults=cfg_answers),
        }
        component_options = resolve_component_options(
            selected, presets=presets, prompt=True
        )
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None

    return project_answers, component_options
