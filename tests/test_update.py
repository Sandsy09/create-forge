"""runner.update() against a local fixture template -- no network.

Regression coverage for #23: `update()` called Copier's `run_update` without
`overwrite=True`, so every invocation failed with
"Enable overwrite to update a subproject." before doing anything at all.

The fixture template is built as a real git repo with two tags rather than
mocked, and projects under test are generated via `runner.scaffold()` --
invariant 4 in CLAUDE.md reserves Copier's Python API for runner.py, so these
tests dogfood the real path instead of calling `copier` directly.

The one real network update -- against forge-template's actual v0.1.0/v0.1.1
tags -- lives in test_update_network.py, not here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from plumbum.commands.processes import ProcessExecutionError

from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold, update
from tests.legacy_template import build_tagged_template
from tests.legacy_template import commit as _commit
from tests.legacy_template import git as _git
from tests.legacy_template import init_repo as _init_repo
from tests.legacy_template import visible_files as _visible_files
from tests.process import run_text


@pytest.fixture(autouse=True)
def _isolated_copier_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never read the developer's real ~/.config/copier/settings.yml.

    Without this, a machine with e.g. `trust` entries configured could behave
    differently under test than a fresh CI runner -- the same reasoning as
    test_cli.py's _isolated_config fixture, applied to Copier's own settings.
    """
    monkeypatch.setenv(
        "COPIER_SETTINGS_PATH", str(tmp_path / "unused-copier-settings.yml")
    )
    monkeypatch.setenv("COPIER_CACHE_DIR", str(tmp_path / "copier-cache"))


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway Copier template, tagged v1.0.0 and v1.1.0.

    Built by `tests/legacy_template.py`, shared with
    `tests/test_e2e_installed_cutover.py` (CF-18.05) -- see that module's
    docstring for the non-obvious constraints (no `.git` suffix, no
    `file://` URL, `core.autocrlf=false`).
    """
    return build_tagged_template(tmp_path_factory.mktemp("template"))


def _scaffold_at(template_path: Path, dst: Path, ref: str) -> None:
    scaffold(
        ScaffoldRequest(
            src=str(template_path), dst=dst, data={"greeting": "world"}, vcs_ref=ref
        )
    )


def _prepare_project(template_path: Path, tmp_path: Path) -> Path:
    """Scaffold at v1.0.0 and commit it -- the state `update()` starts from."""
    dst = tmp_path / "project"
    _scaffold_at(template_path, dst, "v1.0.0")
    _init_repo(dst)
    _commit(dst, "initial scaffold")
    return dst


def test_update_applies_template_changes(template: Path, tmp_path: Path) -> None:
    """This is the test that fails with "Enable overwrite to update a
    subproject." against unmodified runner.py -- the literal bug in #23."""
    project = _prepare_project(template, tmp_path)
    assert "v1" in (project / "README.md").read_text(encoding="utf-8")

    update(project, vcs_ref="v1.1.0")

    assert "v2" in (project / "README.md").read_text(encoding="utf-8")


