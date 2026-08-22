"""slugify, ask_all's preset/depends_on handling, and choose_template.

All ask_all cases here fully satisfy every applicable prompt via `preset`, so
no test actually drives questionary -- there is nothing left to ask.
"""

from __future__ import annotations

import pytest
import questionary

from create_forge.models import Choice, PromptKind, PromptSpec, Template
from create_forge.prompts import ask_all, choose_template, slugify


def _template(prompts: list[PromptSpec] | None = None, **overrides: object) -> Template:
    defaults: dict[str, object] = {
        "id": "lib",
        "name": "Library",
        "description": "d",
        "url": "https://example.com/repo",
    }
    defaults.update(overrides)
    return Template(prompts=prompts or [], **defaults)  # type: ignore[arg-type]


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("Credit Risk Utils") == "credit-risk-utils"


def test_slugify_strips_leading_and_trailing_punctuation() -> None:
    assert slugify("  --Foo Bar!!--  ") == "foo-bar"


def test_choose_template_skips_the_question_for_a_single_template() -> None:
    only = _template(id="lib")
    assert choose_template([only], "lib") is only


def test_ask_all_does_not_reprompt_a_preset_key() -> None:
    spec = PromptSpec(key="project_name", kind=PromptKind.TEXT, message="Name")
    template = _template(prompts=[spec])
    answers = ask_all(template, preset={"project_name": "Foo"})
    assert answers == {"project_name": "Foo"}


def test_ask_all_skips_a_prompt_whose_depends_on_is_unmet() -> None:
    build_backend = PromptSpec(
        key="build_backend", kind=PromptKind.TEXT, message="Backend"
    )
    versioning = PromptSpec(
        key="versioning",
        kind=PromptKind.SELECT,
        message="Version source",
        choices=[Choice(value="static", label="Static")],
        depends_on={"build_backend": "hatchling"},
    )
    template = _template(prompts=[build_backend, versioning])

    answers = ask_all(template, preset={"build_backend": "uv_build"})

    assert answers == {"build_backend": "uv_build"}
    assert "versioning" not in answers


# --- defaults (from user config): pre-fill, don't suppress -----------------


class _FakeAnswer:
    """Stands in for questionary's `Question`, returning its default as-is."""

    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def _recording_text(seen: dict[str, object], key: str) -> object:
    """A `questionary.text` replacement that records the default it was given
    and answers with it, as if the user had accepted the pre-fill unchanged."""

    def fake_text(
        message: str,
        default: str,
        instruction: str | None,
        validate: object,
        style: object,
    ) -> _FakeAnswer:
        seen[key] = default
        return _FakeAnswer(default)

    return fake_text


def test_defaults_pre_fill_a_text_prompt_without_suppressing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(questionary, "text", _recording_text(seen, "github_org"))

    spec = PromptSpec(key="github_org", kind=PromptKind.TEXT, message="Org")
    template = _template(prompts=[spec])

    answers = ask_all(template, defaults={"github_org": "config-org"})

    assert seen["github_org"] == "config-org"
    assert answers == {"github_org": "config-org"}


def test_preset_still_wins_over_defaults() -> None:
    spec = PromptSpec(key="github_org", kind=PromptKind.TEXT, message="Org")
    template = _template(prompts=[spec])

    answers = ask_all(
        template,
        preset={"github_org": "from-data"},
        defaults={"github_org": "from-config"},
    )

    assert answers == {"github_org": "from-data"}


def test_repo_name_derivation_still_outranks_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(questionary, "text", _recording_text(seen, "repo_name"))

    spec = PromptSpec(key="repo_name", kind=PromptKind.TEXT, message="Repo name")
    template = _template(prompts=[spec])

    answers = ask_all(
        template,
        preset={"project_name": "My Project"},
        defaults={"repo_name": "should-be-ignored"},
    )

    assert seen["repo_name"] == "my-project"
    assert answers["repo_name"] == "my-project"
