"""Installed-client batch end-to-end validation (CF-29.02).

Builds the create-forge candidate wheel, installs it alongside the reviewed
PyPI ``forge-template 0.7.0`` release into a clean virtual environment, then
drives the real installed ``create-forge`` console script through its default
(engine) `new` path -- the same installed boundary
`tests/test_e2e_installed_streamlit.py` (CF-21.02) established for Streamlit,
`tests/test_e2e_installed_data_science.py` (CF-14.02) for Data Science, and
`tests/test_e2e_installed_rollout.py` (CF-14.03) for the failure matrix.

This proves only what the *client* owns (CF-29.02 AC-1/AC-2, ADR 0062): every
accepted batch composition generates through the console, agrees byte for byte
with the installed pipeline's own ownership plan, carries a client-finalised
lock that restores under ``--locked``, and passes the generated project's own
checks and its bounded smoke; the example job runs through both of its entry
points; and every incompatible provider, invalid selection, destination
conflict, and lock failure leaves no partial project or staging state.
Provider-owned generated-project details -- the job's transformation, its
idempotency and fail-fast contract, the wheel and sdist contents, the sample
input -- are deliberately *not* re-audited here (CF-29.02 AC-5); they are
linked from ``docs/installed-batch-validation.md``.

The archetype and capability ids here are fixture data feeding the real
installed engine, never selection logic -- ``tests/test_archetype_parity.py``'s
guards own that rule for the shipped modules. Every workspace is
context-managed so virtual environments and generated projects are removed
after success, assertion failure, subprocess failure, or timeout.
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
from tests.batch_recipes import CHECK_COMMAND, RECIPES, RUN_COMMAND, Recipe
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

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

pytestmark = pytest.mark.e2e

_ARCHETYPE = "batch"
_PYTHON_WINDOW_EDGES = ("3.11", "3.14")

# The provider's accepted bound for the whole generated `poe check`, smoke
# included: forge-template's docs/batch-compatibility-and-acceptance.md
# ("Time-bounded, deterministic smoke"). A timeout is a failure -- never
# retried, and the bound is never raised to make a run pass; changing it is a
# provider decision (a superseding ADR there), not an edit here. `run` raises
# `subprocess.TimeoutExpired` on expiry, which fails the test.
_PROJECT_CHECK_TIMEOUT_SECONDS = 600

# The previous compatibility line. It is a real, published engine that lacks
# the `batch` archetype, so it is the incompatible provider a batch client is
# most likely to meet -- the `0.6.x` line `create-forge 0.5.0` declares.
_PREVIOUS_LINE_ENGINE = "0.6.0"

# The minimal answer set a failure case needs to get past the CLI surface and
# reach the engine, where the rejection under test is raised.
_DATA = "--data license=mit --data project_description=x"


@dataclass(frozen=True, slots=True)
class Composition:
    """One accepted batch component selection and its derived names."""

    slug: str
    project_name: str
    capabilities: tuple[str, ...]

    @property
    def repository_name(self) -> str:
        """The console script and directory name the engine derives."""
        return self.project_name.lower().replace(" ", "-")

    @property
    def package_name(self) -> str:
        """The importable package the job module lives in."""
        return self.repository_name.replace("-", "_")


# The four selections forge-template's acceptance contract accepts and sweeps
# at both window edges: the archetype alone, and with each of the two
# capabilities that add a runtime dependency. (The catalogue accepts 640
# compositions in all; the remaining axes are provider-owned.)
_COMPOSITIONS = (
    Composition(
        slug="alone",
        project_name="Installed Batch Alone",
        capabilities=(),
    ),
    Composition(
        slug="jupyter",
        project_name="Installed Batch Jupyter",
        capabilities=("jupyter",),
    ),
    Composition(
        slug="scientific-python",
        project_name="Installed Batch Scientific Python",
        capabilities=("scientific-python",),
    ),
    Composition(
        slug="jupyter-scientific-python",
        project_name="Installed Batch Full",
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
        "project_description": "Installed batch end-to-end validation.",
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

    Which files a batch project owns is the provider's contract; the
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
    canonical check and its job smoke, each under the provider's bound.

    Restoration is unbounded by the provider contract (it downloads); the check
    and the smoke are bounded. The smoke runs the archetype's own generated
    `tests/test_job.py`, which carries its own per-run bound.
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
        [str(client.uv), "run", "--locked", "pytest", "tests/test_job.py"],
        project,
        env=client.env,
        timeout=_PROJECT_CHECK_TIMEOUT_SECONDS,
    )
    assert_success(smoke, f"{project.name} bounded job smoke")


def _run_job_through_both_entry_points(
    client: InstalledClient, project: Path, composition: Composition
) -> None:
    """Run the example job from the project root via its console script and
    `python -m`, and check only what the *client* can vouch for.

    The transformation, its idempotency and its fail-fast contract belong to the
    provider and are proven by its own suite (and by the generated
    `tests/test_job.py` this module already runs). Here: both entry points
    exit 0, produce the output file, preserve the record count of the tracked
    sample input, and a rerun leaves byte-identical output.
    """
    sample = json.loads((project / "data" / "sample_input.json").read_text("utf-8"))
    output = project / "data" / "output.json"
    # The output is a git-ignored artefact the generated smoke may already have
    # produced in place; clear it so each entry point is shown to create it.
    output.unlink(missing_ok=True)

    invocations = (
        (
            "console script",
            [str(client.uv), "run", "--locked", composition.repository_name],
        ),
        (
            "python -m",
            [
                str(client.uv),
                "run",
                "--locked",
                "python",
                "-m",
                composition.package_name,
            ],
        ),
    )
    first_output: bytes | None = None
    for label, argv in invocations:
        result = run(
            argv, project, env=client.env, timeout=_PROJECT_CHECK_TIMEOUT_SECONDS
        )
        assert_success(result, f"{project.name} job via {label}")
        assert output.is_file(), label
        produced = json.loads(output.read_text(encoding="utf-8"))
        assert len(produced) == len(sample), label
        content = output.read_bytes()
        if first_output is None:
            first_output = content
        else:
            # A rerun through the *other* entry point must agree byte for byte.
            assert content == first_output, label


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
    _run_job_through_both_entry_points(client, project, composition)


# --------------------------------------------------------------------------
# AC-1: accepted compositions, committed locks, checks, bounded smoke and job
# --------------------------------------------------------------------------


@pytest.mark.parametrize("composition", _COMPOSITIONS, ids=lambda item: item.slug)
def test_installed_console_validates_batch_composition(
    installed_client: InstalledClient, composition: Composition
) -> None:
    """Every accepted composition passes every installed-client audit."""
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-batch-{composition.slug}-"
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
def test_full_batch_composition_passes_python_window_edge(
    installed_client: InstalledClient, endpoint: str
) -> None:
    """The heaviest composition passes at Python 3.11 and 3.14.

    Batch declares no runtime dependency of its own, so there is no
    third-party resolution to go wrong -- but the client's own lock
    finalisation, the generated project's build and its `poe check` still need
    proving at the floor and the ceiling, as the provider does for the same
    reason.
    """
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-batch-full-py{endpoint.replace('.', '')}-"
    ) as tmp:
        project = Path(tmp) / "project"
        assert_success(
            _generate(installed_client, _FULL_COMPOSITION, project, endpoint=endpoint),
            f"full batch generation at Python {endpoint}",
        )
        _validate_generated_project(
            installed_client, project, _FULL_COMPOSITION, endpoint
        )


# --------------------------------------------------------------------------
# generic selection, no batch-specific surface
# --------------------------------------------------------------------------


def test_installed_list_shows_batch_from_discovery(
    installed_client: InstalledClient,
) -> None:
    """`list` is built only from the engine's discovered catalogue -- the same
    data the interactive archetype prompt is built from -- so an entry here is
    the installed proof that batch is offered through the generic contract.
    Non-interactive selection is exercised by every composition test above via
    `--archetype batch --yes`; interactive selection is proven in-process by
    `tests/test_batch_adoption.py` (a PTY-driven e2e was deliberately not
    built, ADR 0051 and ADR 0062).
    """
    result = run(
        [str(installed_client.console), "list"],
        installed_client.root,
        env=installed_client.env,
    )
    assert_success(result, "installed create-forge list")

    rows = [line.split() for line in result.stdout.splitlines()]
    assert any(row[:2] == [_ARCHETYPE, "archetype"] for row in rows), result.stdout


def test_legacy_route_cannot_select_batch(
    installed_client: InstalledClient, tmp_path: Path
) -> None:
    """The Copier registry is Library-only: `--legacy` never reaches an engine
    archetype, so `--legacy --archetype batch` is a contradiction the CLI
    refuses before touching the disk.
    """
    destination = tmp_path / "proj"
    result = run(
        [
            str(installed_client.console),
            "new",
            "Legacy Batch",
            "--legacy",
            "--archetype",
            _ARCHETYPE,
            "--yes",
            "--path",
            str(destination),
            "--data",
            "license=mit",
        ],
        tmp_path,
        env=installed_client.env,
    )

    assert result.returncode == 1, _normalised(result)
    assert "contradictory" in _normalised(result)
    _assert_nothing_left_behind(destination)


# --------------------------------------------------------------------------
# AC-2: incompatible provider, invalid selections, conflicts, lock failure
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def previous_line_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel with a real `forge-template` from the previous
    compatibility line forced in afterward -- passing it to the main install
    would conflict with the wheel's own declared `>=0.7,<0.8` requirement and
    fail the resolver outright, so this is a second, targeted reinstall.
    """
    with build_client(
        candidate_wheel, e2e_child_env, force_version=_PREVIOUS_LINE_ENGINE
    ) as client:
        yield client


