"""Interactive prompt flow.

Prompts are driven entirely by the registry, so surfacing a new question is a
data change rather than a code change. Anything not prompted here falls through
to the template's own default in copier.yml.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import questionary
from questionary import Choice as QChoice

if TYPE_CHECKING:
    from create_forge.models import PromptSpec, Template

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


class PromptAborted(Exception):
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
    default = next((c for c in choices if c.value.id == default_id), None)

    answer = questionary.select(
        "What are you building?",
        choices=choices,
        default=default,
        style=_STYLE,
    ).ask()

    if answer is None:
        raise PromptAborted
    return answer


def ask_all(
    template: Template,
    *,
    preset: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run every applicable prompt, returning the collected answers.

    `preset` holds values supplied on the command line. Preset keys are not
    re-asked, which is what makes `--data` usable alongside interactive mode.
    """
    answers: dict[str, object] = dict(preset or {})

    for spec in template.prompts:
        if spec.key in answers:
            continue
        if not spec.should_ask(answers):
            continue

        value = _ask_one(spec, answers)
        if value is None:
            raise PromptAborted
        answers[spec.key] = value

    return answers


def _ask_one(spec: PromptSpec, answers: dict[str, object]) -> object | None:
    """Render a single prompt."""
    default = _resolve_default(spec, answers)

    match spec.kind:
        case "confirm":
            return questionary.confirm(
                spec.message,
                default=bool(spec.default),
                style=_STYLE,
            ).ask()

        case "select":
            choices = [
                QChoice(
                    title=c.label + (f"  ({c.hint})" if c.hint else ""),
                    value=c.value,
                )
                for c in spec.choices
            ]
            chosen_default = next(
                (c for c in choices if c.value == spec.default), choices[0]
            )
            return questionary.select(
                spec.message,
                choices=choices,
                default=chosen_default,
                instruction=spec.help,
                style=_STYLE,
            ).ask()

        case _:
            return questionary.text(
                spec.message,
                default=str(default or ""),
                instruction=spec.help,
                validate=_required_if(spec),
                style=_STYLE,
            ).ask()


def _resolve_default(spec: PromptSpec, answers: dict[str, object]) -> object | None:
    """Derive a default from earlier answers where it saves typing."""
    if spec.key == "repo_name" and "project_name" in answers:
        return slugify(str(answers["project_name"]))
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