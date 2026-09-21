"""Installed-candidate cutover evidence: CF-18.05's retained legacy Copier
route and rejected pre-cutover `--engine-preview` transition, plus CF-18.06's
extension to the rest of the installed cutover acceptance matrix -- install
modes, cutover-specific incompatible/invalid/failure/boundary cases, and the
documented recipes.

`docs/engine-cutover-acceptance.md`'s accepted matrix names this module across
six rows: CF-18.05's legacy route and preview-transition rows (204/205, 212),
and CF-18.06's install-mode (172), failure/boundary (219/220), and integrated
(228/229) rows. ADR 0047 records why the file was created by CF-18.05 rather
than CF-18.06; ADR 0048 records CF-18.06's own scoping decisions -- most
importantly, that rows 219/220 are covered here only for surfaces that
postdate `tests/test_e2e_installed_rollout.py` (CF-14.03), which already
proves the bulk of the installed selection/option/destination/lock/cleanup
failure matrix and the out-of-range/no-engine boundary at this same
boundary. `docs/engine-cutover-validation.md` maps every row, including the
rollout suite's pre-existing coverage, to a named test.

Scoped to what only an installed wheel can prove. The offline local-tagged
Copier coverage (dry-run non-mutation, local-edit preservation, a
missing-source failure) already lives in `tests/test_update.py`, reusing the
same `tests/legacy_template.py` harness this module also reuses. The
engine-native update's own merge/classification logic is proven at the fast
suite level by `tests/test_update_engine.py`; this module proves it survives
the full CLI orchestration through a real installed console.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.installed_client import (
    ENGINE_VERSION,
    InstalledClient,
    assert_success,
    build_client,
    run,
)
from tests.legacy_template import (
    TEMPLATE_FIRST_TAG,
    TEMPLATE_SECOND_TAG,
    build_tagged_template,
    commit,
    git,
    init_repo,
    visible_files,
)
from tests.process import run_text
from tests.recovery_recipes import CLEAN_ARGV, CLEAN_PREVIEW_ARGV, RESTORE_ARGV

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

pytestmark = pytest.mark.e2e

_OUT_OF_RANGE_ENGINE = "0.3.2"
_LIBRARY_ANSWERS = {
    "project_description": "create-forge installed cutover CF-18.06 regression.",
    "license": "mit",
    "author_name": "create-forge e2e",
    "author_email": "create-forge-e2e@example.invalid",
}
# The rest of the supported Python window (3.12, 3.13) is discharged by the
# `test` CI matrix and `floor` job (ADR 0048 decision 3), not repeated here --
# mirrors `tests/test_e2e_installed_data_science.py`'s `_PYTHON_WINDOW_EDGES`.
_PYTHON_WINDOW_EDGES = ("3.11", "3.14")


# --------------------------------------------------------------------------
# environments and fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="session")
def local_tagged_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The same real, git-backed, two-tag Copier template
    `tests/test_update.py` uses (`tests/legacy_template.py`), built once for
    the whole session -- this module never mutates it.
    """
    return build_tagged_template(tmp_path_factory.mktemp("legacy-cutover-template"))


