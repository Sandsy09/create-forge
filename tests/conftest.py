"""Shared pytest configuration for contributor-only test options and fixtures
shared across the `e2e`-marked suites.
"""

from __future__ import annotations

import os
import shutil

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the local forge-template checkout used by drift tests."""
    parser.addoption(
        "--forge-template-root",
        metavar="PATH",
        help=(
            "Read copier.yml from a local forge-template checkout instead of "
            "cloning its latest release tag."
        ),
    )


@pytest.fixture(scope="session")
def create_forge_command() -> str:
    """Resolve the real console script -- not `python -m create_forge`, and
    not Typer's `CliRunner`. Both would skip the `[project.scripts]` entry
    point users actually invoke. Shared by every `e2e`-marked module that
    drives the real binary: `tests/test_e2e_generation.py` (Copier path) and
    `tests/test_e2e_engine_generation.py` (engine path).
    """
    found = shutil.which("create-forge")
    if found is None:  # pragma: no cover - packaging bug, not a test failure mode
        pytest.fail(
            "the 'create-forge' console script is not on PATH -- "
            "run this suite via `uv run pytest`, which installs it"
        )
    return found


@pytest.fixture(scope="session")
def e2e_child_env() -> dict[str, str]:
    """The subprocess environment for a real `create-forge` invocation.

    Both e2e paths spawn a child `uv` of their own -- the Copier path's
    `copier.yml` `_tasks` run `uv sync --all-groups` and `git commit` inside
    the generated project; the engine path's tests run the generated
    project's own `uv run poe check` directly. Two things must hold for that
    child `uv` to target the generated project rather than this repository's
    own environment: `VIRTUAL_ENV`, `UV_PROJECT_ENVIRONMENT`, `PYTHONHOME`,
    and `PYTHONPATH` -- all set by `uv run` for *this* pytest process -- must
    not leak into the child. And `git commit` (the Copier path only) needs an
    identity CI does not have, which a plain `env=` argument supplies for the
    whole subprocess tree with no plumbum-snapshot caveat (contrast
    `tests/test_update_network.py`'s `_git_identity_for_template_tasks`
    fixture, needed only because that test calls `scaffold()` in-process).
    """
    env = dict(os.environ)
    for leak in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONHOME", "PYTHONPATH"):
        env.pop(leak, None)
    env.update(
        {
            "GIT_AUTHOR_NAME": "create-forge e2e",
            "GIT_AUTHOR_EMAIL": "create-forge-e2e@example.invalid",
            "GIT_COMMITTER_NAME": "create-forge e2e",
            "GIT_COMMITTER_EMAIL": "create-forge-e2e@example.invalid",
        }
    )
    return env
