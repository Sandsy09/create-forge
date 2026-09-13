"""Real end-to-end `create-forge new` on the default engine path (CF-08.04,
ADR 0020; the default architecture since ADR 0040 / CF-18.01).

`tests/test_e2e_generation.py` proves the `--legacy` Copier path end to end;
this module is its engine-path counterpart, kept separate rather than folded
in because the two paths differ in almost everything but the console script
they invoke:

- the post-rename lifecycle (CF-18.03, ADR 0045) gives a rendered project its
  own `git init` + one initial commit, committing the client-finalised
  `uv.lock` and `.forge/generation.json` alongside the render; `pre-commit
  install --install-hooks` runs only when the render selected the
  `pre-commit` capability. `e2e_child_env` supplies the Git identity this
  needs (`tests/conftest.py`), the same identity the Copier path's own
  `_tasks` already required.
- most of the happy path below needs **no network at all**: `forge-template`
  is a required, installed package (ADR 0040 decision 1), not a cloned
  template, so generating through it is as deterministic as any other
  in-process call. The two negative compatibility tests at the bottom, and
  the lifecycle fixture's `pre-commit install --install-hooks` step (which
  downloads hook environments), are the exceptions -- the negative tests
  skip, rather than fail, when GitHub is unreachable.
- `--archetype` selects which one to build; every archetype this catalogue
  discovers is covered here -- `library` and `cli` (CF-08.03's
  archetype-parity review, ADR 0019) and, since CF-13.05 (ADR 0030), Data
  Science with its `jupyter` and `scientific-python` capabilities. Adding an
  archetype is a one-line change to `_ARCHETYPES` plus, if it has hard
  requirements, an `_EXTRA_ARGS` entry.

Marked `e2e`, sharing `create_forge_command`/`e2e_child_env` with
`test_e2e_generation.py` via `tests/conftest.py`. Skips the whole module,
rather than failing it, when the engine is not importable at all --
`uv run poe test:e2e` should say why, not error.
"""

from __future__ import annotations

import hashlib
import json
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
    reason="forge-template is not importable -- run `uv sync`",
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every archetype the installed catalogue ships. Kept as fixture data feeding
# the real console script, never selection logic -- see this module's
# docstring and `tests/test_archetype_parity.py`'s AST guard.
_ARCHETYPES = ("library", "cli", "data-science")

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
    "data-science": {
        "project_name": "E2E Engine Data Science",
        "project_description": "create-forge engine e2e smoke test (data science).",
        "license": "mit",
        "author_name": "create-forge e2e",
        "author_email": "create-forge-e2e@example.invalid",
    },
}
_PACKAGE_NAMES = {
    "library": "e2e_engine_library",
    "cli": "e2e_engine_cli",
    "data-science": "e2e_engine_data_science",
}
_REPOSITORY_NAMES = {
    "library": "e2e-engine-library",
    "cli": "e2e-engine-cli",
    "data-science": "e2e-engine-data-science",
}
# Hard requirements an archetype needs supplied as `--capability` flags, plus
# the optional capabilities this suite deliberately exercises alongside them.
# Data Science requires `jupyter`; `scientific-python` is independently
# optional and included here so the released project covers both.
_EXTRA_ARGS: dict[str, list[str]] = {
    "data-science": [
        "--capability",
        "jupyter",
        "--capability",
        "scientific-python",
    ],
}
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
    args += _EXTRA_ARGS.get(archetype, [])

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
    """Scaffold every discovered archetype exactly once per session through
    the real engine path; every test below asserts against these real
    projects rather than each paying for its own render.
    """
    projects: dict[str, Path] = {}
    for archetype in _ARCHETYPES:
        dest = (
            tmp_path_factory.mktemp(f"e2e-engine-{archetype}")
            / _REPOSITORY_NAMES[archetype]
        )
        result = _run_engine_new(create_forge_command, e2e_child_env, archetype, dest)
        if result.returncode != 0:
            pytest.fail(
                f"create-forge new --archetype {archetype} "
                f"failed (exit {result.returncode}):\n"
                f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
            )
        projects[archetype] = dest
    return projects


@pytest.mark.parametrize("archetype", _ARCHETYPES)
def test_new_creates_a_real_project(
    generated_engine_projects: dict[str, Path], archetype: str
) -> None:
    assert generated_engine_projects[archetype].is_dir()


@pytest.mark.parametrize("archetype", _ARCHETYPES)
def test_new_produces_the_expected_project_shape(
    generated_engine_projects: dict[str, Path], archetype: str
) -> None:
    project = generated_engine_projects[archetype]
    package = _PACKAGE_NAMES[archetype]

    assert (project / "pyproject.toml").is_file()
    assert (project / f"src/{package}/__init__.py").is_file()
    assert (project / f"src/{package}/py.typed").is_file()
    assert (project / "tests").is_dir()
    assert (project / "uv.lock").is_file()
    assert (project / ".forge" / "generation.json").is_file()
    # The engine path runs no copier.yml _tasks, but does run its own
    # post-rename lifecycle (CF-18.03, ADR 0045): `git init` + one commit.
    # None of these three archetypes select `pre-commit`, so hooks are not
    # installed and no `.venv` is created -- see the dedicated lifecycle
    # fixture below for that combination.
    assert (project / ".git").is_dir()
    assert not (project / ".venv").exists()


