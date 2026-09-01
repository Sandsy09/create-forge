"""Real end-to-end `create-forge new --engine-preview` (CF-08.04, ADR 0020).

`tests/test_e2e_generation.py` proves the default Copier path end to end;
this module is its engine-path counterpart, kept separate rather than folded
in because the two paths differ in almost everything but the console script
they invoke:

- no `copier.yml` `_tasks` run here -- a rendered project has no `.git`,
  `.venv`, or `pre-commit` hooks installed. Client finalisation creates
  `uv.lock`; `uv run --locked poe check` restores and checks from that lock.
- the happy path below needs **no network at all**: `forge-template` is an
  installed package (the optional `engine` extra, ADR 0018), not a cloned
  template, so generating through it is as deterministic as any other
  in-process call. Only the two negative tests at the bottom, which install a
  *different* engine version to prove a compatibility boundary, touch GitHub
  -- and they skip, rather than fail, when it is unreachable.
- `--engine-preview` selects an archetype (`library` or `cli`); both are
  covered here, matching CF-08.03's archetype-parity review (ADR 0019).

Marked `e2e`, sharing `create_forge_command`/`e2e_child_env` with
`test_e2e_generation.py` via `tests/conftest.py`. Skips the whole module,
rather than failing it, when the `engine` extra is not installed at all --
`uv run poe test:e2e` after a plain `uv sync` should say why, not error.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from create_forge import compat

pytestmark = pytest.mark.e2e

pytest.importorskip(
    "forge_template",
    reason="the optional 'engine' extra isn't installed -- run `uv sync --all-extras`",
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_ANSWERS: dict[str, dict[str, str]] = {
    "library": {
        "project_name": "E2E Engine Library",
        "project_description": "create-forge engine end-to-end smoke test (library).",
        "license": "mit",
        "author_name": "create-forge e2e",
        "author_email": "create-forge-e2e@example.invalid",
    },
    "cli": {
        "project_name": "E2E Engine Cli",
        "project_description": "create-forge engine end-to-end smoke test (cli).",
        "license": "mit",
        "author_name": "create-forge e2e",
        "author_email": "create-forge-e2e@example.invalid",
    },
}
_PACKAGE_NAMES = {"library": "e2e_engine_library", "cli": "e2e_engine_cli"}
_REPOSITORY_NAMES = {"library": "e2e-engine-library", "cli": "e2e-engine-cli"}
_FORGE_DISTRIBUTIONS = {
    canonicalize_name("create-forge"),
    canonicalize_name("forge-template"),
}

# A real forge-template release, genuinely below compat.SUPPORTED_ENGINE_RANGE's
# declared lower bound -- this installs the previous git tag directly as a
# durable test fixture. A range that only ever moves up (ADR 0012) keeps
# 0.3.0 permanently out of bounds, so this needs no maintenance as the
# supported range advances -- see ADR 0020 for why this does not weaken
# ADR 0018's PyPI-only *declared* dependency.
_OUT_OF_RANGE_ENGINE = (
    "forge-template @ git+https://github.com/Sandsy09/forge-template@v0.3.0"
)


def _run_engine_new(
    command: str, env: dict[str, str], archetype: str, dest: Path
) -> subprocess.CompletedProcess[str]:
    answers = _ANSWERS[archetype]
    args = [
        command,
        "new",
        answers["project_name"],
        "--engine-preview",
        "--archetype",
        archetype,
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in answers.items():
        if key == "project_name":
            continue
        args += ["--data", f"{key}={value}"]

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
def generated_engine_projects(
    tmp_path_factory: pytest.TempPathFactory,
    create_forge_command: str,
    e2e_child_env: dict[str, str],
) -> dict[str, Path]:
    """Scaffold both archetypes exactly once per session through the real
    engine path; every test below asserts against these two real projects
    rather than each paying for its own render.
    """
    projects: dict[str, Path] = {}
    for archetype in ("library", "cli"):
        dest = (
            tmp_path_factory.mktemp(f"e2e-engine-{archetype}")
            / _REPOSITORY_NAMES[archetype]
        )
        result = _run_engine_new(create_forge_command, e2e_child_env, archetype, dest)
        if result.returncode != 0:
            pytest.fail(
                f"create-forge new --engine-preview --archetype {archetype} "
                f"failed (exit {result.returncode}):\n"
                f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
            )
        projects[archetype] = dest
    return projects


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_new_creates_a_real_project(
    generated_engine_projects: dict[str, Path], archetype: str
) -> None:
    assert generated_engine_projects[archetype].is_dir()


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_new_produces_the_expected_project_shape(
    generated_engine_projects: dict[str, Path], archetype: str
) -> None:
    project = generated_engine_projects[archetype]
    package = _PACKAGE_NAMES[archetype]

    assert (project / "pyproject.toml").is_file()
    assert (project / f"src/{package}/__init__.py").is_file()
    assert (project / f"src/{package}/py.typed").is_file()
    assert (project / "tests").is_dir()
    # The engine path runs no copier.yml _tasks: create-forge adds only the
    # client-finalised lockfile before the atomic rename (ADR 0021).
    assert not (project / ".git").exists()
    assert not (project / ".venv").exists()
    assert (project / "uv.lock").is_file()


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_generated_lockfile_is_current(
    generated_engine_projects: dict[str, Path],
    archetype: str,
    e2e_child_env: dict[str, str],
) -> None:
    project = generated_engine_projects[archetype]
    result = subprocess.run(
        ["uv", "lock", "--check"],  # noqa: S607
        cwd=project,
        env=e2e_child_env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_generated_project_has_no_forge_dependency(
    generated_engine_projects: dict[str, Path], archetype: str
) -> None:
    """ADR 0024: Forge generates projects; it is not their framework.

    Inspect every dependency-bearing project table and the fully resolved
    lock. This covers build, normal runtime, optional, development, and test
    dependencies without treating a harmless provenance mention as a package
    dependency.
    """
    project = generated_engine_projects[archetype]
    pyproject: dict[str, Any] = tomllib.loads(
        (project / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements: list[str] = []
    requirements.extend(pyproject.get("build-system", {}).get("requires", []))
    requirements.extend(pyproject.get("project", {}).get("dependencies", []))
    for extra in pyproject.get("project", {}).get("optional-dependencies", {}).values():
        requirements.extend(item for item in extra if isinstance(item, str))
    for group in pyproject.get("dependency-groups", {}).values():
        requirements.extend(item for item in group if isinstance(item, str))

    declared = {
        canonicalize_name(Requirement(requirement).name) for requirement in requirements
    }
    locked = {
        canonicalize_name(package["name"])
        for package in tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))[
            "package"
        ]
    }

    assert declared.isdisjoint(_FORGE_DISTRIBUTIONS)
    assert locked.isdisjoint(_FORGE_DISTRIBUTIONS)


def test_cli_console_command_is_the_repository_name(
    generated_engine_projects: dict[str, Path],
) -> None:
    """End-to-end counterpart to
    `tests/test_archetype_parity.py::test_cli_console_command_is_exactly_the_repository_name`
    (CF-08.03, ADR 0019) -- proven here against a real rendered file rather
    than an in-memory payload.
    """
    pyproject = (generated_engine_projects["cli"] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    repository_name = _REPOSITORY_NAMES["cli"]
    package = _PACKAGE_NAMES["cli"]

    assert f'{repository_name} = "{package}.cli:app"' in pyproject


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_generated_project_passes_its_own_check(
    generated_engine_projects: dict[str, Path],
    archetype: str,
    e2e_child_env: dict[str, str],
) -> None:
    """The engine-generated project's own canonical gate -- ruff format/check,
    mypy, pytest -- the engine-path counterpart to
    `test_e2e_generation.py::test_generated_project_passes_its_own_check`,
    against exactly what a real user would run next. Uses `e2e_child_env` so
    this child `uv` builds the generated project's own environment rather
    than inheriting this repository's.
    """
    project = generated_engine_projects[archetype]

    result = subprocess.run(
        ["uv", "run", "--locked", "poe", "check"],  # noqa: S607
        cwd=project,
        env=e2e_child_env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, (
        f"{archetype}'s generated project `poe check` failed:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


@pytest.fixture(scope="session")
def _forge_template_reachable() -> None:
    """Skip the two negative tests below, not fail them, when GitHub is
    unreachable -- same reasoning as `test_e2e_generation.py`'s equivalent
    fixture. The happy-path fixture above needs no such guard: the engine is
    an installed package, not a cloned template.
    """
    try:
        subprocess.run(
            [  # noqa: S607
                "git",
                "ls-remote",
                "--tags",
                "--refs",
                "https://github.com/Sandsy09/forge-template",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not reach forge-template on GitHub: {exc}")


def test_an_out_of_range_engine_is_rejected_before_any_write(
    _forge_template_reachable: None, tmp_path: Path
) -> None:
    """A released `create-forge` refuses an installed engine outside
    `compat.SUPPORTED_ENGINE_RANGE` at exit status 3 (ADR 0011), with nothing
    written -- against a real, isolated install of a genuinely incompatible
    engine version, not a monkeypatched `EngineInfo`
    (`test_cli.py::test_new_engine_preview_exits_3_on_incompatible_engine`
    proves the same boundary cheaply, in the fast suite).
    """
    del _forge_template_reachable
    dest = tmp_path / "proj"

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "--no-project",
            "--isolated",
            "--with",
            str(REPO_ROOT),
            "--with",
            _OUT_OF_RANGE_ENGINE,
            "create-forge",
            "new",
            "Out Of Range",
            "--engine-preview",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )

    assert result.returncode == 3, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "0.3.0" in normalised
    assert compat.SUPPORTED_ENGINE_RANGE in normalised
    assert not dest.exists()


def test_a_missing_engine_extra_is_rejected_before_any_write(
    _forge_template_reachable: None, tmp_path: Path
) -> None:
    """The other released-install boundary: `create-forge` alone, with no
    `engine` extra resolved at all, refuses `--engine-preview` at exit 1 with
    an actionable message rather than a raw `ImportError` -- exercising for
    real what `test_cli.py`'s monkeypatched `builtins.__import__` proves
    cheaply in the fast suite.
    """
    del _forge_template_reachable
    dest = tmp_path / "proj"

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "--no-project",
            "--isolated",
            "--with",
            str(REPO_ROOT),
            "create-forge",
            "new",
            "Engine Absent",
            "--engine-preview",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "engine extra isn't installed" in normalised
    assert not dest.exists()
