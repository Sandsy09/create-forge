"""Post-rename Git and pre-commit lifecycle for the engine `new` path.

This is the engine analogue of `forge-template`'s `copier.yml` `_tasks` --
`git init`, an initial commit, and conditional hook installation -- run by
`create-forge` rather than the provider (FT-ROADMAP-01-EX-01, the engine
spawns no process). ADR 0041 (CF-16.02) decided the rules; ADR 0045 (CF-18.03)
records this module's boundary and its warn-and-continue failure posture. See
the canonical engine project lifecycle contract,
`docs/engine-project-lifecycle.md`.

Deliberately engine-free, like `staging.py`, `sources.py`, and
`engine_source.py`: nothing here imports `forge_template`, not even under
`TYPE_CHECKING` (`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard
covers this module for exactly that reason). `pipeline.finalise_files` calls
`finalise_project` only after the atomic rename succeeds -- `git init` bakes
`dst`'s absolute path into `.git/hooks/`, the same reason the direct-Copier
`_tasks` cannot run in a staging directory (`docs/filesystem-generation.md`).

`finalise_project` never raises: a render is sound the moment it is on disk,
and the convenience steps here are not worth discarding it for (ADR 0041 rule
4). Each failure becomes one warning naming the exact manual command that
finishes the step; the caller (`cli.py`) prints these and `new` still exits
`0`. No warning ever includes raw subprocess stdout/stderr -- mirroring
`staging.create_uv_lock`'s and `engine_source.py`'s own rule, since a `uv run`
failure can carry package-index credentials.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_COMMIT_MESSAGE = "feat: initial scaffold from template"
_PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


def _hint(command: str) -> str:
    return f"finish it yourself: {command}"


def _run_git(args: Sequence[str], dst: Path) -> str | None:
    """Run one `git` lifecycle step at `dst`. `None` on success."""
    command = ["git", *args]
    hint_command = " ".join(["git", "-C", str(dst), *args])
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
            command,
            cwd=dst,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return f"git is not on PATH; install git, then {_hint(hint_command)}"
    except OSError as exc:
        return f"could not launch git: {exc}; {_hint(hint_command)}"
    if result.returncode != 0:
        return f"`git {' '.join(args)}` failed; {_hint(hint_command)}"
    return None


def _run_pre_commit_install(dst: Path) -> str | None:
    """Run `pre-commit install --install-hooks` in `dst`'s own environment.

    `uv run --directory <dst>` implicitly creates/syncs `.venv` from the
    staging-created `uv.lock` before invoking `pre-commit` -- one command,
    the same effective outcome as the direct-Copier `_tasks`' separate
    `uv sync --all-groups` + `uv run pre-commit install`.
    """
    args = [
        "uv",
        "run",
        "--directory",
        str(dst),
        "pre-commit",
        "install",
        "--install-hooks",
    ]
    hint_command = " ".join(args)
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
            args,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return f"uv is not on PATH; install uv>=0.12,<0.13, then {_hint(hint_command)}"
    except OSError as exc:
        return f"could not launch uv: {exc}; {_hint(hint_command)}"
    if result.returncode != 0:
        return f"pre-commit hook installation failed; {_hint(hint_command)}"
    return None


def finalise_project(dst: Path) -> tuple[str, ...]:
    """Run the engine `new` post-rename lifecycle at the final destination.

    `git init` + `git add -A` + one initial commit, then
    `pre-commit install --install-hooks` only if `dst` contains a rendered
    `.pre-commit-config.yaml` -- the client checks for the rendered file it
    already holds, never a component id (`docs/component-selection.md`'s
    no-allowlist rule). A `git init` failure skips every later step, since
    none of them can succeed without a repository; a failed `git add` skips
    only the commit, since hook installation needs `.git/` but not a commit.
    Returns every warning collected, in the order the steps ran; an empty
    tuple means every step succeeded.
    """
    warnings: list[str] = []

    init_failure = _run_git(["init", "--initial-branch=main"], dst)
    if init_failure is not None:
        warnings.append(init_failure)
        return tuple(warnings)

    add_failure = _run_git(["add", "-A"], dst)
    if add_failure is not None:
        warnings.append(add_failure)
    else:
        commit_failure = _run_git(["commit", "--no-verify", "-m", _COMMIT_MESSAGE], dst)
        if commit_failure is not None:
            warnings.append(commit_failure)

    if (dst / _PRE_COMMIT_CONFIG).exists():
        hook_failure = _run_pre_commit_install(dst)
        if hook_failure is not None:
            warnings.append(hook_failure)

    return tuple(warnings)
