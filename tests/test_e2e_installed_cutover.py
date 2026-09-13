"""Installed-candidate CF-18.05 evidence: the retained legacy Copier route
and the rejected pre-cutover `--engine-preview` transition.

`docs/engine-cutover-acceptance.md`'s accepted matrix names this module as
CF-18.05's own evidence (`-k legacy`, rows 204/205) alongside the
preview-project transition row (212, proved at the unit/CLI level by
`tests/test_update_routing.py -k preview`; this module's own preview test
proves the same rejection survives the installed console). ADR 0047 records
why the file is created here rather than by CF-18.06, which extends it to the
rest of the installed cutover acceptance matrix.

Scoped to what only an installed wheel can prove -- `create-forge[legacy]`
actually resolving `copier`, and `--legacy` failing without it. The offline
local-tagged Copier coverage (dry-run non-mutation, local-edit preservation,
a missing-source failure) already lives in `tests/test_update.py`, reusing
the same `tests/legacy_template.py` harness this module also reuses.
"""

from __future__ import annotations

import json
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
    init_repo,
    visible_files,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.e2e


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


def _read_answers(project: Path) -> dict[str, object]:
    data: dict[str, object] = yaml.safe_load(
        (project / ".copier-answers.yml").read_text(encoding="utf-8")
    )
    return data


# --------------------------------------------------------------------------
# the retained legacy Copier route (acceptance rows 204-205)
# --------------------------------------------------------------------------


def test_legacy_extra_installs_copier(installed_client: InstalledClient) -> None:
    """`create-forge[legacy]` resolves `copier` -- read back through
    `doctor --json`'s own diagnostic field rather than probing the venv
    directly, since that field is the client's own documented contract
    (docs/engine-resolution.md)."""
    result = run(
        [str(installed_client.console), "doctor", "--json"],
        installed_client.root,
        env=installed_client.env,
    )
    assert_success(result, "doctor --json")
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
