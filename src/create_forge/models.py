"""Registry data models.

The registry is bundled with the package, so adding a template means cutting a
new CLI release. That is a deliberate MVP trade-off: no network call on start,
no partial-failure states, and the registry is validated at build time by the
test suite rather than at runtime by the user.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class PromptKind(StrEnum):
    """How a prompt is rendered."""

    TEXT = "text"
    SELECT = "select"
    CONFIRM = "confirm"


class Choice(BaseModel):
    """One option in a select prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: str
    label: str
    hint: str | None = None


class PromptSpec(BaseModel):
    """A question the CLI asks on behalf of a template.

    This is UX metadata only. The authoritative declaration of every variable —
    including its type, default and validation — lives in the template's own
    `copier.yml`. Anything not listed here is left to the template default.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    """Must match a question key in the template's copier.yml."""

    kind: PromptKind
    message: str
    help: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    default: str | bool | None = None
    depends_on: dict[str, str] = Field(default_factory=dict)
    """Only ask when these previously-answered keys hold these values."""

    @model_validator(mode="after")
    def _choices_match_kind(self) -> Self:
        if self.kind is PromptKind.SELECT and not self.choices:
            msg = f"prompt {self.key!r} is a select but declares no choices"
            raise ValueError(msg)
        if self.kind is not PromptKind.SELECT and self.choices:
            msg = f"prompt {self.key!r} declares choices but is not a select"
            raise ValueError(msg)
        return self

    def should_ask(self, answers: dict[str, object]) -> bool:
        """Whether this prompt applies given what has been answered so far."""
        return all(
            str(answers.get(key)) == expected
            for key, expected in self.depends_on.items()
        )


class Template(BaseModel):
    """One archetype available to scaffold."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    name: str
    description: str
    url: HttpUrl
    status: Literal["stable", "preview", "deprecated"] = "stable"
    deprecated_in_favour_of: str | None = None
    prompts: list[PromptSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _deprecation_has_successor(self) -> Self:
        if self.status == "deprecated" and not self.deprecated_in_favour_of:
            msg = f"template {self.id!r} is deprecated but names no successor"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _prompt_keys_unique(self) -> Self:
        keys = [p.key for p in self.prompts]
        if len(keys) != len(set(keys)):
            msg = f"template {self.id!r} has duplicate prompt keys"
            raise ValueError(msg)
        return self


class Registry(BaseModel):
    """The full set of templates this CLI release knows about."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    default_template: str
    templates: list[Template]

    @model_validator(mode="after")
    def _default_exists_and_is_usable(self) -> Self:
        match = next((t for t in self.templates if t.id == self.default_template), None)
        if match is None:
            msg = f"default_template {self.default_template!r} is not in the registry"
            raise ValueError(msg)
        if match.status == "deprecated":
            msg = f"default_template {self.default_template!r} is deprecated"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _ids_unique(self) -> Self:
        ids = [t.id for t in self.templates]
        if len(ids) != len(set(ids)):
            msg = "duplicate template ids in registry"
            raise ValueError(msg)
        return self

    def get(self, template_id: str) -> Template:
        """Look up a template, raising a useful error when absent."""
        for template in self.templates:
            if template.id == template_id:
                return template
        available = ", ".join(sorted(t.id for t in self.templates))
        msg = f"unknown template {template_id!r}. Available: {available}"
        raise KeyError(msg)

    @property
    def selectable(self) -> list[Template]:
        """Templates offered interactively (deprecated ones stay addressable)."""
        return [t for t in self.templates if t.status != "deprecated"]
