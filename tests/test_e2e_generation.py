"""Real end-to-end `create-forge new`, generated project and all (CF-07.06).

Every other test module proves this CLI resolves the right `ScaffoldRequest`
or stages/finalises the right bytes; none of them ever run the actual
`create-forge` console script users get from `uvx create-forge`, or check the
project it produces. This module does, against `forge-template`'s latest
released tag -- see docs/end-to-end-tests.md.

Marked `e2e`, never `network`: this is dramatically slower than
`test_drift.py`/`test_update_network.py` (it clones the template, runs its
`_tasks` -- `uv sync --all-groups`, `pre-commit install --install-hooks` --
then the generated project's own `uv run poe check`), so it must stay
separable from the drift guard's CI job. Like the other network-touching
suites, it skips rather than fails when GitHub is unreachable.

The `--engine-preview` path is deliberately out of scope here: it is a
materially different generation path (no `copier.yml` `_tasks`, a different
answer set, archetype selection). See
[`tests/test_e2e_engine_generation.py`](test_e2e_engine_generation.py)
(CF-08.04, ADR 0020) for its own end-to-end coverage; the two modules share
subprocess helpers via `tests/conftest.py`'s `create_forge_command` and
`e2e_child_env` fixtures.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from create_forge.registry import load_registry

pytestmark = pytest.mark.e2e

_ANSWERS = {
    "project_name": "E2E Smoke Test",
    "project_description": "create-forge end-to-end smoke test.",
    "github_org": "test-org",
    "license": "mit",
    "author_name": "create-forge e2e",
    "author_email": "create-forge-e2e@example.invalid",
}
_PACKAGE_NAME = "e2e_smoke_test"


def _run_new(
    command: str,
    env: dict[str, str],
    dest: Path,
    *,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        command,
        "new",
        _ANSWERS["project_name"],
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in _ANSWERS.items():
        if key == "project_name":
            continue
        args += ["--data", f"{key}={value}"]
    args += extra_args or []

    return subprocess.run(  # noqa: S603
        args,
        cwd=dest.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


@pytest.fixture(scope="session")
def _template_reachable() -> None:
    """Skip the whole module, not fail it, when GitHub is unreachable --
    same reasoning as test_drift.py and test_update_network.py.
    """
    load_registry.cache_clear()
    registry = load_registry()
    url = str(registry.get(registry.default_template).url)
    try:
        subprocess.run(  # noqa: S603
            ["git", "ls-remote", "--tags", "--refs", url],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not reach {url}: {exc}")


@pytest.fixture(scope="session")
def generated_project(
    _template_reachable: None,
    tmp_path_factory: pytest.TempPathFactory,
    create_forge_command: str,
    e2e_child_env: dict[str, str],
) -> Path:
    """Scaffold exactly once per test session; every test below asserts
    against this one real project rather than each paying for its own clone
    and `_tasks` run.
    """
    del _template_reachable
    dest = tmp_path_factory.mktemp("e2e") / "e2e-smoke-test"

    result = _run_new(create_forge_command, e2e_child_env, dest)
    if result.returncode != 0:
        pytest.fail(
            f"create-forge new failed (exit {result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return dest


def test_new_creates_a_real_project(generated_project: Path) -> None:
    assert generated_project.is_dir()


def test_new_produces_the_expected_project_shape(generated_project: Path) -> None:
    assert (generated_project / "pyproject.toml").is_file()
    assert (generated_project / f"src/{_PACKAGE_NAME}/__init__.py").is_file()
    assert (generated_project / "tests").is_dir()
    assert (generated_project / ".copier-answers.yml").is_file()
    # Both baked in by copier.yml's _tasks -- proof the post-generation
    # commands actually ran, not just Copier's own file rendering.
    assert (generated_project / ".git").is_dir()
    assert (generated_project / "uv.lock").is_file()


def test_new_records_the_answers_it_was_given(generated_project: Path) -> None:
    """Invariant 1 (CLAUDE.md) checked from the user's side: `test_drift.py`
    proves every registry key exists in copier.yml; this proves the values
    survive the real round trip through Copier rather than silently falling
    back to the template's own default.
    """
    answers = yaml.safe_load(
        (generated_project / ".copier-answers.yml").read_text(encoding="utf-8")
    )
    assert answers["project_name"] == _ANSWERS["project_name"]
    assert answers["project_description"] == _ANSWERS["project_description"]
    assert answers["github_org"] == _ANSWERS["github_org"]
    assert answers["license"] == _ANSWERS["license"]
    assert answers["author_name"] == _ANSWERS["author_name"]
    assert answers["author_email"] == _ANSWERS["author_email"]
    # `_commit` records the resolved tag `--ref`-less `new` gives real users.
    assert answers["_commit"]


def test_generated_project_passes_its_own_check(generated_project: Path) -> None:
    """The template's own canonical gate -- ruff format/check, mypy, pytest
    -- against exactly what a real user would run next, straight from the
    success panel's own advice (`cd <project> && uv run poe check`).
    """
    result = subprocess.run(
        ["uv", "run", "poe", "check"],  # noqa: S607
        cwd=generated_project,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, (
        f"generated project's `poe check` failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_new_rejects_a_non_empty_destination(
    _template_reachable: None,
    tmp_path: Path,
    create_forge_command: str,
    e2e_child_env: dict[str, str],
) -> None:
    """No clone is attempted -- `staging.ensure_available` (ADR 0015) fails
    before Copier is even reached, so this costs nothing beyond the
    reachability probe already paid for by the session fixture above.
    """
    del _template_reachable
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    result = _run_new(create_forge_command, e2e_child_env, dest)

    assert result.returncode == 1, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "already exists and is not empty" in normalised
    assert list(dest.iterdir()) == [dest / "existing.txt"]
