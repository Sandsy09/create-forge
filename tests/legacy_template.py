"""A throwaway, real, git-backed Copier template with two PEP440 tags.

Shared by `tests/test_update.py` (offline, fast suite) and
`tests/test_e2e_installed_cutover.py` (CF-18.05, through the installed
console script) -- both need "a real local tagged Copier template" as their
update-route fixture, and the non-obvious constraints (an absolute path with
no `.git` suffix, `core.autocrlf=false`) are worth solving exactly once.

Like `tests/installed_client.py`, this is a support module, not a test
module: it defines no tests of its own and is imported by the suites that
share it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TEMPLATE_FIRST_TAG = "v1.0.0"
TEMPLATE_SECOND_TAG = "v1.1.0"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout


def init_repo(path: Path) -> None:
    """A git repo with a fixed identity and CRLF normalisation off.

    CI runners have no global git identity -- the same reason test_cli.py
    monkeypatches `_git_config`. `core.autocrlf=false` matters on Windows:
    with it on, a freshly committed file can immediately read back as dirty
    from `git status --porcelain`, tripping Copier's own dirty-tree guard
    before the test does anything.
    """
    path.mkdir(parents=True, exist_ok=True)
    git("init", "--quiet", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "core.autocrlf", "false", cwd=path)


def commit(path: Path, message: str) -> None:
    git("add", "-A", cwd=path)
    git("commit", "--quiet", "-m", message, cwd=path)


def build_tagged_template(root: Path) -> Path:
    """A throwaway Copier template, tagged `v1.0.0` and `v1.1.0`.

    Deliberately an absolute path with no `.git` suffix and not a `file://`
    URL: Copier's `get_repo()` only recognises a local directory that is
    itself a git repo root -- a `file://` URL falls through to "Local
    template must be a directory." `v1.1.0` both changes an existing file
    (`README.md.jinja`) and adds a new one (`CHANGELOG.md.jinja`), so a
    consumer can exercise both a merged change and a newly-appearing target.
    """
    init_repo(root)

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
    commit(root, "v1")
    git("tag", TEMPLATE_FIRST_TAG, cwd=root)

    (root / "README.md.jinja").write_text(
        "Hello, {{ greeting }}! v2\n", encoding="utf-8"
    )
    (root / "CHANGELOG.md.jinja").write_text("v2 added this file\n", encoding="utf-8")
    commit(root, "v2")
    git("tag", TEMPLATE_SECOND_TAG, cwd=root)

    return root


def visible_files(project: Path) -> dict[str, bytes]:
    """Snapshot every project file except Git's internal object database."""
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(project).parts
    }
