"""slugify, ask_all's preset/depends_on handling, choose_template,
choose_archetype, ask_project_answers, and ask_component_options.

All ask_all/ask_project_answers cases here fully satisfy every applicable
prompt via `preset`, so no test actually drives questionary -- there is
nothing left to ask, except where noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import questionary

from create_forge.models import Choice, PromptKind, PromptSpec, Template
from create_forge.prompts import (
    PromptAbortedError,
    ask_all,
    ask_component_options,
    ask_project_answers,
    choose_archetype,
    choose_template,
    coerce_option_value,
    resolve_component_options,
    slugify,
)


@dataclass(frozen=True)
class _ComponentOption:
    """A minimal stand-in satisfying `ComponentOptionSpec` structurally --
    `forge_template.ComponentOption` itself is out of reach here, same
    reasoning as `ComponentOptionSpec`'s own docstring (#91, ADR 0025).
    """

    name: str
    type: str
    required: bool = False
    default: object = None
    choices: tuple[object, ...] = ()
    description: str = ""
    format: str | None = None


@dataclass(frozen=True)
class _Archetype:
    """A minimal stand-in satisfying `ArchetypeChoice` structurally --
    `ComponentDescriptor` itself is out of reach here, same reasoning as the
    Protocol's own docstring (CF-08.02).
    """

    id: str
    name: str
    description: str
    options: tuple[_ComponentOption, ...] = field(default_factory=tuple)


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


def test_choose_archetype_skips_the_question_for_a_single_archetype() -> None:
    only = _Archetype(id="cli", name="CLI Application", description="d")
    assert choose_archetype([only]) is only


def test_choose_archetype_returns_the_selected_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _Archetype(id="library", name="Library", description="A package.")
    cli = _Archetype(id="cli", name="CLI Application", description="An app.")
    monkeypatch.setattr(questionary, "select", lambda *_a, **_kw: _FakeAnswer(cli))

    assert choose_archetype([library, cli]) is cli


def test_choose_archetype_raises_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _Archetype(id="library", name="Library", description="A package.")
    cli = _Archetype(id="cli", name="CLI Application", description="An app.")
    monkeypatch.setattr(questionary, "select", lambda *_a, **_kw: _FakeAnswer(None))

    with pytest.raises(PromptAbortedError):
        choose_archetype([library, cli])


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


# --- ask_project_answers (#91, ADR 0025) ------------------------------------


def test_ask_project_answers_does_not_reprompt_a_preset_key() -> None:
    answers = ask_project_answers(
        preset={"project_name": "Foo", "project_description": "d", "license": "mit"}
    )
    assert answers == {
        "project_name": "Foo",
        "project_description": "d",
        "license": "mit",
    }


def test_ask_project_answers_defaults_pre_fill_without_suppressing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        questionary, "text", _recording_text(seen, "project_description")
    )
    monkeypatch.setattr(questionary, "select", lambda *_a, **_kw: _FakeAnswer("mit"))

    answers = ask_project_answers(
        preset={"project_name": "Foo"},
        defaults={"project_description": "from config"},
    )

    assert seen["project_description"] == "from config"
    assert answers["project_description"] == "from config"
    assert answers["license"] == "mit"


def test_ask_project_answers_raises_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "text", lambda *_a, **_kw: _FakeAnswer(None))

    with pytest.raises(PromptAbortedError):
        ask_project_answers(preset={"project_name": "Foo"})


# --- ask_component_options (#91, ADR 0025) ----------------------------------


def _forbid_prompting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any questionary function is invoked."""

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("must not prompt")

    monkeypatch.setattr(questionary, "text", fail)
    monkeypatch.setattr(questionary, "select", fail)
    monkeypatch.setattr(questionary, "confirm", fail)


