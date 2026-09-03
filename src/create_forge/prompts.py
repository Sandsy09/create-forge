"""Interactive prompt flow.

Two independent prompt sets live here. The Copier path is driven entirely by
the registry, so surfacing a new question there is a data change rather than
a code change — anything not prompted falls through to the template's own
default in copier.yml. The engine path (`--engine-preview`, #91,
ADR 0025) is driven by ProjectSpec's own required identity fields
(`PROJECT_PROMPTS`) plus the selected archetype's own discovered
`ComponentDescriptor.options` (`ask_component_options`) — it reads no
registry data at all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

import questionary
from questionary import Choice as QChoice

from create_forge.models import Choice, PromptKind, PromptSpec

if TYPE_CHECKING:
    from create_forge.models import Template


class ComponentOptionSpec(Protocol):
    """The engine's `ComponentOption` shape this module actually needs.

    Structural, not imported: `prompts.py` is one of the shipped modules
    `tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
    guards, so it may not import `forge_template` even under
    `TYPE_CHECKING`. `ComponentOption` satisfies this without either module
    knowing about the other. Read-only properties, not plain attributes:
    `ComponentOption`'s fields are frozen, and a read-write Protocol
    attribute would reject it as non-conforming. `type`/`default`/`choices`
    are widened from the engine's own `Literal[...]`/`JsonValue` to
    `str`/`object`/`Sequence[object]` — a read-only property is covariant, so
    the engine's narrower types still conform.
    """

    @property
    def name(self) -> str:
        """The option's identifier within its component's namespace."""
        ...

    @property
    def type(self) -> str:
        """One of `string`, `integer`, `boolean`, `string_list`."""
        ...

    @property
    def required(self) -> bool:
        """Whether the component rejects generation without this option."""
        ...

    @property
    def default(self) -> object:
        """The value applied when the option is left unanswered."""
        ...

    @property
    def choices(self) -> Sequence[object]:
        """A closed set of acceptable values, or empty for an open one."""
        ...

    @property
    def description(self) -> str:
        """The one-line explanation shown as the prompt message."""
        ...

    @property
    def format(self) -> str | None:
        """An additional shape constraint (e.g. `pep440`), or `None`."""
        ...


class ArchetypeChoice(Protocol):
    """The engine's `ComponentDescriptor` shape this module actually needs.

    Named for its first use (archetype selection, CF-08.02) but it describes
    any component descriptor: `choose_components` renders capability and
    platform descriptors through the same Protocol. Structural, not imported:
    see `ComponentOptionSpec` above for why. `ComponentDescriptor` satisfies
    this without either module knowing about the other. Read-only properties,
    not plain attributes: `ComponentDescriptor`'s fields are frozen, and a
    read-write Protocol attribute would reject it as non-conforming.
    """

    @property
    def id(self) -> str:
        """The canonical component identifier."""
        ...

    @property
    def name(self) -> str:
        """The display name shown in the prompt."""
        ...

    @property
    def description(self) -> str:
        """The one-line description shown alongside the name."""
        ...

    @property
    def options(self) -> Sequence[ComponentOptionSpec]:
        """This component's own declared, directly-promptable options."""
        ...


_SLUG_RE = re.compile(r"[^a-z0-9]+")

_STYLE = questionary.Style(
    [
        ("qmark", "fg:#5f819d bold"),
        ("question", "bold"),
        ("answer", "fg:#85678f"),
        ("pointer", "fg:#5f819d bold"),
        ("highlighted", "fg:#5f819d bold"),
        ("selected", "fg:#5f819d"),
        ("instruction", "fg:#888888"),
    ]
)


class PromptAbortedError(Exception):
    """The user pressed Ctrl-C or Ctrl-D."""


def slugify(value: str) -> str:
    """Turn a project name into a repository-safe slug."""
    return _SLUG_RE.sub("-", value.lower()).strip("-")


def choose_template(templates: list[Template], default_id: str) -> Template:
    """Ask which archetype to scaffold. Skipped when only one is selectable."""
    if len(templates) == 1:
        return templates[0]

    choices = [
        QChoice(
            title=f"{t.name}  —  {t.description}"
            + ("  [preview]" if t.status == "preview" else ""),
            value=t,
        )
        for t in templates
    ]
    default = next(
        (c for c in choices if c.value is not None and c.value.id == default_id),
        None,
    )

    answer: Template | None = questionary.select(
        "What are you building?",
        choices=choices,
        default=default,
        style=_STYLE,
    ).ask()

    if answer is None:
        raise PromptAbortedError
    return answer


def choose_archetype(archetypes: Sequence[ArchetypeChoice]) -> ArchetypeChoice:
    """Ask which engine archetype to build. Skipped when only one exists.

    Mirrors `choose_template`'s shape for the engine-preview path (CF-08.02):
    same skip-when-one behaviour, same `PromptAbortedError` on cancel.
    `archetypes` is expected to be non-empty -- callers resolve an empty
    catalogue as a compatibility failure before reaching here.
    """
    if len(archetypes) == 1:
        return archetypes[0]

    choices = [
        QChoice(title=f"{a.name}  —  {a.description}", value=a) for a in archetypes
    ]

    answer: ArchetypeChoice | None = questionary.select(
        "What are you building?",
        choices=choices,
        style=_STYLE,
    ).ask()

    if answer is None:
        raise PromptAbortedError
    return answer


COMPONENT_PROMPTS: dict[str, str] = {
    "capabilities": "Which capabilities?",
    "platforms": "Which platforms?",
}
"""The multi-select prompt message for each selectable component kind
(`--engine-preview`, CF-13.03). Keyed by `spec.SelectionKind`'s value string,
not the enum -- `prompts.py` cannot import `spec` (`spec` imports
`prompts.slugify`).
"""

_COMPONENT_INSTRUCTION = "space to toggle, enter to confirm"


def choose_components(
    prompt: str,
    descriptors: Sequence[ArchetypeChoice],
    *,
    required: Sequence[str] = (),
    required_by: str,
) -> tuple[str, ...]:
    """Multi-select over `descriptors`, returning the chosen component ids.

    A `required` id renders pre-checked and locked, annotated
    `(required by <required_by>)`, and is re-added to the result after the
    prompt returns: `questionary`'s checkbox lets its select-all key clear a
    `disabled` entry, so `disabled=` is display only, not enforcement
    (CF-13.03, [ADR 0028](adr/0028-discovery-driven-component-selection.md)).
    The returned ids keep `descriptors`' own (discovery) order.

    An empty result is a legitimate answer -- an explicit "no capabilities".
    Cancelling (Ctrl-C / Ctrl-D) raises `PromptAbortedError`. Callers skip
    this entirely when there is nothing to choose (every descriptor required,
    or none discovered) -- see `cli._resolve_selection`.
    """
    required_set = set(required)
    choices = [
        QChoice(
            title=f"{d.name}  —  {d.description}",
            value=d.id,
            checked=d.id in required_set,
            disabled=f"required by {required_by}" if d.id in required_set else None,
        )
        for d in descriptors
    ]

    picked: list[str] | None = questionary.checkbox(
        prompt,
        choices=choices,
        instruction=_COMPONENT_INSTRUCTION,
        style=_STYLE,
    ).ask()

    if picked is None:
        raise PromptAbortedError

    chosen = required_set | set(picked)
    return tuple(d.id for d in descriptors if d.id in chosen)


def ask_all(
    template: Template,
    *,
    preset: dict[str, object] | None = None,
    defaults: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run every applicable Copier-path prompt, returning the collected answers.

    `preset` holds values supplied on the command line. Preset keys are not
    re-asked, which is what makes `--data` usable alongside interactive mode.

    `defaults` (e.g. from user config) pre-fills a prompt's answer without
    suppressing it -- unlike `preset`, the question is still asked.
    """
    return _ask_prompts(template.prompts, preset=preset, defaults=defaults)


PROJECT_PROMPTS: tuple[PromptSpec, ...] = (
    PromptSpec(
        key="project_name",
        kind=PromptKind.TEXT,
        message="Project name",
        help="Human readable, e.g. 'Credit Risk Utils'",
    ),
    PromptSpec(
        key="project_description",
        kind=PromptKind.TEXT,
        message="Short description",
    ),
    PromptSpec(
        key="license",
        kind=PromptKind.SELECT,
        message="License",
        choices=[
            Choice(value="proprietary", label="Proprietary", hint="internal use only"),
            Choice(value="mit", label="MIT"),
            Choice(value="apache-2.0", label="Apache-2.0"),
        ],
    ),
)
"""The `--engine-preview` path's own prompt set (#91, ADR 0025).

These are exactly the CLI-collected answers that reach `ProjectSpec.project`
(see `spec._project_metadata`) -- `python_min_version`/`python_version`/
`author_name`/`author_email` are deliberately excluded: they already resolve
from config, `--data`, or `spec.DEFAULT_PYTHON_*` without ever being asked
interactively today, and prompting them is a scope increase #91 does not ask
for. Independent of `templates.toml`: the engine path reads no registry data
at all.
"""


def ask_project_answers(
    *,
    preset: dict[str, object] | None = None,
    defaults: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run `PROJECT_PROMPTS`, returning the collected answers.

    Mirrors `ask_all`'s preset/defaults contract exactly, over the engine
    path's own fixed prompt set instead of a `Template`'s registry-declared
    one.
    """
    return _ask_prompts(PROJECT_PROMPTS, preset=preset, defaults=defaults)


def _ask_prompts(
    prompts: Sequence[PromptSpec],
    *,
    preset: dict[str, object] | None,
    defaults: dict[str, object] | None,
) -> dict[str, object]:
    """Shared core behind `ask_all` and `ask_project_answers`."""
    answers: dict[str, object] = dict(preset or {})

    for spec in prompts:
        if spec.key in answers:
            continue
        if not spec.should_ask(answers):
            continue

        value = _ask_one(spec, answers, defaults or {})
        if value is None:
            raise PromptAbortedError
        answers[spec.key] = value

    return answers


def ask_component_options(
    descriptor: ArchetypeChoice, *, preset: dict[str, object] | None = None
) -> dict[str, object]:
    """Prompt for `descriptor.options` directly, returning real-typed answers.

    Renders each `ComponentOptionSpec` natively rather than coercing it
    through `PromptSpec` -- `Choice.value`/`PromptSpec.default` are
    `str | bool`, which would be lossy for `integer`/`string_list` options.
    Returns `{}` immediately for a descriptor with no declared options
    (`cli`'s today) -- that empty return is itself #91's first acceptance
    criterion: no Library-specific question is ever reached for an archetype
    that declares none.

    A `preset` key with the option's own name suppresses that prompt, mirror-
    ing `ask_all`'s preset semantics -- an explicit `--data packaging_mode=...`
    is honoured without being re-asked.
    """
    answers: dict[str, object] = {}
    preset = preset or {}

    for option in descriptor.options:
        if option.name in preset:
            answers[option.name] = preset[option.name]
            continue

        value = _ask_component_option(option)
        if value is None:
            raise PromptAbortedError
        answers[option.name] = value

    return answers


def _ask_component_option(option: ComponentOptionSpec) -> object | None:
    """Render a single declared component option."""
    if option.type == "boolean":
        confirmed: bool | None = questionary.confirm(
            option.description,
            default=bool(option.default),
            style=_STYLE,
        ).ask()
        return confirmed

    if option.type == "string" and option.choices:
        choices = [QChoice(title=str(c), value=c) for c in option.choices]
        chosen_default = next(
            (c for c in choices if c.value == option.default), choices[0]
        )
        selected: object | None = questionary.select(
            option.description,
            choices=choices,
            default=chosen_default,
            style=_STYLE,
        ).ask()
        return selected

    if option.type == "integer":
        raw_int: str | None = questionary.text(
            option.description,
            default=str(option.default) if option.default is not None else "",
            instruction=_format_hint(option),
            validate=_integer_validator,
            style=_STYLE,
        ).ask()
        return None if raw_int is None else int(raw_int)

    if option.type == "string_list":
        default_items = (
            option.default
            if isinstance(option.default, Sequence)
            and not isinstance(option.default, str)
            else ()
        )
        hint = _format_hint(option)
        raw_list: str | None = questionary.text(
            option.description,
            default=", ".join(str(v) for v in default_items),
            instruction=f"comma-separated; {hint}" if hint else "comma-separated",
            style=_STYLE,
        ).ask()
        if raw_list is None:
            return None
        return [item.strip() for item in raw_list.split(",") if item.strip()]

    # "string" without choices: a free-form value, e.g. a pep440 version.
    raw_text: str | None = questionary.text(
        option.description,
        default=str(option.default) if option.default is not None else "",
        instruction=_format_hint(option),
        style=_STYLE,
    ).ask()
    return raw_text


def _format_hint(option: ComponentOptionSpec) -> str | None:
    """The `format` constraint shown as a prompt instruction, if any.

    Presentation only -- validating `format` (e.g. `pep440`) stays the
    engine's job, matching `docs/cli-conventions.md`'s validation-ownership
    rule that create-forge never reproduces a semantic-validation predicate.
    """
    return option.format


def _integer_validator(text: str) -> bool | str:
    """Reject non-integer input for an `integer`-typed component option."""
    try:
        int(text)
    except ValueError:
        return "Enter a whole number"
    return True


def _ask_one(
    spec: PromptSpec, answers: dict[str, object], defaults: dict[str, object]
) -> object | None:
    """Render a single prompt."""
    default = _resolve_default(spec, answers, defaults)

    match spec.kind:
        case PromptKind.CONFIRM:
            confirmed: bool | None = questionary.confirm(
                spec.message,
                default=bool(default),
                style=_STYLE,
            ).ask()
            return confirmed

        case PromptKind.SELECT:
            choices = [
                QChoice(
                    title=c.label + (f"  ({c.hint})" if c.hint else ""),
                    value=c.value,
                )
                for c in spec.choices
            ]
            chosen_default = next(
                (c for c in choices if c.value == default), choices[0]
            )
            selected: str | None = questionary.select(
                spec.message,
                choices=choices,
                default=chosen_default,
                instruction=spec.help,
                style=_STYLE,
            ).ask()
            return selected

        case _:
            text: str | None = questionary.text(
                spec.message,
                default=str(default or ""),
                instruction=spec.help,
                validate=_required_if(spec),
                style=_STYLE,
            ).ask()
            return text


def _resolve_default(
    spec: PromptSpec, answers: dict[str, object], defaults: dict[str, object]
) -> object | None:
    """Derive a default from earlier answers, then config, then the template."""
    if spec.key == "repo_name" and "project_name" in answers:
        return slugify(str(answers["project_name"]))
    if spec.key in defaults:
        return defaults[spec.key]
    return spec.default


def _required_if(spec: PromptSpec) -> object:
    """Reject empty input for keys the template cannot default."""
    if spec.key != "project_name":
        return lambda _: True

    def _validate(text: str) -> bool | str:
        if not text.strip():
            return "Project name is required"
        if not slugify(text):
            return "Project name must contain letters or digits"
        return True

    return _validate
