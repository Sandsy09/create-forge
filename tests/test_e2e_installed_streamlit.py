"""Installed-client Streamlit end-to-end validation (CF-21.02).

Builds the create-forge candidate wheel, installs it alongside the reviewed
PyPI ``forge-template 0.6.0`` release into a clean virtual environment, then
drives the real installed ``create-forge`` console script through its default
(engine) `new` path -- the same installed boundary
`tests/test_e2e_installed_data_science.py` (CF-14.02) established for Data
Science, and `tests/test_e2e_installed_rollout.py` (CF-14.03) for the failure
matrix.

This proves only what the *client* owns (CF-ROADMAP-02-AC-04/05, ADR 0051):
every accepted Streamlit composition generates through the console, agrees
byte for byte with the installed pipeline's own ownership plan, carries a
client-finalised lock that restores under ``--locked``, and passes the
generated project's own checks and its bounded smoke; and every incompatible
provider, invalid selection, destination conflict, and lock failure leaves no
partial project or staging state. Provider-owned generated-project details --
the wheel and sdist contents, the ``run`` task, the secrets handling, the listen
guard -- are deliberately *not* re-audited here (CF-ROADMAP-02-AC-03/EX-01);
they are linked from ``docs/installed-streamlit-validation.md``.

The archetype and capability ids here are fixture data feeding the real
installed engine, never selection logic --
``tests/test_archetype_parity.py``'s guards own that rule for the shipped
modules. Every workspace is context-managed so virtual environments and
generated projects are removed after success, assertion failure, subprocess
failure, or timeout.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from create_forge.compat import SUPPORTED_ENGINE_RANGE
from tests.installed_client import (
    DEFAULT_PYTHON,
    FORGE_DISTRIBUTIONS,
    InstalledClient,
    assert_output_matches_owned_plan,
    assert_success,
    build_client,
    file_bytes,
    run,
)
from tests.streamlit_recipes import CHECK_COMMAND, RECIPES, Recipe

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

pytestmark = pytest.mark.e2e

_ARCHETYPE = "streamlit"
_PYTHON_WINDOW_EDGES = ("3.11", "3.14")

# The provider's accepted bound for the whole generated `poe check`, smoke
# included: forge-template's docs/streamlit-compatibility-and-acceptance.md
# ("Time-bounded, non-serving smoke"). A timeout is a failure -- never retried,
# and the bound is never raised to make a run pass; changing it is a provider
# decision, not an edit here. `run` raises `subprocess.TimeoutExpired` on
# expiry, which fails the test.
_PROJECT_CHECK_TIMEOUT_SECONDS = 600

# The previous compatibility line. It is a real, published engine that lacks
# the `streamlit` archetype, so it is the incompatible provider a Streamlit
# client is most likely to meet -- unlike rollout's older, far-below `0.3.2`.
_PREVIOUS_LINE_ENGINE = "0.5.0"

# The minimal answer set a failure case needs to get past the CLI surface and
# reach the engine, where the rejection under test is raised.
_DATA = "--data license=mit --data project_description=x"


@dataclass(frozen=True, slots=True)
class Composition:
    """One accepted Streamlit component selection and its derived names."""

    slug: str
    project_name: str
    capabilities: tuple[str, ...]


# The four selections forge-template's acceptance contract accepts: the
# archetype alone, and with each of the two capabilities it composes with.
_COMPOSITIONS = (
    Composition(
        slug="alone",
        project_name="Installed Streamlit Alone",
        capabilities=(),
    ),
    Composition(
        slug="jupyter",
        project_name="Installed Streamlit Jupyter",
        capabilities=("jupyter",),
    ),
    Composition(
        slug="scientific-python",
        project_name="Installed Streamlit Scientific Python",
        capabilities=("scientific-python",),
    ),
    Composition(
        slug="jupyter-scientific-python",
        project_name="Installed Streamlit Full",
        capabilities=("jupyter", "scientific-python"),
    ),
)
_ALONE = _COMPOSITIONS[0]
_FULL_COMPOSITION = _COMPOSITIONS[-1]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _answers(composition: Composition, endpoint: str) -> dict[str, str]:
    return {
        "project_name": composition.project_name,
        "project_description": "Installed Streamlit end-to-end validation.",
        "license": "mit",
        "author_name": "create-forge installed e2e",
        "author_email": "create-forge-installed-e2e@example.invalid",
        "python_min_version": "3.11",
        "python_version": endpoint,
    }


def _new_args(
    client: InstalledClient,
    composition: Composition,
    destination: Path,
    *,
    endpoint: str = DEFAULT_PYTHON,
) -> list[str]:
    args = [
        str(client.console),
        "new",
        composition.project_name,
        "--archetype",
        _ARCHETYPE,
        "--yes",
        "--path",
        str(destination),
    ]
    for key, value in _answers(composition, endpoint).items():
        if key != "project_name":
            args += ["--data", f"{key}={value}"]
    for capability in composition.capabilities:
        args += ["--capability", capability]
    return args


def _generate(
    client: InstalledClient,
    composition: Composition,
    destination: Path,
    *,
    endpoint: str = DEFAULT_PYTHON,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run(
        _new_args(client, composition, destination, endpoint=endpoint),
        destination.parent,
        env=client.env if env is None else env,
    )


def _staging_siblings(destination: Path) -> list[Path]:
    parent = destination.parent
    if not parent.is_dir():
        return []
    return [p for p in parent.iterdir() if p.name.startswith(".create-forge-")]


def _assert_nothing_left_behind(destination: Path) -> None:
    """No partial project and no `.create-forge-*` staging sibling."""
    assert not destination.exists()
    assert _staging_siblings(destination) == []


def _normalised(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join((result.stdout + result.stderr).split())


def _assert_initial_project_shape(project: Path) -> None:
    """Generic post-generation shape only.

    Which files a Streamlit project owns is the provider's contract; the
    ownership-plan comparison below proves the console wrote exactly what the
    installed pipeline planned. This asserts only what the *client* adds.
    """
    assert project.is_dir()
    assert (project / "pyproject.toml").is_file()
    assert (project / "uv.lock").is_file()
    assert (project / ".forge" / "generation.json").is_file()
    # The engine path runs no copier.yml _tasks but does run its own
    # post-rename lifecycle (CF-18.03, ADR 0045): `git init` + one commit. No
    # composition selects `pre-commit`, so hooks are not installed and no
    # `.venv` is created.
    assert (project / ".git").is_dir()
    assert not (project / ".venv").exists()
    assert _staging_siblings(project) == []


def _assert_lock_is_current(client: InstalledClient, project: Path) -> None:
    result = run([str(client.uv), "lock", "--check"], project, env=client.env)
    assert_success(result, f"{project.name} uv lock --check")


def _assert_no_forge_dependencies(project: Path) -> None:
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
    assert declared.isdisjoint(FORGE_DISTRIBUTIONS)
    assert locked.isdisjoint(FORGE_DISTRIBUTIONS)


def _restore_check_and_smoke(client: InstalledClient, project: Path) -> None:
    """Restore from the committed lock, then run the generated project's own
    canonical check and its Streamlit smoke, each under the provider's bound.

    Restoration is unbounded by the provider contract (it downloads); the check
    and the smoke are bounded. The smoke runs the archetype's own generated
    `tests/test_app.py` (non-serving `AppTest`); `streamlit run` is never
    started here, and the `run` task is not exercised.
    """
    restored = run(
        [str(client.uv), "sync", "--all-groups", "--locked"], project, env=client.env
    )
    assert_success(restored, f"{project.name} locked restoration")

    checked = run(
        [str(client.uv), "run", "--locked", "poe", "check"],
        project,
        env=client.env,
        timeout=_PROJECT_CHECK_TIMEOUT_SECONDS,
    )
    assert_success(checked, f"{project.name} canonical project check")

    smoke = run(
        [str(client.uv), "run", "--locked", "pytest", "tests/test_app.py"],
        project,
        env=client.env,
        timeout=_PROJECT_CHECK_TIMEOUT_SECONDS,
    )
    assert_success(smoke, f"{project.name} bounded Streamlit smoke")


def _validate_generated_project(
    client: InstalledClient,
    project: Path,
    composition: Composition,
    endpoint: str,
) -> None:
    _assert_initial_project_shape(project)
    _assert_lock_is_current(client, project)
    assert_output_matches_owned_plan(
        client,
        project,
        archetype=_ARCHETYPE,
        capabilities=composition.capabilities,
        answers=_answers(composition, endpoint),
    )
    _assert_no_forge_dependencies(project)
    _restore_check_and_smoke(client, project)


# --------------------------------------------------------------------------
# AC-04: accepted compositions, committed locks, checks, bounded smoke
# --------------------------------------------------------------------------


@pytest.mark.parametrize("composition", _COMPOSITIONS, ids=lambda item: item.slug)
def test_installed_console_validates_streamlit_composition(
    installed_client: InstalledClient, composition: Composition
) -> None:
    """Every accepted composition passes every installed-client audit."""
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-streamlit-{composition.slug}-"
    ) as tmp:
        root = Path(tmp)
        first = root / "first"
        repeated = root / "repeated"

        assert_success(
            _generate(installed_client, composition, first),
            f"first {composition.slug} generation",
        )
        assert_success(
            _generate(installed_client, composition, repeated),
            f"repeated {composition.slug} generation",
        )

        _assert_initial_project_shape(repeated)
        _assert_lock_is_current(installed_client, repeated)
        # Determinism: two independent generations agree on every byte,
        # including the client-finalised `uv.lock`.
        assert file_bytes(first) == file_bytes(repeated)

        _validate_generated_project(
            installed_client, first, composition, DEFAULT_PYTHON
        )


@pytest.mark.parametrize("endpoint", _PYTHON_WINDOW_EDGES)
def test_full_streamlit_composition_passes_python_window_edge(
    installed_client: InstalledClient, endpoint: str
) -> None:
    """The heaviest composition passes at Python 3.11 and 3.14.

    The provider's only real Streamlit defect was interpreter-dependent (a NumPy
    ceiling that mattered on 3.12+, invisible to resolution alone), so the
    client's own lock finalisation is proven at both window edges too.
    """
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-streamlit-full-py{endpoint.replace('.', '')}-"
    ) as tmp:
        project = Path(tmp) / "project"
        assert_success(
            _generate(installed_client, _FULL_COMPOSITION, project, endpoint=endpoint),
            f"full Streamlit generation at Python {endpoint}",
        )
        _validate_generated_project(
            installed_client, project, _FULL_COMPOSITION, endpoint
        )


# --------------------------------------------------------------------------
# AC-02 (installed half): generic selection, no Streamlit-specific surface
# --------------------------------------------------------------------------


def test_installed_list_shows_streamlit_from_discovery(
    installed_client: InstalledClient,
) -> None:
    """`list` is built only from the engine's discovered catalogue -- the same
    data the interactive archetype prompt is built from -- so an entry here is
    the installed proof that Streamlit is offered through the generic contract.
    Non-interactive selection is exercised by every composition test above via
    `--archetype streamlit --yes`; interactive selection is proven in-process by
    `tests/test_streamlit_adoption.py` (a PTY-driven e2e was deliberately not
    built, ADR 0051).
    """
    result = run(
        [str(installed_client.console), "list"],
        installed_client.root,
        env=installed_client.env,
    )
    assert_success(result, "installed create-forge list")

    rows = [line.split() for line in result.stdout.splitlines()]
    assert any(row[:2] == [_ARCHETYPE, "archetype"] for row in rows), result.stdout


# --------------------------------------------------------------------------
# AC-05: incompatible provider, invalid selections, conflicts, lock failure
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def previous_line_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel with a real `forge-template` from the previous
    compatibility line forced in afterward -- passing it to the main install
    would conflict with the wheel's own declared `>=0.6,<0.7` requirement and
    fail the resolver outright, so this is a second, targeted reinstall.
    """
    with build_client(
        candidate_wheel, e2e_child_env, force_version=_PREVIOUS_LINE_ENGINE
    ) as client:
        yield client


