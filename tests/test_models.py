"""Validator behaviour for the registry's Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from create_forge.models import Choice, PromptKind, PromptSpec, Registry, Template


def _template(**overrides: object) -> Template:
    defaults: dict[str, object] = {
        "id": "lib",
        "name": "Library",
        "description": "d",
        "url": "https://example.com/repo",
    }
    defaults.update(overrides)
    return Template(**defaults)  # type: ignore[arg-type]


# --- PromptSpec ---------------------------------------------------------


def test_select_without_choices_is_rejected() -> None:
    with pytest.raises(ValidationError, match="declares no choices"):
        PromptSpec(key="foo", kind=PromptKind.SELECT, message="Foo")


def test_non_select_with_choices_is_rejected() -> None:
    with pytest.raises(ValidationError, match="declares choices but is not a select"):
        PromptSpec(
            key="foo",
            kind=PromptKind.TEXT,
            message="Foo",
            choices=[Choice(value="a", label="A")],
        )


def test_select_with_choices_is_accepted() -> None:
    spec = PromptSpec(
        key="foo",
        kind=PromptKind.SELECT,
        message="Foo",
        choices=[Choice(value="a", label="A")],
    )
    assert spec.choices[0].value == "a"


def test_should_ask_is_true_with_no_depends_on() -> None:
    spec = PromptSpec(key="foo", kind=PromptKind.TEXT, message="Foo")
    assert spec.should_ask({}) is True


def test_should_ask_respects_depends_on() -> None:
    spec = PromptSpec(
        key="versioning",
        kind=PromptKind.SELECT,
        message="Version source",
        choices=[Choice(value="static", label="Static")],
        depends_on={"build_backend": "hatchling"},
    )
    assert spec.should_ask({"build_backend": "hatchling"}) is True
    assert spec.should_ask({"build_backend": "uv_build"}) is False
    assert spec.should_ask({}) is False


# --- Template ------------------------------------------------------------


def test_deprecated_without_successor_is_rejected() -> None:
    with pytest.raises(ValidationError, match="deprecated but names no successor"):
        _template(status="deprecated")


def test_deprecated_with_successor_is_accepted() -> None:
    template = _template(status="deprecated", deprecated_in_favour_of="lib2")
    assert template.deprecated_in_favour_of == "lib2"


def test_duplicate_prompt_keys_are_rejected() -> None:
    dup = PromptSpec(key="a", kind=PromptKind.TEXT, message="A")
    with pytest.raises(ValidationError, match="duplicate prompt keys"):
        _template(prompts=[dup, dup])


# --- Registry --------------------------------------------------------------


def test_default_template_must_exist() -> None:
    with pytest.raises(ValidationError, match="not in the registry"):
        Registry(default_template="missing", templates=[_template()])


def test_default_template_cannot_be_deprecated() -> None:
    template = _template(status="deprecated", deprecated_in_favour_of="lib2")
    with pytest.raises(ValidationError, match="is deprecated"):
        Registry(default_template="lib", templates=[template])


def test_duplicate_template_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate template ids"):
        Registry(
            default_template="lib",
            templates=[_template(id="lib"), _template(id="lib")],
        )


def test_get_returns_the_matching_template() -> None:
    template = _template(id="lib")
    registry = Registry(default_template="lib", templates=[template])
    assert registry.get("lib") is template


def test_get_unknown_id_lists_available_ids() -> None:
    registry = Registry(default_template="lib", templates=[_template(id="lib")])
    with pytest.raises(KeyError, match="Available: lib"):
        registry.get("missing")


def test_selectable_excludes_deprecated_templates() -> None:
    stable = _template(id="lib")
    deprecated = _template(id="old", status="deprecated", deprecated_in_favour_of="lib")
    registry = Registry(default_template="lib", templates=[stable, deprecated])
    assert registry.selectable == [stable]
