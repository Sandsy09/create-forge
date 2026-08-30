"""Interactive prompt flow.

Prompts are driven entirely by the registry, so surfacing a new question is a
data change rather than a code change. Anything not prompted here falls through
to the template's own default in copier.yml.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

import questionary
from questionary import Choice as QChoice

from create_forge.models import PromptKind

if TYPE_CHECKING:
    from collections.abc import Sequence

    from create_forge.models import PromptSpec, Template


class ArchetypeChoice(Protocol):
    """The engine's `ComponentDescriptor` shape this module actually needs.

    Structural, not imported: `prompts.py` is one of the shipped modules
    `tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
    guards, so it may not import `forge_template` even under
    `TYPE_CHECKING`. `ComponentDescriptor` satisfies this without either
    module knowing about the other (CF-08.02). Read-only properties, not
    plain attributes: `ComponentDescriptor`'s fields are frozen, and a
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


def ask_all(
    template: Template,
    *,
    preset: dict[str, object] | None = None,
    defaults: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run every applicable prompt, returning the collected answers.

    `preset` holds values supplied on the command line. Preset keys are not
    re-asked, which is what makes `--data` usable alongside interactive mode.

    `defaults` (e.g. from user config) pre-fills a prompt's answer without
    suppressing it -- unlike `preset`, the question is still asked.
    """
    answers: dict[str, object] = dict(preset or {})

    for spec in template.prompts:
        if spec.key in answers:
            continue
        if not spec.should_ask(answers):
            continue

        value = _ask_one(spec, answers, defaults or {})
        if value is None:
            raise PromptAbortedError
        answers[spec.key] = value

    return answers


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