def test_previous_provider_line_is_rejected_before_any_write(
    previous_line_client: InstalledClient, tmp_path: Path
) -> None:
    """A published engine without `streamlit` is an incompatible provider: the
    range check rejects it at exit 3 before discovery, so the user is told to
    install a compatible engine rather than shown an "unknown archetype".
    """
    destination = tmp_path / "proj"
    result = run(
        [
            str(previous_line_client.console),
            "new",
            "Previous Line",
            "--archetype",
            _ARCHETYPE,
            "--yes",
            "--path",
            str(destination),
            "--data",
            "project_description=x",
        ],
        tmp_path,
        env=previous_line_client.env,
    )

    normalised = _normalised(result)
    assert result.returncode == 3, normalised
    assert _PREVIOUS_LINE_ENGINE in normalised
    assert SUPPORTED_ENGINE_RANGE in normalised
    _assert_nothing_left_behind(destination)


def test_previous_provider_line_is_visible_in_doctor(
    previous_line_client: InstalledClient,
) -> None:
    result = run(
        [str(previous_line_client.console), "doctor", "--json"],
        previous_line_client.root,
        env=previous_line_client.env,
    )
    integration = json.loads(result.stdout)["integration"]
    assert integration["engine_package"] == _PREVIOUS_LINE_ENGINE
    assert integration["engine_range"] == f"forge-template{SUPPORTED_ENGINE_RANGE}"