def test_previous_provider_line_is_rejected_before_any_write(
    previous_line_client: InstalledClient, tmp_path: Path
) -> None:
    """A published engine without `batch` is an incompatible provider: the
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


def test_previous_provider_line_fails_doctor_not_just_new(
    previous_line_client: InstalledClient,
) -> None:
    """CF-29.01 (ADR 0061) closed a gap: `doctor` used to pass on presence
    alone and report `ok: true` for an engine `new` refuses. Proven here on the
    installed console against a real out-of-range engine: `doctor` exits 1 and
    names the range, while protocol negotiation -- which the old engine
    satisfies -- still passes, so the failure is attributable to the package
    range alone.
    """
    result = run(
        [str(previous_line_client.console), "doctor", "--json"],
        previous_line_client.root,
        env=previous_line_client.env,
    )
    payload = json.loads(result.stdout)
    checks = {check["name"]: check for check in payload["checks"]}

    assert result.returncode == 1, result.stdout
    assert payload["ok"] is False
    assert checks["engine"]["ok"] is False
    assert _PREVIOUS_LINE_ENGINE in checks["engine"]["detail"]
    assert checks["engine negotiation"]["ok"] is True
    integration = payload["integration"]
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


# Mirrors the provider's accepted rejection matrix (forge-template
# docs/batch-compatibility-and-acceptance.md, "Valid and invalid selections"):
# the client must present each one cleanly, and none may write anything.
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
def test_installed_batch_selection_failure_is_rejected_cleanly(
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
# AC-5 / user recipes: the documented commands, through the installed console
# --------------------------------------------------------------------------


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda item: item.id)
def test_documented_recipe_runs_through_the_installed_console(
    installed_client: InstalledClient, recipe: Recipe
) -> None:
    """Run each command `docs/user-guide/batch.md` documents, verbatim but for
    the launcher (`uvx create-forge` becomes the installed console), from a
    clean working directory -- so the documented default destination is
    exercised too -- then the documented check and the documented run, under
    the provider's bound. `tests/test_user_guide_recipes.py` keeps the guide
    and these strings in step. Unlike a server archetype, the batch `run` task
    terminates, so it is a recipe step here too.
    """
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-batch-recipe-{recipe.id}-"
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

        for command in (CHECK_COMMAND, RUN_COMMAND):
            parts = shlex.split(command)
            assert parts[0] == "uv", command
            completed = run(
                [str(installed_client.uv), *parts[1:]],
                project,
                env=installed_client.env,
                timeout=_PROJECT_CHECK_TIMEOUT_SECONDS,
            )
            assert_success(completed, f"recipe {recipe.id}: {command}")

        assert (project / "data" / "output.json").is_file()
