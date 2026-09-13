"""Filesystem orchestration shared by the Copier and engine generation paths.

Deliberately engine-free: nothing here imports `forge_template`, not even
under `TYPE_CHECKING`. That keeps this module in the wheel and in the fast
test suite with no optional `engine` extra (ADR 0018) installed, and lets it
serve both `runner.scaffold()` (Copier writes straight to the destination; this
module only cleans up after a failure) and `pipeline.finalise_generation_request()`
(the engine path; this module stages and atomically finalises). See
[ADR 0015](../../docs/adr/0015-staged-filesystem-generation.md),
[ADR 0021](../../docs/adr/0021-client-finalises-engine-lockfiles.md), and the
canonical [filesystem generation contract](../../docs/filesystem-generation.md)
for why the two paths differ and what each guarantees.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

_STAGING_PREFIX = ".create-forge-"


class StagingError(Exception):
    """A filesystem operation failed in a way the user can act on."""


class DestinationConflictError(StagingError):
    """The destination already exists and is not empty."""


def ensure_available(dst: Path) -> None:
    """Reject a destination that already exists and has content.

    Cheap and side-effect free -- callers run this before any compatibility
    check or write, so an obvious conflict is reported before anything else
    is attempted.
    """
    if dst.exists() and any(dst.iterdir()):
        msg = f"{dst} already exists and is not empty"
        raise DestinationConflictError(msg)


# Copier's `copier.yml` `_exclude` list, minus `copier.yml` itself (which has
# no engine analogue -- ADR 0045) and `.git` (folded into `_is_denylisted`
# below, since it is now load-bearing rather than merely hygienic: `git init`
# runs at `dst` after the rename, so a rendered `.git/hooks/pre-commit` would
# survive re-initialisation and then execute). `PurePosixPath.match` applies
# each pattern to the whole target, so `*.py[co]` and `__pycache__` catch a
# match at any depth, not only at the root.
_DENYLISTED_PATTERNS = ("*.py[co]", "__pycache__", "__pycache__/*", "~*", ".DS_Store")


def _is_denylisted(posix_target: PurePosixPath) -> bool:
    """Whether `posix_target` falls under the engine's `_exclude` refusal.

    A `.git` path segment anywhere is refused outright; the rest are Copier's
    hygiene patterns, matched against the whole target so they catch a nested
    path (`sub/__pycache__/mod.pyc`) the same as a root-level one.
    """
    if ".git" in posix_target.parts:
        return True
    return any(posix_target.match(pattern) for pattern in _DENYLISTED_PATTERNS)


def _safe_relative_path(root: Path, target: str) -> Path:
    """Resolve one project-relative target under `root`, refusing escapes.

    Targets are engine-owned strings using forward slashes (`RenderedFile`
    documents them as project-relative). `PurePosixPath` parses them
    platform-independently before `Path` joins them, so a target containing
    backslashes is treated as a literal filename component, never as a
    Windows separator.
    """
    posix_target = PurePosixPath(target)
    if posix_target.is_absolute() or posix_target.drive:
        msg = f"refusing to write outside the staging directory: {target!r}"
        raise StagingError(msg)
    if ".." in posix_target.parts:
        msg = f"refusing to write outside the staging directory: {target!r}"
        raise StagingError(msg)
    if _is_denylisted(posix_target):
        msg = f"refusing to write an excluded target: {target!r}"
        raise StagingError(msg)

    resolved_root = root.resolve()
    destination = (root / Path(*posix_target.parts)).resolve()
    if destination != resolved_root and resolved_root not in destination.parents:
        msg = f"refusing to write outside the staging directory: {target!r}"
        raise StagingError(msg)
    return destination


def write_files(root: Path, files: Iterable[tuple[str, bytes]]) -> None:
    """Write each (target, content) pair under `root`, creating parents.

    Every target is validated before anything is written -- an absolute
    path, a drive-qualified path, or a `..` segment anywhere in a single
    target aborts the whole call with nothing written by it.
    """
    resolved: list[tuple[Path, bytes]] = [
        (_safe_relative_path(root, target), content) for target, content in files
    ]
    for path, content in resolved:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(content)
        except OSError as exc:
            msg = f"could not write {path}: {exc}"
            raise StagingError(msg) from exc


def create_uv_lock(root: Path) -> None:
    """Resolve the staged project's committed lockfile before finalisation.

    The engine render is deliberately side-effect free, so ``uv.lock`` is a
    client-owned finalisation artefact. Run uv without a shell and translate
    launch or resolution failures into the staging error surface; the
    surrounding :func:`staged` context then removes the incomplete tree and
    leaves the destination untouched.
    """
    command = ["uv", "lock", "--directory", str(root)]
    try:
        result = subprocess.run(  # noqa: S603 - reviewed fixed executable
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = (
            "could not create uv.lock because the uv executable is unavailable; "
            "install uv>=0.12,<0.13 and retry"
        )
        raise StagingError(msg) from exc
    except OSError as exc:
        msg = f"could not launch uv to create uv.lock: {exc}"
        raise StagingError(msg) from exc

    if result.returncode != 0:
        msg = (
            f"uv lock failed with exit status {result.returncode}; check the "
            "project's declared dependencies and package-index access, then retry"
        )
        raise StagingError(msg)


def _on_rm_error(func: object, path: str, exc_info: object) -> None:
    """`shutil.rmtree` error handler: clear read-only and retry once.

    Accepted as both 3.12+'s `onexc` and 3.11's `onerror` -- both call the
    handler with three positional arguments; the third (`exc_info`) is
    unused by either signature this implements.
    """
    del exc_info
    target = Path(path)
    target.chmod(0o700)
    if callable(func):
        func(path)


def remove_tree(path: Path) -> None:
    """Best-effort recursive removal that clears read-only files first.

    Never raises: a failed cleanup must not mask the original error that
    triggered it, so a residual directory is reported as a warning instead.
    Public rather than module-private: `engine_source.py`'s ephemeral
    `--engine-source` environment (ADR 0044) needs the same
    read-only-clearing, never-raises removal Windows requires for a
    just-installed package's read-only files.
    """
    if not path.exists():
        return
    try:
        try:
            # `onexc` only exists from Python 3.12; mypy is pinned to the 3.11
            # stub (pyproject.toml's python_version), so this call needs an
            # explicit ignore regardless of the interpreter mypy itself runs
            # under.
            shutil.rmtree(path, onexc=_on_rm_error)  # type: ignore[call-arg]
        except TypeError:
            shutil.rmtree(path, onerror=_on_rm_error)
    except OSError as exc:
        warnings.warn(f"could not remove {path}: {exc}", RuntimeWarning, stacklevel=2)


@contextlib.contextmanager
def staged(dst: Path) -> Iterator[Path]:
    """Yield a staging directory adjacent to `dst`; finalise by atomic rename.

    The staging directory is created next to `dst` with `tempfile.mkdtemp`,
    not under the system temp directory -- same-volume placement is what
    makes the finalising `Path.rename` an atomic directory rename on both
    NTFS and POSIX rather than a copy. There is deliberately no cross-volume
    copy fallback: that would silently trade the atomicity guarantee for
    availability, so a cross-volume destination fails instead.

    On success, an existing *empty* `dst` is removed first -- `os.rename`
    will not replace a directory on Windows. On any exception, the staging
    tree is removed and the original error propagates; `dst` is left exactly
    as it was found.
    """
    ensure_available(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=dst.parent))

    try:
        yield staging_dir
        if dst.exists():
            dst.rmdir()
        try:
            staging_dir.rename(dst)
        except OSError as exc:
            msg = f"could not move {staging_dir} into place at {dst}: {exc}"
            raise StagingError(msg) from exc
    except BaseException:
        remove_tree(staging_dir)
        raise


@contextlib.contextmanager
def discard_on_failure(dst: Path) -> Iterator[None]:
    """Remove `dst` on failure, but only if this call is what created it.

    Used around the Copier path, which writes straight to `dst` and cannot
    safely be staged: templates run `_tasks` (`uv sync`, `pre-commit
    install`) that bake `dst`'s absolute path into `.venv/pyvenv.cfg`,
    console-script shims, and `.git/hooks/pre-commit`. Renaming a completed
    Copier output afterward would silently break all three, so this context
    manager only ever cleans up a failure at the path Copier already used --
    it never stages or moves anything.
    """
    pre_existing = dst.exists()
    try:
        yield
    except BaseException:
        if not pre_existing:
            remove_tree(dst)
        raise