@dataclass(frozen=True, slots=True)
class FailureCase:
    """One rejected invocation and what the CLI must do with it.

    `args` is a whitespace-split `new ...` command tail; `--path` is appended
    by the test. `fragments` must all appear in the whitespace-normalised
    output. Engine-owned rejections keep the engine's stable error code in the
    message (`engine.explain`), so the code is part of what is asserted.
    """

    id: str
    args: str
    fragments: tuple[str, ...]
    exit_code: int = 1


# Mirrors the provider's accepted rejection matrix
# (forge-template tests/test_streamlit_composition.py `_REJECTIONS`): the
# client must present each one cleanly, and none may write anything.
_FAILURE_CASES = (
    FailureCase(
        "documentation-requires-library",
        f"new X --archetype {_ARCHETYPE} --capability documentation --yes {_DATA}",
        (
            "invalid-component-selection",
            "component 'documentation' requires selected component(s): library",
        ),
    ),
    FailureCase(
        "dependabot-requires-github",
        f"new X --archetype {_ARCHETYPE} --capability dependabot --yes {_DATA}",
        (
            "invalid-component-selection",
            "component 'dependabot' requires selected component(s): github",
        ),
    ),
    FailureCase(
        "options-for-an-optionless-archetype",
        f"new X --archetype {_ARCHETYPE} "
        f"--component-option {_ARCHETYPE}.not_a_real_option=1 --yes {_DATA}",
        (
            "invalid-component-options",
            "not declared by its options_schema: not_a_real_option",
        ),
    ),
    FailureCase(
        "archetype-given-as-a-capability",
        f"new X --archetype library --capability {_ARCHETYPE} --yes {_DATA}",
        (f"--capability '{_ARCHETYPE}' is not a capability",),
    ),
)


