"""Installed-candidate rollout regression and failure matrix (CF-14.03).

CF-14.02 validated the Data Science compositions through the release-candidate
console script. This module covers everything that issue deliberately left to
CF-14.03: the Library and CLI Application engine paths, the default Copier
path, the no-engine command surface, the compatibility boundary, and the full
selection / option / destination / lock / cleanup failure matrix -- all through
the same freshly built `create_forge-0.3.0` wheel, not the editable
development console the `tests/test_e2e_*` suites otherwise resolve.

Three environments are built from the one `candidate_wheel`:

* `installed_client` (conftest) -- `wheel[engine]` + `forge-template 0.4.1`;
  the engine-path regressions and the failure matrix.
* `engineless_client` -- `wheel` alone; the default Copier path and the
  commands that must work with no engine installed (CLAUDE.md invariant 5).
* `out_of_range_client` -- `wheel` + a real `forge-template 0.3.2` from PyPI,
  genuinely below `SUPPORTED_ENGINE_RANGE`; the exit-3 boundary.

See ADR 0033 and `docs/rollout-regression-validation.md`. The archetype and
component ids here are fixture data feeding the real installed engine, never
selection logic -- `tests/test_archetype_parity.py`'s AST guard owns that rule
for the shipped modules.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from create_forge.compat import SUPPORTED_ENGINE_RANGE
from tests.installed_client import (
    CLIENT_VERSION,
    FORGE_DISTRIBUTIONS,
    InstalledClient,
    assert_output_matches_owned_plan,
    assert_success,
    build_client,
    run,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# fixture data -- feeds the real installed console, never selection logic
# --------------------------------------------------------------------------

_ENGINE_ARCHETYPES = ("library", "cli")
_ENGINE_ANSWERS: dict[str, dict[str, str]] = {
    "library": {
        "project_name": "Rollout Engine Library",
        "project_description": "create-forge installed rollout regression (library).",
        "license": "mit",
        "author_name": "create-forge e2e",
        "author_email": "create-forge-e2e@example.invalid",
    },
    "cli": {
        "project_name": "Rollout Engine Cli",
        "project_description": "create-forge installed rollout regression (cli).",
        "license": "mit",
        "author_name": "create-forge e2e",
        "author_email": "create-forge-e2e@example.invalid",
    },
}
_ENGINE_PACKAGE_NAMES = {
    "library": "rollout_engine_library",
    "cli": "rollout_engine_cli",
}
_ENGINE_REPOSITORY_NAMES = {
    "library": "rollout-engine-library",
    "cli": "rollout-engine-cli",
}

_COPIER_ANSWERS = {
    "project_name": "Rollout Copier Smoke",
    "project_description": "create-forge installed rollout regression (copier).",
    "github_org": "test-org",
    "license": "mit",
    "author_name": "create-forge e2e",
    "author_email": "create-forge-e2e@example.invalid",
}
_COPIER_PACKAGE_NAME = "rollout_copier_smoke"

_OUT_OF_RANGE_ENGINE = "forge-template==0.3.2"
_FORGE_DISTRIBUTIONS = FORGE_DISTRIBUTIONS


# --------------------------------------------------------------------------
# environments
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def engineless_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel installed with no `engine` extra -- the shape a
    plain `pip install create-forge` produces.
    """
    with build_client(candidate_wheel, e2e_child_env) as client:
        yield client


