"""Shared pytest configuration for contributor-only test options and fixtures
shared across the `e2e`-marked suites.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.encoding_lanes import report_header_line
from tests.installed_client import (
    ENGINE_VERSION,
    InstalledClient,
    build_candidate_wheel,
    build_client,
    supplied_candidate_wheel,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def pytest_report_header() -> str:
    """State the interpreter's own text-encoding mode in every job's log
    (CF-23.02): what `main()`, `git`, and `uv` are decoded/decoding under is
    exactly what the non-UTF-8 lanes in `tests/encoding_lanes.py` exist to
    stop assuming and start measuring -- so it belongs in the log header
    every run prints, not only in the tests that check it.
    """
    return report_header_line()


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


@pytest.fixture(scope="session")
def candidate_wheel(e2e_child_env: dict[str, str]) -> Iterator[Path]:
    """Build the create-forge candidate wheel exactly once per session.

    Shared by every `e2e`-marked suite that installs the release candidate
    rather than resolving the editable console script: CF-14.02's installed
    Data Science validation and CF-14.03's installed rollout regression matrix
    (ADR 0032, ADR 0033).

    `CREATE_FORGE_CANDIDATE_WHEEL=<path>` supplies an already-built wheel
    instead -- the one PyPI serves after a release -- so the same suites can
    test the published artefact (CF-21.03, ADR 0056). Unset, nothing changes.
    """
    supplied = supplied_candidate_wheel(os.environ)
    if supplied is not None:
        yield supplied
        return
    with tempfile.TemporaryDirectory(prefix="create-forge-candidate-wheel-") as tmp:
        yield build_candidate_wheel(Path(tmp), e2e_child_env)


@pytest.fixture(scope="session")
def installed_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel installed with the reviewed
    `forge-template 0.6.0` engine release in one isolated virtual environment.

    `forge-template` is a required dependency since ADR 0040 (CF-18.01) --
    there is no more `[engine]` extra to opt into; `engine=` pins the exact
    reviewed release alongside the wheel's own declared range. `extras=
    "[legacy]"` also installs `copier`, since several rollout regressions
    (`tests/test_e2e_installed_rollout.py`) exercise `--legacy` against this
    same environment alongside the now-default engine path.
    """
    with build_client(
        candidate_wheel,
        e2e_child_env,
        extras="[legacy]",
        engine=f"forge-template=={ENGINE_VERSION}",
    ) as client:
        yield client