def test_documented_local_source_through_console(
    template: Path,
    tmp_path: Path,
    create_forge_command: str,
    e2e_child_env: dict[str, str],
) -> None:
    """Exercise the guide's local --template-url/--ref HEAD recipe without network."""
    dst = tmp_path / "local-trial"
    result = run_text(
        [
            create_forge_command,
            "new",
            "--legacy",
            "Local Template Trial",
            "--yes",
            "--template-url",
            str(template),
            "--ref",
            "HEAD",
            "--path",
            str(dst),
        ],
        env=e2e_child_env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Template code will be executed" in result.stderr
    assert "v2" in (dst / "README.md").read_text(encoding="utf-8")
    assert yaml.safe_load((dst / ".copier-answers.yml").read_text(encoding="utf-8"))[
        "_src_path"
    ] == str(template)


def test_update_dry_run_changes_nothing_before_a_real_update(
    template: Path, tmp_path: Path
) -> None:
    project = _prepare_project(template, tmp_path)
    before_files = _visible_files(project)
    before_head = _git("rev-parse", "HEAD", cwd=project)
    before_index = _git("write-tree", cwd=project)
    before_status = _git("status", "--porcelain", cwd=project)

    update(project, vcs_ref="v1.1.0", dry_run=True)

    assert _visible_files(project) == before_files
    assert _git("rev-parse", "HEAD", cwd=project) == before_head
    assert _git("write-tree", cwd=project) == before_index
    assert _git("status", "--porcelain", cwd=project) == before_status

    update(project, vcs_ref="v1.1.0")

    assert "v2" in (project / "README.md").read_text(encoding="utf-8")


def test_update_explains_a_real_missing_template_without_changing_the_project(
    template: Path, tmp_path: Path
) -> None:
    project = _prepare_project(template, tmp_path)
    answers_path = project / ".copier-answers.yml"
    answers = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
    missing_source = tmp_path / "missing-template.git"
    answers["_src_path"] = str(missing_source)
    answers_path.write_text(yaml.safe_dump(answers, sort_keys=False), encoding="utf-8")
    _commit(project, "point at missing template")

    before_files = _visible_files(project)
    before_head = _git("rev-parse", "HEAD", cwd=project)
    before_index = _git("write-tree", cwd=project)
    before_status = _git("status", "--porcelain", cwd=project)

    with pytest.raises(
        ScaffoldError, match="Git could not complete the template operation"
    ) as raised:
        update(project, vcs_ref="HEAD")

    assert isinstance(raised.value.__cause__, ProcessExecutionError)
    assert str(missing_source) not in str(raised.value)
    assert "Unexpected exit code" not in str(raised.value)
    assert _visible_files(project) == before_files
    assert _git("rev-parse", "HEAD", cwd=project) == before_head
    assert _git("write-tree", cwd=project) == before_index
    assert _git("status", "--porcelain", cwd=project) == before_status


def test_update_preserves_local_edits(template: Path, tmp_path: Path) -> None:
    """The README's headline claim: "Local edits survive; template changes
    arrive." notes.txt is untouched by the template between v1.0.0 and
    v1.1.0, so Copier's merge should carry the local edit through untouched."""
    project = _prepare_project(template, tmp_path)
    notes = project / "notes.txt"
    notes.write_text("my own notes\n", encoding="utf-8")
    _commit(project, "local edit")

    update(project, vcs_ref="v1.1.0")

    assert notes.read_text(encoding="utf-8") == "my own notes\n"


def test_update_rejects_a_dirty_working_tree(template: Path, tmp_path: Path) -> None:
    """Regression for the dead _explain() branch: this asserts on _explain()'s
    own wording, not Copier's raw message (which coincidentally also contains
    "stash") -- so this only passes if the translation is actually reached,
    not merely present in the source."""
    project = _prepare_project(template, tmp_path)
    (project / "README.md").write_text("uncommitted change", encoding="utf-8")

    with pytest.raises(ScaffoldError, match="clean working tree"):
        update(project, vcs_ref="v1.1.0")


def test_update_without_an_answers_file_is_explained(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _init_repo(project)
    (project / "file.txt").write_text("x", encoding="utf-8")
    _commit(project, "initial")

    with pytest.raises(ScaffoldError, match="copier-answers"):
        update(project)


def test_update_of_a_non_git_project_is_explained(
    template: Path, tmp_path: Path
) -> None:
    """Scaffolded but never git-initialised -- the other newly-reachable
    _explain() branch. Asserts on the translation's own wording, since
    Copier's raw message also happens to mention "git-tracked"."""
    dst = tmp_path / "project"
    _scaffold_at(template, dst, "v1.0.0")

    with pytest.raises(ScaffoldError, match="git init"):
        update(dst, vcs_ref="v1.1.0")