def test_ask_component_options_returns_empty_for_an_optionless_descriptor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`cli`'s real descriptor declares no options -- #91's first acceptance
    criterion, made a unit test: nothing is ever prompted for it.
    """
    _forbid_prompting(monkeypatch)
    archetype = _Archetype(id="cli", name="CLI Application", description="d")

    assert ask_component_options(archetype) == {}


def test_ask_component_options_preset_suppresses_a_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forbid_prompting(monkeypatch)
    option = _ComponentOption(
        name="packaging_mode",
        type="string",
        default="uv-build-static",
        choices=("uv-build-static", "hatchling-static", "hatchling-vcs"),
        description="How the package is built and versioned.",
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(
        archetype, preset={"packaging_mode": "hatchling-vcs"}
    )

    assert answers == {"packaging_mode": "hatchling-vcs"}


def test_ask_component_options_string_choice_returns_the_selected_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        questionary, "select", lambda *_a, **_kw: _FakeAnswer("hatchling-vcs")
    )
    option = _ComponentOption(
        name="packaging_mode",
        type="string",
        default="uv-build-static",
        choices=("uv-build-static", "hatchling-static", "hatchling-vcs"),
        description="How the package is built and versioned.",
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(archetype)

    assert answers == {"packaging_mode": "hatchling-vcs"}


def test_ask_component_options_free_form_string_returns_the_typed_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "text", lambda *_a, **_kw: _FakeAnswer("1.2.3"))
    option = _ComponentOption(
        name="initial_version",
        type="string",
        default="0.1.0",
        description="Initial package version.",
        format="pep440",
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(archetype)

    assert answers == {"initial_version": "1.2.3"}


def test_ask_component_options_boolean_renders_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "confirm", lambda *_a, **_kw: _FakeAnswer(True))
    option = _ComponentOption(
        name="include_docs", type="boolean", default=False, description="Include docs?"
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(archetype)

    assert answers == {"include_docs": True}


def test_ask_component_options_integer_returns_an_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "text", lambda *_a, **_kw: _FakeAnswer("42"))
    option = _ComponentOption(
        name="retries", type="integer", default=3, description="Retry count"
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(archetype)

    assert answers == {"retries": 42}


def test_ask_component_options_string_list_splits_on_commas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "text", lambda *_a, **_kw: _FakeAnswer("a, b ,c"))
    option = _ComponentOption(
        name="tags", type="string_list", default=(), description="Tags"
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    answers = ask_component_options(archetype)

    assert answers == {"tags": ["a", "b", "c"]}


def test_ask_component_options_raises_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(questionary, "confirm", lambda *_a, **_kw: _FakeAnswer(None))
    option = _ComponentOption(
        name="include_docs", type="boolean", description="Include docs?"
    )
    archetype = _Archetype(
        id="library", name="Library", description="d", options=(option,)
    )

    with pytest.raises(PromptAbortedError):
        ask_component_options(archetype)


# --- coerce_option_value (CF-13.04, ADR 0029) ------------------------------


@pytest.mark.parametrize(
    ("option_type", "raw", "expected"),
    [
        ("string", "hatchling-vcs", "hatchling-vcs"),
        ("boolean", "true", True),
        ("boolean", "FALSE", False),
        ("integer", "42", 42),
        ("string_list", "a, b ,c", ["a", "b", "c"]),
        ("string_list", "", []),
    ],
)
def test_coerce_option_value_converts_a_cli_string_to_its_declared_type(
    option_type: str, raw: str, expected: object
) -> None:
    option = _ComponentOption(name="x", type=option_type)
    assert coerce_option_value(option, raw) == expected


def test_coerce_option_value_passes_an_unconvertible_string_through() -> None:
    """A value the engine will reject is left verbatim so *it* produces the
    authoritative `does not match its declared type` message.
    """
    option = _ComponentOption(name="x", type="integer")
    assert coerce_option_value(option, "not-a-number") == "not-a-number"


def test_coerce_option_value_leaves_a_non_string_untouched() -> None:
    """A `--data` bool is already typed -- coercion must not re-parse it."""
    option = _ComponentOption(name="x", type="boolean")
    assert coerce_option_value(option, value=True) is True


# --- resolve_component_options (CF-13.04, ADR 0029) ------------------------


def test_resolve_component_options_walks_descriptors_and_owner_namespaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each descriptor's options land under its own id; a preset value whose
    option the descriptor declares is coerced; a declared option the preset
    omits is prompted.
    """
    monkeypatch.setattr(questionary, "text", lambda *_a, **_kw: _FakeAnswer("7"))
    archetype = _Archetype(
        id="arch",
        name="Arch",
        description="d",
        options=(_ComponentOption(name="retries", type="integer", default=3),),
    )
    capability = _Archetype(
        id="cap",
        name="Cap",
        description="d",
        options=(_ComponentOption(name="mode", type="string"),),
    )

    resolved = resolve_component_options(
        [archetype, capability], presets={"cap": {"mode": "fast"}}
    )

    assert resolved == {"arch": {"retries": 7}, "cap": {"mode": "fast"}}


def test_resolve_component_options_omits_an_empty_namespace() -> None:
    """A selected optionless component produces no key at all -- not `{}`."""
    optionless = _Archetype(id="cli", name="CLI", description="d")

    assert resolve_component_options([optionless], prompt=False) == {}


def test_resolve_component_options_keeps_an_undeclared_preset_key_verbatim() -> None:
    """An unknown option name is the engine's rejection to make, so the
    client forwards it rather than dropping it.
    """
    archetype = _Archetype(
        id="arch",
        name="Arch",
        description="d",
        options=(_ComponentOption(name="known", type="string"),),
    )

    resolved = resolve_component_options(
        [archetype],
        presets={"arch": {"known": "a", "mystery": "b"}},
        prompt=False,
    )

    assert resolved == {"arch": {"known": "a", "mystery": "b"}}