@pytest.fixture(scope="session")
def no_legacy_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel installed with no extra at all -- `copier` absent,
    unlike the shared `installed_client` fixture (`extras="[legacy]"`). The
    reviewed engine is still pinned so this differs from `installed_client`
    in exactly one respect.
    """
    with build_client(
        candidate_wheel, e2e_child_env, engine=f"forge-template=={ENGINE_VERSION}"
    ) as client:
        yield client


@pytest.fixture(scope="session")
def _forge_template_reachable() -> None:
    """Skip, not fail, a test needing GitHub when it is unreachable -- the
    same contract `tests/test_e2e_installed_rollout.py` and
    `tests/test_e2e_generation.py` keep.
    """
    try:
        run_text(
            [
                "git",
                "ls-remote",
                "--tags",
                "--refs",
                "https://github.com/Sandsy09/forge-template",
            ],
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not reach forge-template on GitHub: {exc}")


def _read_answers(project: Path) -> dict[str, object]:
    data: dict[str, object] = yaml.safe_load(
        (project / ".copier-answers.yml").read_text(encoding="utf-8")
    )
    return data


# --------------------------------------------------------------------------
# CF-18.06: install-mode helpers (row 172)
#
# `uvx`/`uv tool install` resolve `uv` and `forge-template` into their own
# managed environments, not a venv `tests/installed_client.py`'s
# `build_client` controls -- these two small helpers are kept local to this
# module rather than added to the shared harness (ADR 0048 decision 6: this
# issue only extends this file and tests/test_cli.py).
# --------------------------------------------------------------------------


def _isolated_tool_env(base: Mapping[str, str], config_root: Path) -> dict[str, str]:
    """Env for running an already-installed `uvx`/`uv tool install` console
    script -- the same isolation `installed_client.installed_child_env` gives
    a venv-installed console, minus the venv-scripts PATH prepend: `uvx`/
    `uv tool install` resolve their own environment from the requirement, and
    the host's own `uv` (put on PATH by the CI job's `setup-uv` step, or a
    developer's real install) is exactly what a real `uvx create-forge` user
    has on PATH by definition -- `staging.create_uv_lock` shells out to it by
    name.
    """
    env = {k: v for k, v in base.items() if not k.upper().startswith("FORGE_")}
    for leak in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONHOME", "PYTHONPATH"):
        env.pop(leak, None)
    env["XDG_CONFIG_HOME"] = str(config_root)
    return env


def _tool_bin_script(bin_dir: Path) -> Path:
    """The console script `uv tool install` places in its bin directory."""
    exe = bin_dir / "create-forge.exe"
    return exe if exe.is_file() else bin_dir / "create-forge"


def _engine_new_args(
    dest: Path, *, project_name: str = "Cutover Install Mode"
) -> list[str]:
    """`new --archetype library --yes` args for a plain engine-path
    generation -- no capabilities, matching the answers every install-mode
    test needs and nothing more.
    """
    args = [
        "new",
        project_name,
        "--archetype",
        "library",
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in _LIBRARY_ANSWERS.items():
        args += ["--data", f"{key}={value}"]
    return args


def _assert_engine_generation(dest: Path) -> None:
    """The minimum an engine-path generation must have produced -- shape,
    committed metadata, and a lockfile (ADR 0048 decision 1: install-mode
    tests stop here rather than re-running the generated project's own
    `poe check`, which `tests/test_e2e_installed_rollout.py` and this
    module's own legacy tests already prove at this boundary).
    """
    assert dest.is_dir(), dest
    assert (dest / "pyproject.toml").is_file()
    assert (dest / ".forge" / "generation.json").is_file()
    assert (dest / "uv.lock").is_file()


# --------------------------------------------------------------------------
# the retained legacy Copier route (acceptance rows 204-205)
# --------------------------------------------------------------------------


def test_legacy_extra_installs_copier(installed_client: InstalledClient) -> None:
    """`create-forge[legacy]` resolves `copier` -- read back through
    `doctor --json`'s own diagnostic field rather than probing the venv
    directly, since that field is the client's own documented contract
    (docs/engine-resolution.md). `doctor`'s overall `ok`/exit status is not
    asserted here -- an unrelated check (e.g. no global git identity on a
    bare CI runner) can fail it independent of anything this test covers,
    exactly as `tests/test_e2e_installed_rollout.py`'s own `doctor --json`
    cases only inspect the fields they care about.
    """
    result = run(
        [str(installed_client.console), "doctor", "--json"],
        installed_client.root,
        env=installed_client.env,
    )
    payload = json.loads(result.stdout)
    assert payload["integration"]["copier"] is not None


def test_legacy_generation_and_update_against_a_local_tagged_template(
    installed_client: InstalledClient, local_tagged_template: Path
) -> None:
    """`new --legacy` and `update` against a recorded `.copier-answers.yml`
    project run real tagged Copier generation and update, preserving local
    edits and reaching the second tag (acceptance row 204)."""
    dest = installed_client.root / "legacy-cutover" / "tagged-template-trial"
    dest.parent.mkdir(parents=True, exist_ok=True)

    scaffolded = run(
        [
            str(installed_client.console),
            "new",
            "--legacy",
            "Legacy Cutover Trial",
            "--yes",
            "--template-url",
            str(local_tagged_template),
            "--ref",
            TEMPLATE_FIRST_TAG,
            "--path",
            str(dest),
        ],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(scaffolded, "installed new --legacy against a local tagged template")
    assert _read_answers(dest)["_commit"] == TEMPLATE_FIRST_TAG

    # `runner.update`'s clean-tree precondition (unchanged since before
    # CF-18.04) needs a git-tracked project -- the legacy route's own scaffold
    # step does not init one, exactly like `tests/test_update.py`'s
    # `_prepare_project`.
    init_repo(dest)
    commit(dest, "initial scaffold")
    (dest / "notes.txt").write_text("my own notes\n", encoding="utf-8")
    commit(dest, "local edit")
    before = visible_files(dest)

    dry_run = run(
        [str(installed_client.console), "update", "--dry-run", str(dest)],
        dest,
        env=installed_client.env,
    )
    assert_success(dry_run, "installed update --dry-run")
    assert visible_files(dest) == before

    updated = run(
        [str(installed_client.console), "update", str(dest)],
        dest,
        env=installed_client.env,
    )
    assert_success(updated, "installed update")
    assert _read_answers(dest)["_commit"] == TEMPLATE_SECOND_TAG
    assert (dest / "notes.txt").read_text(encoding="utf-8") == "my own notes\n"
    assert "v2" in (dest / "README.md").read_text(encoding="utf-8")
    assert (dest / "CHANGELOG.md").is_file()


def test_legacy_route_without_the_extra_exits_3(
    no_legacy_client: InstalledClient,
) -> None:
    """`--legacy` without the extra exits `3` naming the remedy (acceptance
    row 204's final clause) -- there is no coverage of this at any level
    below the installed boundary, since the fast suite always installs
    `[legacy]`."""
    result = run(
        [str(no_legacy_client.console), "new", "--legacy", "Blocked", "--yes"],
        no_legacy_client.root,
        env=no_legacy_client.env,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "pip install" in result.stderr
    assert "create-forge[legacy]" in result.stderr


# --------------------------------------------------------------------------
# the pre-cutover `--engine-preview` transition (acceptance row 212)
# --------------------------------------------------------------------------


def test_preview_era_project_transition_is_rejected(
    installed_client: InstalledClient,
) -> None:
    """A directory with neither provenance file -- the shape a pre-cutover
    `--engine-preview` project has (ADR 0047 rule 1: that flag wrote no
    answers file and no metadata) -- is rejected by `update` with actionable
    guidance, and nothing is written (CF-ROADMAP-01-AC-05)."""
    project = installed_client.root / "legacy-cutover" / "preview-era-project"
    project.mkdir(parents=True)

    result = run(
        [str(installed_client.console), "update", str(project)],
        project,
        env=installed_client.env,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "--engine-preview" in result.stderr
    assert "create-forge new" in result.stderr
    assert not (project / ".forge").exists()
    assert not (project / ".copier-answers.yml").exists()


# --------------------------------------------------------------------------
# CF-18.06: the four contractual install modes (acceptance row 172)
# --------------------------------------------------------------------------


def test_install_modes_uvx_ephemeral_resolves_and_generates(
    candidate_wheel: Path, e2e_child_env: dict[str, str], tmp_path: Path
) -> None:
    """`uvx create-forge` -- the primary documented ephemeral path
    (`docs/engine-cutover-acceptance.md`'s Install modes table) -- resolves
    the required engine and generates from an isolated, uv-managed
    environment with no persistent install of its own.
    """
    root = tmp_path / "uvx-mode"
    root.mkdir()
    env = _isolated_tool_env(e2e_child_env, root / "config")

    # `doctor`'s overall exit status/`ok` reflects unrelated environment
    # checks too (e.g. no global git identity on a bare CI runner) --
    # test_legacy_extra_installs_copier's own docstring explains this; only
    # the field this test cares about is asserted.
    doctor = run(
        ["uvx", "--from", str(candidate_wheel), "create-forge", "doctor", "--json"],
        root,
        env=env,
    )
    payload = json.loads(doctor.stdout)
    assert payload["integration"]["engine_package"] is not None

    dest = root / "generated"
    generated = run(
        [
            "uvx",
            "--from",
            str(candidate_wheel),
            "create-forge",
            *_engine_new_args(dest),
        ],
        root,
        env=env,
    )
    assert_success(generated, "uvx create-forge new")
    _assert_engine_generation(dest)


def test_install_modes_uv_tool_install_resolves_and_generates(
    candidate_wheel: Path, e2e_child_env: dict[str, str], tmp_path: Path
) -> None:
    """`uv tool install create-forge` -- the persistent install mode -- makes
    its own managed environment resolve the required engine and expose a
    console script independent of any project virtualenv.
    """
    root = tmp_path / "tool-install-mode"
    root.mkdir()
    tool_dir = root / "tools"
    bin_dir = root / "bin"
    install_env = dict(e2e_child_env)
    install_env["UV_TOOL_DIR"] = str(tool_dir)
    install_env["UV_TOOL_BIN_DIR"] = str(bin_dir)

    installed = run(
        ["uv", "tool", "install", str(candidate_wheel)], root, env=install_env
    )
    assert_success(installed, "uv tool install create-forge")

    console = _tool_bin_script(bin_dir)
    assert console.is_file(), console
    run_env = _isolated_tool_env(e2e_child_env, root / "config")

    # See test_install_modes_uvx_ephemeral_resolves_and_generates's comment:
    # `doctor`'s overall status is not asserted, only the field of interest.
    doctor = run([str(console), "doctor", "--json"], root, env=run_env)
    payload = json.loads(doctor.stdout)
    assert payload["integration"]["engine_package"] is not None

    dest = root / "generated"
    generated = run([str(console), *_engine_new_args(dest)], root, env=run_env)
    assert_success(generated, "uv tool install create-forge new")
    _assert_engine_generation(dest)


def test_install_modes_pip_install_resolves_and_generates(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> None:
    """`pip install create-forge` -- the Environment mode -- into an active
    virtual environment resolves the required engine alongside it and
    generates with no `legacy` extra at all.
    """
    with build_client(candidate_wheel, e2e_child_env) as client:
        # See test_install_modes_uvx_ephemeral_resolves_and_generates's
        # comment: `doctor`'s overall status is not asserted here either.
        doctor = run(
            [str(client.console), "doctor", "--json"], client.root, env=client.env
        )
        payload = json.loads(doctor.stdout)
        assert payload["integration"]["engine_package"] is not None

        dest = client.root / "generated"
        generated = run(
            [str(client.console), *_engine_new_args(dest)], client.root, env=client.env
        )
        assert_success(generated, "pip install create-forge new")
        _assert_engine_generation(dest)


def test_install_modes_legacy_extra_resolves_and_generates(
    installed_client: InstalledClient,
) -> None:
    """`create-forge[legacy]` -- the fourth contractual install mode -- keeps
    resolving the required engine (this module's own
    `test_legacy_extra_installs_copier` proves it also resolves `copier`) and
    still generates through the default engine path, not only `--legacy`.
    """
    dest = installed_client.root / "install-modes" / "legacy-extra-default-path"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated = run(
        [str(installed_client.console), *_engine_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "create-forge[legacy] new (default engine path)")
    _assert_engine_generation(dest)


@pytest.mark.parametrize("python", _PYTHON_WINDOW_EDGES)
def test_install_modes_python_window_edge(
    python: str, candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> None:
    """The pip-install mode resolves and generates at both edges of the
    supported Python window (`docs/engine-cutover-acceptance.md`'s Python
    axis) -- the rest of the window is proven by the `test` CI matrix and
    `floor` job (ADR 0048 decision 3), not repeated here.
    """
    with build_client(candidate_wheel, e2e_child_env, python=python) as client:
        dest = client.root / "generated"
        generated = run(
            [str(client.console), *_engine_new_args(dest)], client.root, env=client.env
        )
        assert_success(generated, f"create-forge new on Python {python}")
        _assert_engine_generation(dest)


# --------------------------------------------------------------------------
# CF-18.06: cutover-specific incompatible/invalid/failure/boundary cases
# (acceptance rows 219-220) -- only surfaces that postdate
# tests/test_e2e_installed_rollout.py; docs/engine-cutover-validation.md maps
# that suite's own pre-existing coverage onto these same rows.
# --------------------------------------------------------------------------


def test_incompatible_engine_native_update_fails_closed_at_exit_3(
    installed_client: InstalledClient,
    candidate_wheel: Path,
    e2e_child_env: dict[str, str],
) -> None:
    """An engine-native project's `update`, run against an out-of-range
    engine, fails closed at exit `3` and writes nothing -- the update-side
    counterpart to the rollout suite's `new`-side boundary tests, not
    covered anywhere until now. `generation_metadata_target` predates the
    `0.3.2` release, so its own `ImportError` reaches `update_project`'s
    ADR 0047 rule 3 fallback -- and, since this project has no
    `.copier-answers.yml`, that fallback itself exits `3`.
    """
    dest = installed_client.root / "incompatible" / "engine-native-project"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated = run(
        [str(installed_client.console), *_engine_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "generate the project to update")
    before = visible_files(dest)

    with build_client(
        candidate_wheel, e2e_child_env, force_version=_OUT_OF_RANGE_ENGINE
    ) as broken_client:
        result = run(
            [str(broken_client.console), "update", str(dest)],
            dest,
            env=broken_client.env,
        )

    assert result.returncode == 3, result.stdout + result.stderr
    assert "unusable" in result.stderr
    assert visible_files(dest) == before


def test_invalid_degraded_with_an_unusable_engine_exits_1(
    installed_client: InstalledClient,
    candidate_wheel: Path,
    e2e_child_env: dict[str, str],
    local_tagged_template: Path,
) -> None:
    """`--degraded` combined with a `.copier-answers.yml` project reached
    through ADR 0047 rule 3's own engine-unusable fallback -- not the
    earlier, already-covered `Route.COPIER` branch
    (`tests/test_update_routing.py::test_cli_rejects_degraded_on_the_copier_route`)
    -- still exits `1` naming `--degraded`, proven here for the first time
    through a real installed console with a genuinely broken engine.
    """
    dest = installed_client.root / "invalid" / "legacy-degraded-unusable-engine"
    dest.parent.mkdir(parents=True, exist_ok=True)
    scaffolded = run(
        [
            str(installed_client.console),
            "new",
            "--legacy",
            "Invalid Degraded Trial",
            "--yes",
            "--template-url",
            str(local_tagged_template),
            "--ref",
            TEMPLATE_FIRST_TAG,
            "--path",
            str(dest),
        ],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(
        scaffolded, "installed new --legacy for the degraded-rejection fixture"
    )

    with build_client(
        candidate_wheel, e2e_child_env, force_version=_OUT_OF_RANGE_ENGINE
    ) as broken_client:
        result = run(
            [str(broken_client.console), "update", "--degraded", str(dest)],
            dest,
            env=broken_client.env,
        )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "--degraded" in result.stderr


def test_failure_engine_native_degraded_update_refuses_to_overwrite_a_diverged_edit(
    installed_client: InstalledClient,
) -> None:
    """A `--degraded` update whose working tree has diverged from the
    recorded digest reports a conflict and leaves the file exactly as the
    user left it -- `degraded_plan` has no merge base to reconcile a local
    edit against a stale template default, so it never overwrites (rule 22),
    unlike the engine-native route's real three-way merge, which inserts
    conflict markers instead (`tests/test_update_engine.py` proves that at
    the fast-suite level). This proves the *degraded* route's own
    no-merge-base guarantee survives the full CLI orchestration through a
    real installed console for the first time -- no engine update has run
    through an installed console before this.
    """
    dest = installed_client.root / "failure" / "engine-native-degraded-conflict"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated = run(
        [str(installed_client.console), *_engine_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "generate the project to conflict-update")

    readme = dest / "README.md"
    diverged = readme.read_text(encoding="utf-8") + "local edit\n"
    readme.write_text(diverged, encoding="utf-8")
    # A local commit here (distinct from the engine lifecycle's own initial
    # commit, which supplies its own identity via installed_client.env's
    # GIT_AUTHOR_NAME/EMAIL) needs its own repo-local identity -- a bare CI
    # runner has no global git config, the same reason
    # tests/legacy_template.py's init_repo sets one.
    git("config", "user.name", "Test", cwd=dest)
    git("config", "user.email", "test@example.com", cwd=dest)
    git("add", "-A", cwd=dest)
    git("commit", "--quiet", "-m", "local edit", cwd=dest)

    result = run(
        [str(installed_client.console), "update", "--degraded", str(dest)],
        dest,
        env=installed_client.env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "conflicted" in result.stdout.lower()
    assert readme.read_text(encoding="utf-8") == diverged

    # README.md, the conflicted target, is left byte-for-byte untouched;
    # only .forge/generation.json changes -- rewritten with
    # `degraded_reason` set, and staged by `stage_result` as every
    # `--degraded` run does regardless of whether any target's content
    # actually changed.
    status = git("status", "--porcelain", cwd=dest)
    assert "README.md" not in status
    assert "generation.json" in status


def test_recipe_rollback_restores_a_bad_update(
    installed_client: InstalledClient,
) -> None:
    """The documented recovery recipe (`docs/user-guide/updates.md` and
    `migration.md`, CF-22.02, ADR 0053) genuinely restores a project left
    mid-update in each state an update can leave, run against a real
    installed-console-generated repository -- not a hand-built fixture.

    The states: an unstaged edit plus an untracked file; a fully **staged**
    update (what a completed update always leaves); and a rename applied with
    `git mv`, which stages at once. The previous recipe, `git restore . && git
    clean -fd`, restores from the index and recovered neither staged state.
    One project serves all three because each recovery must return it to the
    generated baseline, and an ignored file the user owns must survive every one.

    `tests/test_update_recovery.py` drives the update's own functions through
    the same states; this is the installed-console half.
    """
    dest = installed_client.root / "recipe" / "rollback-project"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated = run(
        [str(installed_client.console), *_engine_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "generate the project to roll back")

    readme = dest / "README.md"
    original = readme.read_text(encoding="utf-8")
    user_file = dest / "__pycache__" / "user-data.pyc"
    user_file.parent.mkdir(exist_ok=True)
    user_file.write_bytes(b"owned by the user\n")
    git("check-ignore", "-q", "__pycache__/user-data.pyc", cwd=dest)  # precondition
    assert git("status", "--porcelain", cwd=dest).strip() == ""

    def unstaged() -> None:
        readme.write_text(original + "merged content\n", encoding="utf-8")
        (dest / "mid-update.txt").write_text("new content\n", encoding="utf-8")

    def staged() -> None:
        readme.write_text(original + "merged content\n", encoding="utf-8")
        (dest / "added-by-update.txt").write_text("new content\n", encoding="utf-8")
        git("add", "-A", cwd=dest)  # `stage_result`

    def renamed() -> None:
        git("mv", "README.md", "README-moved.md", cwd=dest)  # `apply_renames`
        (dest / "mid-update.txt").write_text("new content\n", encoding="utf-8")

    for name, leave_state in (
        ("unstaged", unstaged),
        ("staged", staged),
        ("renamed", renamed),
    ):
        leave_state()
        assert git("status", "--porcelain", cwd=dest).strip() != "", name

        # The documented recipe, from the repository root.
        git(*RESTORE_ARGV[1:], cwd=dest)
        untracked = git(*CLEAN_PREVIEW_ARGV[1:], cwd=dest)
        assert "__pycache__" not in untracked, name  # ignored: never a candidate
        git(*CLEAN_ARGV[1:], cwd=dest)

        assert readme.read_text(encoding="utf-8") == original, name
        assert not (dest / "README-moved.md").exists(), name
        assert not (dest / "mid-update.txt").exists(), name
        assert not (dest / "added-by-update.txt").exists(), name
        assert user_file.read_bytes() == b"owned by the user\n", name
        assert git("status", "--porcelain", cwd=dest).strip() == "", name


def test_boundary_incompatible_engine_via_engine_source_writes_nothing(
    installed_client: InstalledClient, _forge_template_reachable: None
) -> None:
    """An `--engine-source` override pinned to a real, permanently
    out-of-range `forge-template` release exits `3` with nothing written --
    proven through an installed console for the first time. Existing
    coverage (`tests/test_engine_source.py`) is entirely `CliRunner`-level
    with a monkeypatched `negotiate`; this drives the real provisioning
    machinery end to end.
    """
    dest = installed_client.root / "boundary" / "engine-source-out-of-range"
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            str(installed_client.console),
            "new",
            "Boundary Engine Source Trial",
            "--engine-source",
            "https://github.com/Sandsy09/forge-template",
            "--engine-ref",
            "v0.3.0",
            "--yes",
            "--path",
            str(dest),
        ],
        dest.parent,
        env=installed_client.env,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert not dest.exists()


def test_boundary_missing_engine_update_fails_closed_at_exit_3(
    installed_client: InstalledClient,
    candidate_wheel: Path,
    e2e_child_env: dict[str, str],
) -> None:
    """The no-engine boundary, re-asserted at this suite's own `update`
    route so `-k boundary` selects a test here specifically -- the bulk of
    this proof (`new`-side, `doctor --json`) lives in
    `tests/test_e2e_installed_rollout.py`
    (`test_engineless_new_fails_closed_at_exit_3`,
    `test_engineless_doctor_json_reports_the_absent_engine`), mapped onto
    this row in `docs/engine-cutover-validation.md` rather than repeated
    here.
    """
    dest = installed_client.root / "boundary" / "no-engine-update-project"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated = run(
        [str(installed_client.console), *_engine_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "generate the project to update")
    before = visible_files(dest)

    with build_client(
        candidate_wheel, e2e_child_env, omit="forge-template"
    ) as engineless_client:
        result = run(
            [str(engineless_client.console), "update", str(dest)],
            dest,
            env=engineless_client.env,
        )

    assert result.returncode == 3, result.stdout + result.stderr
    assert visible_files(dest) == before


# --------------------------------------------------------------------------
# CF-18.06: documented recipes, exercised through the installed console
# (acceptance rows 228-229)
# --------------------------------------------------------------------------


def test_recipe_diagnose_with_doctor(installed_client: InstalledClient) -> None:
    """`docs/user-guide/updates.md`'s "Diagnose problems" recipe --
    `--version`, `doctor`, `doctor --json` -- runs cleanly through the
    installed console.
    """
    version = run(
        [str(installed_client.console), "--version"],
        installed_client.root,
        env=installed_client.env,
    )
    assert_success(version, "create-forge --version")

    doctor = run(
        [str(installed_client.console), "doctor"],
        installed_client.root,
        env=installed_client.env,
    )
    # doctor's overall exit status depends on unrelated environment checks
    # (e.g. git identity) -- see test_legacy_extra_installs_copier's own
    # docstring; only the command's own successful execution matters here.
    assert doctor.returncode in (0, 1), doctor.stdout + doctor.stderr

    doctor_json = run(
        [str(installed_client.console), "doctor", "--json"],
        installed_client.root,
        env=installed_client.env,
    )
    json.loads(doctor_json.stdout)  # must be valid JSON regardless of ok/exit


def test_recipe_pin_back_to_0_3_x(
    e2e_child_env: dict[str, str], tmp_path: Path
) -> None:
    """The `0.3.x` pin-back recipe (`docs/user-guide/migration.md`) --
    `uv tool install "create-forge==0.3.2"` -- still resolves and runs from
    PyPI after the cutover, the 90-day support window
    (`docs/engine-cutover-acceptance.md`) promises. Proven with a real
    install rather than asserted only as doc text; skips, not fails, when
    PyPI is unreachable.
    """
    root = tmp_path / "pin-back"
    root.mkdir()
    tool_dir = root / "tools"
    bin_dir = root / "bin"
    install_env = dict(e2e_child_env)
    install_env["UV_TOOL_DIR"] = str(tool_dir)
    install_env["UV_TOOL_BIN_DIR"] = str(bin_dir)

    installed = run(
        ["uv", "tool", "install", "create-forge==0.3.2"], root, env=install_env
    )
    if installed.returncode != 0:
        pytest.skip(
            f"could not resolve create-forge==0.3.2 from PyPI: {installed.stderr}"
        )

    console = _tool_bin_script(bin_dir)
    run_env = _isolated_tool_env(e2e_child_env, root / "config")
    version = run([str(console), "--version"], root, env=run_env)
    assert_success(version, "pinned create-forge==0.3.2 --version")
    assert version.stdout.strip() == "0.3.2"