@pytest.mark.parametrize("archetype", _ARCHETYPES)
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


@pytest.mark.parametrize("archetype", _ARCHETYPES)
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


@pytest.mark.parametrize("archetype", _ARCHETYPES)
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


# --------------------------------------------------------------------------- #
# CF-18.03 / ADR 0045: the post-rename Git and pre-commit hook lifecycle       #
# --------------------------------------------------------------------------- #

# `_ARCHETYPES`'s three fixtures above select no capability, so none of them
# renders `.pre-commit-config.yaml` -- generated separately, once per session,
# so the hook-installation step (which needs network) is proven somewhere.
_LIFECYCLE_PROJECT_NAME = "E2E Engine Lifecycle"
_LIFECYCLE_PACKAGE_NAME = "e2e_engine_lifecycle"
_LIFECYCLE_REPOSITORY_NAME = "e2e-engine-lifecycle"


def _git(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(project), *args],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture(scope="session")
def generated_lifecycle_project(
    tmp_path_factory: pytest.TempPathFactory,
    create_forge_command: str,
    e2e_child_env: dict[str, str],
) -> Path:
    """A `library` project generated with the `pre-commit` capability
    selected -- the one combination that exercises every step of the
    post-rename lifecycle: `git init`, one initial commit containing
    `uv.lock` and `.forge/generation.json`, and
    `pre-commit install --install-hooks`.
    """
    dest = tmp_path_factory.mktemp("e2e-engine-lifecycle") / _LIFECYCLE_REPOSITORY_NAME
    answers = _ANSWERS["library"]
    args = [
        create_forge_command,
        "new",
        _LIFECYCLE_PROJECT_NAME,
        "--archetype",
        "library",
        "--capability",
        "pre-commit",
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in answers.items():
        if key == "project_name":
            continue
        args += ["--data", f"{key}={value}"]

    result = subprocess.run(  # noqa: S603
        args,
        cwd=dest.parent,
        env=e2e_child_env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "create-forge new --capability pre-commit failed "
            f"(exit {result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return dest


def test_new_lifecycle_finalise_creates_exactly_one_commit(
    generated_lifecycle_project: Path,
) -> None:
    """`git init` + `git add -A` + one initial commit, byte-identical to the
    direct-Copier `_tasks`' own message.
    """
    project = generated_lifecycle_project
    assert (project / ".git").is_dir()

    log = _git(project, "log", "--format=%s")
    assert log.returncode == 0, log.stdout + log.stderr
    assert log.stdout.strip().splitlines() == ["feat: initial scaffold from template"]


def test_new_lifecycle_finalise_commits_the_lock_and_metadata(
    generated_lifecycle_project: Path,
) -> None:
    project = generated_lifecycle_project
    tracked = _git(project, "ls-tree", "-r", "--name-only", "HEAD")
    assert tracked.returncode == 0, tracked.stdout + tracked.stderr
    names = set(tracked.stdout.split())
    assert "uv.lock" in names
    assert ".forge/generation.json" in names


def test_new_lifecycle_finalise_writes_valid_generation_metadata(
    generated_lifecycle_project: Path,
) -> None:
    """The committed document parses, and every recorded digest matches the
    file it describes on disk -- proving `create-forge` persisted the real
    document the engine returned, not a hand-built stand-in.
    """
    project = generated_lifecycle_project
    document = json.loads(
        (project / ".forge" / "generation.json").read_text(encoding="utf-8")
    )
    assert document["metadata_version"] == 1
    assert document["provider"]["distribution"] == "forge-template"

    for record in document["output"]:
        target = project / record["target"]
        assert target.is_file(), f"{record['target']} is recorded but missing"
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        assert record["digest"] == f"sha256:{digest}"


def test_new_lifecycle_installs_pre_commit_hooks(
    generated_lifecycle_project: Path,
) -> None:
    """`pre-commit install --install-hooks` ran because
    `.pre-commit-config.yaml` was rendered -- proven by the installed hook
    shim rather than by running `pre-commit` itself, which would additionally
    require the downloaded hook environments to succeed, not merely exist.
    """
    project = generated_lifecycle_project
    hook = project / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()


def test_new_lifecycle_failure_keeps_the_project_and_warns(
    tmp_path: Path, create_forge_command: str, e2e_child_env: dict[str, str]
) -> None:
    """A `git commit` failure after a good render keeps the project, prints
    the one manual command that finishes the step, and still exits `0` (ADR
    0041 rule 4) -- proven against a real subprocess with no Git identity
    reachable anywhere (env, global config, or system config), not a faked
    lifecycle.
    """
    dest = tmp_path / "proj"
    answers = _ANSWERS["library"]
    args = [
        create_forge_command,
        "new",
        answers["project_name"],
        "--archetype",
        "library",
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in answers.items():
        if key == "project_name":
            continue
        args += ["--data", f"{key}={value}"]

    env = dict(e2e_child_env)
    for key in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        env.pop(key, None)
    # Neither an env identity nor a discoverable global/system gitconfig:
    # point both at paths that do not exist rather than relying on this
    # machine happening to have no `user.name` configured.
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "no-such-gitconfig")
    env["GIT_CONFIG_SYSTEM"] = str(tmp_path / "no-such-gitconfig-system")
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    result = subprocess.run(  # noqa: S603
        args,
        cwd=dest.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "finish it yourself" in normalised
    assert (dest / "pyproject.toml").is_file()
    assert (dest / ".git").is_dir()


def test_new_cleanup_leaves_a_pre_existing_destination_untouched(
    tmp_path: Path, create_forge_command: str, e2e_child_env: dict[str, str]
) -> None:
    """The non-empty-destination check still runs, and still runs first, with
    the heavier post-rename lifecycle wired in: a pre-existing file is never
    touched, and neither the render nor the lifecycle ever starts.
    """
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("keep me", encoding="utf-8")

    answers = _ANSWERS["library"]
    args = [
        create_forge_command,
        "new",
        answers["project_name"],
        "--archetype",
        "library",
        "--capability",
        "pre-commit",
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in answers.items():
        if key == "project_name":
            continue
        args += ["--data", f"{key}={value}"]

    result = subprocess.run(  # noqa: S603
        args,
        cwd=dest.parent,
        env=e2e_child_env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert list(dest.iterdir()) == [dest / "existing.txt"]
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "keep me"


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


def _venv_python(venv: Path) -> Path:
    return venv / (
        "Scripts/python.exe" if (venv / "Scripts").is_dir() else "bin/python"
    )


def _venv_console(venv: Path, name: str) -> Path:
    if (venv / "Scripts").is_dir():
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def test_an_out_of_range_engine_is_rejected_before_any_write(
    _forge_template_reachable: None, tmp_path: Path
) -> None:
    """A released `create-forge` refuses an installed engine outside
    `compat.SUPPORTED_ENGINE_RANGE` at exit status 3 (ADR 0011), with nothing
    written -- against a real, isolated install of a genuinely incompatible
    engine version, not a monkeypatched `EngineInfo`
    (`test_cli.py::test_new_exits_3_on_incompatible_engine` proves the same
    boundary cheaply, in the fast suite).

    Since ADR 0040 (CF-18.01) made the engine a required dependency, a single
    `uv run --with <this checkout> --with <out-of-range pin>` would now
    conflict with the checkout's own declared `>=0.5,<0.6` range and fail the
    resolver outright rather than installing the out-of-range version. A real
    venv plus a second, targeted `--reinstall` step reaches the same broken
    state deliberately instead.
    """
    del _forge_template_reachable
    dest = tmp_path / "proj"
    venv = tmp_path / "venv"

    created = subprocess.run(  # noqa: S603
        ["uv", "venv", "--python", "3.13", str(venv)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert created.returncode == 0, created.stdout + created.stderr

    python_path = _venv_python(venv)
    installed = subprocess.run(  # noqa: S603
        ["uv", "pip", "install", "--python", str(python_path), str(REPO_ROOT)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    forced = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "pip",
            "install",
            "--python",
            str(python_path),
            "--reinstall",
            _OUT_OF_RANGE_ENGINE,
        ],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert forced.returncode == 0, forced.stdout + forced.stderr

    console = _venv_console(venv, "create-forge")
    result = subprocess.run(  # noqa: S603
        [
            str(console),
            "new",
            "Out Of Range",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 3, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "0.3.0" in normalised
    assert compat.SUPPORTED_ENGINE_RANGE in normalised
    assert not dest.exists()


def test_a_broken_install_with_no_engine_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    """ADR 0040 decision 12 (CF-18.01): a broken environment where the
    required engine cannot be imported at all fails closed at exit `3` with
    an actionable message, not a raw `ImportError` traceback -- exercising
    for real what `test_cli.py`'s monkeypatched `builtins.__import__` proves
    cheaply in the fast suite. Needs no network: installing this checkout
    then removing `forge-template` affords no GitHub round trip.
    """
    dest = tmp_path / "proj"
    venv = tmp_path / "venv"

    created = subprocess.run(  # noqa: S603
        ["uv", "venv", "--python", "3.13", str(venv)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert created.returncode == 0, created.stdout + created.stderr

    python_path = _venv_python(venv)
    installed = subprocess.run(  # noqa: S603
        ["uv", "pip", "install", "--python", str(python_path), str(REPO_ROOT)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    removed = subprocess.run(  # noqa: S603
        ["uv", "pip", "uninstall", "--python", str(python_path), "forge-template"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert removed.returncode == 0, removed.stdout + removed.stderr

    console = _venv_console(venv, "create-forge")
    result = subprocess.run(  # noqa: S603
        [
            str(console),
            "new",
            "Engine Absent",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 3, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "forge-template is not installed" in normalised
    assert not dest.exists()
