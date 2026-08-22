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

import subprocess
from pathlib import Path

import pytest

from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold, update


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


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _init_repo(path: Path) -> None:
    """A git repo with a fixed identity and CRLF normalisation off.

    CI runners have no global git identity -- the same reason test_cli.py
    monkeypatches _git_config. core.autocrlf=false matters on Windows: with
    it on, a freshly committed file can immediately read back as dirty from
    `git status --porcelain`, tripping Copier's own dirty-tree guard before
    the test does anything.
    """
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "--quiet", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "core.autocrlf", "false", cwd=path)


def _commit(path: Path, message: str) -> None:
    _git("add", "-A", cwd=path)
    _git("commit", "--quiet", "-m", message, cwd=path)


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A throwaway Copier template, tagged v1.0.0 and v1.1.0.

    Deliberately an absolute path with no `.git` suffix and not a `file://`
    URL: Copier's `get_repo()` only recognises a local directory that is
    itself a git repo root -- a `file://` URL falls through to
    "Local template must be a directory."
    """
    root = tmp_path_factory.mktemp("template")
    _init_repo(root)

    (root / "copier.yml").write_text(
        "greeting:\n  type: str\n  default: hello\n", encoding="utf-8"
    )
    (root / ".copier-answers.yml.jinja").write_text(
        "{{ _copier_answers|to_nice_yaml }}\n", encoding="utf-8"
    )
    (root / "README.md.jinja").write_text(
        "Hello, {{ greeting }}! v1\n", encoding="utf-8"
    )
    (root / "notes.txt.jinja").write_text("original notes\n", encoding="utf-8")
    _commit(root, "v1")
    _git("tag", "v1.0.0", cwd=root)

    (root / "README.md.jinja").write_text(
        "Hello, {{ greeting }}! v2\n", encoding="utf-8"
    )
    _commit(root, "v2")
    _git("tag", "v1.1.0", cwd=root)

    return root


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