@pytest.mark.parametrize("case", _FAILURE_CASES, ids=lambda item: item.id)
def test_installed_streamlit_selection_failure_is_rejected_cleanly(
    installed_client: InstalledClient, case: FailureCase, tmp_path: Path
) -> None:
    destination = tmp_path / "proj"
    result = run(
        [
            str(installed_client.console),
            *case.args.split(),
            "--path",
            str(destination),
        ],
        tmp_path,
        env=installed_client.env,
    )

    normalised = _normalised(result)
    assert result.returncode == case.exit_code, normalised
    for fragment in case.fragments:
        assert fragment in normalised
    _assert_nothing_left_behind(destination)


def test_installed_non_empty_destination_is_preserved(
    installed_client: InstalledClient, tmp_path: Path
) -> None:
    destination = tmp_path / "proj"
    destination.mkdir()
    (destination / "keep.txt").write_text("original", encoding="utf-8")

    result = _generate(installed_client, _ALONE, destination)

    assert result.returncode == 1, _normalised(result)
    assert "already exists and is not empty" in _normalised(result)
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "original"
    assert _staging_siblings(destination) == []


def test_installed_lock_failure_leaves_no_partial_project(
    installed_client: InstalledClient, tmp_path: Path
) -> None:
    """A real, non-monkeypatched lock failure: the render succeeds, then
    `staging.create_uv_lock` cannot find `uv` on a stripped PATH, so the staged
    tree is removed and the destination is never created.
    """
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = dict(installed_client.env)
    path_key = next((key for key in env if key.upper() == "PATH"), "PATH")
    env[path_key] = str(empty_bin)

    destination = tmp_path / "proj"
    result = _generate(installed_client, _ALONE, destination, env=env)

    normalised = _normalised(result)
    assert result.returncode == 1, normalised
    assert "uv.lock" in normalised
    _assert_nothing_left_behind(destination)


# --------------------------------------------------------------------------
# AC-03 / AC-07: the documented user recipes, through the installed console
# --------------------------------------------------------------------------


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda item: item.id)
def test_documented_recipe_runs_through_the_installed_console(
    installed_client: InstalledClient, recipe: Recipe
) -> None:
    """Run each command `docs/user-guide/streamlit.md` documents, verbatim but
    for the launcher (`uvx create-forge` becomes the installed console), from a
    clean working directory -- so the documented default destination is
    exercised too -- then the documented check, under the provider's bound.
    `tests/test_user_guide_recipes.py` keeps the guide and these strings in
    step. `poe run` is not a recipe step here: it serves.
    """
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-streamlit-recipe-{recipe.id}-"
    ) as tmp:
        workdir = Path(tmp)
        argv = shlex.split(recipe.command)
        assert argv[:2] == ["uvx", "create-forge"], recipe.command

        created = run(
            [str(installed_client.console), *argv[2:]],
            workdir,
            env=installed_client.env,
        )
        assert_success(created, f"recipe {recipe.id}: {recipe.command}")

        project = workdir / recipe.directory
        assert project.is_dir(), sorted(p.name for p in workdir.iterdir())

        check = shlex.split(CHECK_COMMAND)
        assert check[0] == "uv", CHECK_COMMAND
        checked = run(
            [str(installed_client.uv), *check[1:]],
            project,
            env=installed_client.env,
            timeout=_PROJECT_CHECK_TIMEOUT_SECONDS,
        )
        assert_success(checked, f"recipe {recipe.id}: {CHECK_COMMAND}")