@pytest.fixture(scope="session")
def out_of_range_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel with a real `forge-template` release below the
    supported range resolved alongside it.
    """
    with build_client(
        candidate_wheel, e2e_child_env, engine=_OUT_OF_RANGE_ENGINE
    ) as client:
        yield client


@pytest.fixture(scope="session")
def _forge_template_reachable() -> None:
    """Skip, not fail, the Copier-path tests when GitHub is unreachable --
    the same contract `tests/test_e2e_generation.py` keeps.
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


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _engine_new_args(archetype: str, dest: Path) -> list[str]:
    answers = _ENGINE_ANSWERS[archetype]
    args = [
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
        if key != "project_name":
            args += ["--data", f"{key}={value}"]
    return args


def _staging_siblings(dest: Path) -> list[Path]:
    parent = dest.parent
    if not parent.is_dir():
        return []
    return [p for p in parent.iterdir() if p.name.startswith(".create-forge-")]


def _declared_and_locked(project: Path) -> tuple[set[Any], set[Any]]:
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
    return declared, locked


# --------------------------------------------------------------------------
# engine-path regression: Library and CLI Application from the wheel
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def installed_engine_projects(installed_client: InstalledClient) -> dict[str, Path]:
    """Generate every regression archetype once per session through the
    installed engine console.
    """
    projects: dict[str, Path] = {}
    for archetype in _ENGINE_ARCHETYPES:
        dest = (
            installed_client.root
            / "engine-projects"
            / _ENGINE_REPOSITORY_NAMES[archetype]
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = run(
            [str(installed_client.console), *_engine_new_args(archetype, dest)],
            dest.parent,
            env=installed_client.env,
        )
        assert_success(result, f"installed engine generation of {archetype}")
        projects[archetype] = dest
    return projects


@pytest.mark.parametrize("archetype", _ENGINE_ARCHETYPES)
def test_installed_engine_archetype_has_the_expected_shape(
    installed_engine_projects: dict[str, Path], archetype: str
) -> None:
    project = installed_engine_projects[archetype]
    package = _ENGINE_PACKAGE_NAMES[archetype]

    assert (project / "pyproject.toml").is_file()
    assert (project / f"src/{package}/__init__.py").is_file()
    assert (project / f"src/{package}/py.typed").is_file()
    assert (project / "tests").is_dir()
    assert (project / "uv.lock").is_file()
    # The engine path runs no copier.yml _tasks -- only the client-finalised
    # lock before the atomic rename (ADR 0021).
    assert not (project / ".git").exists()
    assert not (project / ".venv").exists()
    assert _staging_siblings(project) == []


@pytest.mark.parametrize("archetype", _ENGINE_ARCHETYPES)
def test_installed_engine_archetype_lock_is_current(
    installed_client: InstalledClient,
    installed_engine_projects: dict[str, Path],
    archetype: str,
) -> None:
    result = run(
        [str(installed_client.uv), "lock", "--check"],
        installed_engine_projects[archetype],
        env=installed_client.env,
    )
    assert_success(result, f"{archetype} uv lock --check")


@pytest.mark.parametrize("archetype", _ENGINE_ARCHETYPES)
def test_installed_engine_archetype_output_matches_the_owned_plan(
    installed_client: InstalledClient,
    installed_engine_projects: dict[str, Path],
    archetype: str,
) -> None:
    assert_output_matches_owned_plan(
        installed_client,
        installed_engine_projects[archetype],
        archetype=archetype,
        capabilities=(),
        answers=_ENGINE_ANSWERS[archetype],
    )


@pytest.mark.parametrize("archetype", _ENGINE_ARCHETYPES)
def test_installed_engine_archetype_has_no_forge_dependency(
    installed_engine_projects: dict[str, Path], archetype: str
) -> None:
    declared, locked = _declared_and_locked(installed_engine_projects[archetype])
    assert declared.isdisjoint(_FORGE_DISTRIBUTIONS)
    assert locked.isdisjoint(_FORGE_DISTRIBUTIONS)


def test_installed_cli_console_command_is_the_repository_name(
    installed_engine_projects: dict[str, Path],
) -> None:
    pyproject = (installed_engine_projects["cli"] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    repository_name = _ENGINE_REPOSITORY_NAMES["cli"]
    package = _ENGINE_PACKAGE_NAMES["cli"]
    assert f'{repository_name} = "{package}.cli:app"' in pyproject


@pytest.mark.parametrize("archetype", _ENGINE_ARCHETYPES)
def test_installed_engine_archetype_passes_its_own_check(
    installed_client: InstalledClient,
    installed_engine_projects: dict[str, Path],
    archetype: str,
) -> None:
    result = run(
        [str(installed_client.uv), "run", "--locked", "poe", "check"],
        installed_engine_projects[archetype],
        env=installed_client.env,
    )
    assert_success(result, f"{archetype} generated project `poe check`")


# --------------------------------------------------------------------------
# default Copier path -- from a wheel with no engine installed at all
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def engineless_copier_project(
    _forge_template_reachable: None,
    engineless_client: InstalledClient,
) -> Path:
    """One real Copier generation through the engine-less installed console,
    `_tasks` and all.
    """
    del _forge_template_reachable
    dest = engineless_client.root / "copier-project" / "rollout-copier-smoke"
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [str(engineless_client.console), "new", _COPIER_ANSWERS["project_name"]]
    args += ["--yes", "--path", str(dest)]
    for key, value in _COPIER_ANSWERS.items():
        if key != "project_name":
            args += ["--data", f"{key}={value}"]
    result = run(args, dest.parent, env=engineless_client.env)
    assert_success(result, "engine-less Copier generation")
    return dest


def test_engineless_copier_generation_has_the_expected_shape(
    engineless_copier_project: Path,
) -> None:
    project = engineless_copier_project
    assert (project / "pyproject.toml").is_file()
    assert (project / f"src/{_COPIER_PACKAGE_NAME}/__init__.py").is_file()
    assert (project / "tests").is_dir()
    assert (project / ".copier-answers.yml").is_file()
    # Both baked in by copier.yml's _tasks -- proof they ran from the wheel.
    assert (project / ".git").is_dir()
    assert (project / "uv.lock").is_file()


def test_engineless_copier_generation_records_the_answers(
    engineless_copier_project: Path,
) -> None:
    answers = yaml.safe_load(
        (engineless_copier_project / ".copier-answers.yml").read_text(encoding="utf-8")
    )
    for key, value in _COPIER_ANSWERS.items():
        assert answers[key] == value
    assert answers["_commit"]


def test_engineless_copier_project_passes_its_own_check(
    engineless_client: InstalledClient,
    engineless_copier_project: Path,
) -> None:
    result = run(
        [str(engineless_client.uv), "run", "poe", "check"],
        engineless_copier_project,
        env=engineless_client.env,
    )
    assert_success(result, "engine-less Copier project `poe check`")


def test_engineless_copier_generation_rejects_a_non_empty_destination(
    _forge_template_reachable: None,
    engineless_client: InstalledClient,
    tmp_path: Path,
) -> None:
    del _forge_template_reachable
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "keep.txt").write_text("hi", encoding="utf-8")

    args = [str(engineless_client.console), "new", "Blocked", "--yes", "--path"]
    args += [str(dest), "--data", "project_description=x", "--data", "github_org=o"]
    result = run(args, tmp_path, env=engineless_client.env)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "already exists and is not empty" in " ".join(
        (result.stdout + result.stderr).split()
    )
    assert list(dest.iterdir()) == [dest / "keep.txt"]


# --------------------------------------------------------------------------
# commands that must work with no engine installed
# --------------------------------------------------------------------------


def test_engineless_version_is_the_candidate(
    engineless_client: InstalledClient,
) -> None:
    result = run(
        [str(engineless_client.console), "--version"],
        engineless_client.root,
        env=engineless_client.env,
    )
    assert_success(result, "engine-less --version")
    assert result.stdout.strip() == CLIENT_VERSION


def test_engineless_list_shows_the_bundled_registry(
    engineless_client: InstalledClient,
) -> None:
    """`templates.toml` really shipped in the wheel (CLAUDE.md invariant 5)."""
    result = run(
        [str(engineless_client.console), "list"],
        engineless_client.root,
        env=engineless_client.env,
    )
    assert_success(result, "engine-less list")
    # The bundled registry's default template really loaded from the wheel.
    assert "(default)" in result.stdout


def test_engineless_doctor_json_reports_the_absent_engine(
    engineless_client: InstalledClient,
) -> None:
    result = run(
        [str(engineless_client.console), "doctor", "--json"],
        engineless_client.root,
        env=engineless_client.env,
    )
    # doctor's own git / uv / identity rows describe the host, not the
    # candidate, so its overall status is not asserted here.
    payload = json.loads(result.stdout)
    integration = payload["integration"]
    assert integration["engine_package"] is None
    assert integration["engine_range"] == f"forge-template{SUPPORTED_ENGINE_RANGE}"
    by_name = {check["name"]: check for check in payload["checks"]}
    assert by_name["registry"]["ok"] is True
    assert by_name["config"]["ok"] is True


def test_engineless_engine_preview_is_rejected_with_guidance(
    engineless_client: InstalledClient, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = run(
        [
            str(engineless_client.console),
            "new",
            "Engine Absent",
            "--engine-preview",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
        ],
        tmp_path,
        env=engineless_client.env,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "engine extra isn't installed" in " ".join(
        (result.stdout + result.stderr).split()
    )
    assert not dest.exists()
    assert _staging_siblings(dest) == []


# --------------------------------------------------------------------------
# compatibility boundary -- a real out-of-range engine
# --------------------------------------------------------------------------


def test_out_of_range_engine_is_rejected_before_any_write(
    out_of_range_client: InstalledClient, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = run(
        [
            str(out_of_range_client.console),
            "new",
            "Out Of Range",
            "--engine-preview",
            "--archetype",
            "library",
            "--yes",
            "--path",
            str(dest),
            "--data",
            "project_description=x",
        ],
        tmp_path,
        env=out_of_range_client.env,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    normalised = " ".join((result.stdout + result.stderr).split())
    assert "0.3.2" in normalised
    assert SUPPORTED_ENGINE_RANGE in normalised
    assert not dest.exists()
    assert _staging_siblings(dest) == []


def test_out_of_range_engine_is_visible_in_doctor(
    out_of_range_client: InstalledClient,
) -> None:
    result = run(
        [str(out_of_range_client.console), "doctor", "--json"],
        out_of_range_client.root,
        env=out_of_range_client.env,
    )
    payload = json.loads(result.stdout)
    integration = payload["integration"]
    assert integration["engine_package"] == "0.3.2"
    assert integration["engine_range"] == f"forge-template{SUPPORTED_ENGINE_RANGE}"


# --------------------------------------------------------------------------
# failure matrix -- documented status, actionable message, nothing written
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FailureCase:
    """One rejected invocation and what the CLI must do with it.

    `args` is a whitespace-split `new ...` command tail; `--path` is appended
    by the test. No value here contains a space.
    """

    id: str
    args: str
    exit_code: int
    fragment: str


_DS = "--engine-preview --archetype data-science"
_LIB = "--engine-preview --archetype library"
# The minimal answer set an engine-path ProjectSpec needs when a case gets
# far enough to be built rather than rejected at the CLI surface.
_DATA = "--data license=mit --data project_description=x"

_FAILURE_CASES = (
    FailureCase(
        "unknown-archetype",
        "new X --engine-preview --archetype nope --yes",
        1,
        "Unknown archetype 'nope'",
    ),
    FailureCase(
        "archetype-without-engine-preview",
        "new X --archetype library --yes",
        1,
        "--archetype requires --engine-preview",
    ),
    FailureCase(
        "engine-preview-yes-without-archetype",
        "new X --engine-preview --yes",
        1,
        "requires --archetype",
    ),
    FailureCase(
        "unknown-capability",
        f"new X {_LIB} --capability nope --yes",
        1,
        "Unknown --capability 'nope'",
    ),
    FailureCase(
        "wrong-kind-capability",
        f"new X {_LIB} --capability library --yes",
        1,
        "is not a capability",
    ),
    FailureCase(
        "contradictory-capability-flags",
        f"new X {_LIB} --capability jupyter --no-capabilities --yes",
        1,
        "contradictory",
    ),
    FailureCase(
        "capability-without-engine-preview",
        "new X --capability jupyter --yes",
        1,
        "require --engine-preview",
    ),
    FailureCase(
        "missing-hard-requirement",
        f"new X {_DS} --yes {_DATA}",
        1,
        "Add --capability jupyter.",
    ),
    FailureCase(
        "missing-hard-requirement-explicit-empty",
        f"new X {_DS} --no-capabilities --yes {_DATA}",
        1,
        "Add --capability jupyter.",
    ),
    FailureCase(
        "component-option-unknown-owner",
        f"new X {_LIB} --component-option nope.thing=1 --yes",
        1,
        "Unknown --component-option component 'nope'",
    ),
    FailureCase(
        "component-option-unselected-owner",
        f"new X {_LIB} --component-option jupyter.kernel=py --yes",
        1,
        "is not selected",
    ),
    FailureCase(
        "undeclared-component-option",
        f"new X {_LIB} --component-option library.not_a_real_option=1 --yes {_DATA}",
        1,
        "not_a_real_option",
    ),
    FailureCase(
        "engine-preview-with-copier-flag",
        f"new X {_LIB} --template python-lib --yes",
        1,
        "require the Copier path",
    ),
    FailureCase("malformed-data", f"new X {_LIB} --data oops --yes", 2, "key=value"),
    FailureCase(
        "malformed-component-option",
        f"new X {_LIB} --component-option oops --yes",
        2,
        "ID.OPTION=VALUE",
    ),
)


@pytest.mark.parametrize("case", _FAILURE_CASES, ids=lambda c: c.id)
def test_installed_failure_case_is_rejected_cleanly(
    installed_client: InstalledClient, case: FailureCase, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = run(
        [str(installed_client.console), *case.args.split(), "--path", str(dest)],
        tmp_path,
        env=installed_client.env,
    )
    normalised = " ".join((result.stdout + result.stderr).split())
    assert result.returncode == case.exit_code, normalised
    assert case.fragment in normalised
    assert not dest.exists()
    assert _staging_siblings(dest) == []


@pytest.mark.parametrize("engine_preview", [True, False])
def test_installed_non_empty_destination_is_preserved(
    installed_client: InstalledClient, tmp_path: Path, *, engine_preview: bool
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "keep.txt").write_text("original", encoding="utf-8")

    args = [
        str(installed_client.console),
        "new",
        "Blocked",
        "--yes",
        "--path",
        str(dest),
    ]
    args += ["--data", "project_description=x", "--data", "github_org=o"]
    if engine_preview:
        args += ["--engine-preview", "--archetype", "library"]
    result = run(args, tmp_path, env=installed_client.env)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "already exists and is not empty" in " ".join(
        (result.stdout + result.stderr).split()
    )
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "original"
    assert _staging_siblings(dest) == []


def test_installed_lock_failure_leaves_no_partial_project(
    installed_client: InstalledClient, tmp_path: Path
) -> None:
    """A real, non-monkeypatched lock failure: the render succeeds, then
    `staging.create_uv_lock` cannot find `uv` on a stripped PATH, so the
    staged tree is removed and the destination is never created.
    """
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = dict(installed_client.env)
    path_key = next((key for key in env if key.upper() == "PATH"), "PATH")
    env[path_key] = str(empty_bin)

    dest = tmp_path / "proj"
    result = run(
        [
            str(installed_client.console),
            *_engine_new_args("library", dest),
        ],
        tmp_path,
        env=env,
    )
    normalised = " ".join((result.stdout + result.stderr).split())
    assert result.returncode == 1, normalised
    assert "uv.lock" in normalised
    assert not dest.exists()
    assert _staging_siblings(dest) == []
