"""copier.yml drift guard -- the direct test for CLAUDE.md invariant 1.

Copier silently drops `data` keys with no matching question in the target
template's copier.yml: no error, the answer vanishes, the template default
applies. A registry prompt whose key has drifted from copier.yml therefore
fails silently, producing a scaffold that looks fine and is subtly wrong.
This is exactly how the `task_runner` prompt shipped -- see
docs/plan-v0.1.0.md for the incident this test suite exists to prevent.

Clones the template with `git` directly, never through runner.py: invariant 4
in CLAUDE.md reserves Copier's Python API for that module, and a clone is not
a Copier operation.
"""

from __future__ import annotations

import re
import subprocess
from typing import Any

import pytest
import yaml

from create_forge.models import Choice, PromptKind, PromptSpec
from create_forge.registry import load_registry

pytestmark = pytest.mark.network

_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_SIMPLE_WHEN_RE = re.compile(r"^\{\{\s*(\w+)\s*==\s*'([^']*)'\s*\}\}$")


def _version_key(tag: str) -> tuple[int, int, int]:
    match = _TAG_RE.match(tag)
    if not match:
        msg = f"not a vX.Y.Z tag: {tag!r}"
        raise ValueError(msg)
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _latest_tag(url: str) -> str | None:
    """The tag `vcs_ref=None` actually resolves to for users."""
    result = subprocess.run(  # noqa: S603
        ["git", "ls-remote", "--tags", "--refs", url],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    tags = [
        line.rsplit("refs/tags/", 1)[-1] for line in result.stdout.splitlines() if line
    ]
    versioned = [t for t in tags if _TAG_RE.match(t)]
    if not versioned:
        return None
    return max(versioned, key=_version_key)


def _questions(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Non-underscore top-level keys -- the actual questions."""
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def _is_computed(question: dict[str, Any]) -> bool:
    """`when: false` (the YAML boolean) hides a question.

    `when` as a Jinja *string* is a real condition, not a hidden/computed
    value -- `versioning` and `initial_version` both use that form. Never use
    truthiness here, or those two get misclassified as computed.
    """
    return question.get("when") is False


def _choice_values(question: dict[str, Any]) -> set[str] | None:
    """copier.yml's `choices` is a label->value mapping for most select
    questions, but a plain list (value == label) for the python_* pickers."""
    choices = question.get("choices")
    if isinstance(choices, dict):
        return set(choices.values())
    if isinstance(choices, list):
        return set(choices)
    return None


@pytest.fixture(scope="session")
def copier_yml(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Clone the library template at its latest tag and parse copier.yml.

    Network-dependent: skips rather than fails when the template is
    unreachable, so a connectivity problem is never mistaken for a genuine
    registry drift -- both would otherwise show up as the same red X.
    """
    load_registry.cache_clear()
    registry = load_registry()
    url = str(registry.get(registry.default_template).url)

    try:
        tag = _latest_tag(url)
        if tag is None:
            pytest.skip(f"{url} has no version tags yet")

        dst = tmp_path_factory.mktemp("forge-template") / "repo"
        subprocess.run(  # noqa: S603
            [  # noqa: S607
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                tag,
                url,
                str(dst),
            ],
            check=True,
            timeout=60,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not reach {url}: {exc}")

    with (dst / "copier.yml").open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data


def test_every_registry_key_exists_in_copier_yml(
    copier_yml: dict[str, Any],
) -> None:
    """The direct guard: this is the check that would have caught task_runner."""
    registry = load_registry()
    questions = _questions(copier_yml)

    errors = [
        f"{spec.key!r} (template {template.id!r}) has no matching question "
        "in forge-template's copier.yml"
        for template in registry.templates
        for spec in template.prompts
        if spec.key not in questions
    ]
    assert not errors, "\n".join(errors)


def test_no_registry_prompt_targets_a_computed_question(
    copier_yml: dict[str, Any],
) -> None:
    registry = load_registry()
    questions = _questions(copier_yml)

    errors = [
        f"{spec.key!r} (template {template.id!r}) is computed (when: false) "
        "in copier.yml -- the CLI cannot ask it"
        for template in registry.templates
        for spec in template.prompts
        if spec.key in questions and _is_computed(questions[spec.key])
    ]
    assert not errors, "\n".join(errors)


def test_unasked_questions_all_have_a_default(copier_yml: dict[str, Any]) -> None:
    """runner.py passes defaults=True, so anything the CLI doesn't ask must
    fall back safely to copier.yml's own default, or be computed."""
    registry = load_registry()
    questions = _questions(copier_yml)
    asked = {spec.key for template in registry.templates for spec in template.prompts}

    errors = [
        f"{key!r} is asked by no template and has no default in copier.yml"
        for key, question in questions.items()
        if key not in asked and not _is_computed(question) and "default" not in question
    ]
    assert not errors, "\n".join(errors)


def test_select_prompt_choices_match_copier_yml(copier_yml: dict[str, Any]) -> None:
    registry = load_registry()
    questions = _questions(copier_yml)

    errors = []
    for template in registry.templates:
        for spec in template.prompts:
            if spec.kind is not PromptKind.SELECT:
                continue
            question = questions.get(spec.key)
            if question is None:
                continue  # already reported by the key-existence test
            expected = _choice_values(question)
            if expected is None:
                errors.append(f"{spec.key!r} has no choices in copier.yml")
                continue
            actual = {c.value for c in spec.choices}
            if actual != expected:
                errors.append(
                    f"{spec.key!r} choice values {sorted(actual)} do not "
                    f"match copier.yml's {sorted(expected)}"
                )
    assert not errors, "\n".join(errors)


def test_depends_on_mirrors_simple_when_expressions(
    copier_yml: dict[str, Any],
) -> None:
    """Only checks the simple `{{ x == 'y' }}` form -- anything more complex
    is left unchecked rather than hand-rolling a Jinja parser."""
    registry = load_registry()
    questions = _questions(copier_yml)

    errors = []
    for template in registry.templates:
        for spec in template.prompts:
            if not spec.depends_on:
                continue
            question = questions.get(spec.key)
            if question is None:
                continue
            when = question.get("when")
            if not isinstance(when, str):
                continue
            match = _SIMPLE_WHEN_RE.match(when.strip())
            if not match:
                continue
            dep_key, dep_value = match.group(1), match.group(2)
            if spec.depends_on.get(dep_key) != dep_value:
                errors.append(
                    f"{spec.key!r} depends_on {spec.depends_on} does not "
                    f"match copier.yml's when: {when!r}"
                )
    assert not errors, "\n".join(errors)


# --- proves the guard actually fires ----------------------------------
#
# forge-template's own standing rule: "a check which cannot fail is not a
# check." These are cheaper than manually re-adding task_runner to
# templates.toml and reverting it, and they run every time.


def test_a_bogus_key_would_be_detected(copier_yml: dict[str, Any]) -> None:
    spec = PromptSpec(key="not_a_real_question", kind=PromptKind.TEXT, message="?")
    assert spec.key not in _questions(copier_yml)


def test_a_choice_value_typo_would_be_detected(copier_yml: dict[str, Any]) -> None:
    spec = PromptSpec(
        key="license",
        kind=PromptKind.SELECT,
        message="License",
        choices=[Choice(value="mit-typo", label="MIT")],
    )
    expected = _choice_values(_questions(copier_yml)["license"])
    actual = {c.value for c in spec.choices}
    assert actual != expected
