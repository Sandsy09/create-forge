"""Thin wrapper over Copier's Python API.

Copier's Python API is public but not versioned as strictly as its CLI, so this
module is the single place that touches it. Pin copier narrowly in
pyproject.toml (`copier>=9.16,<10`) and this file is the only thing that
needs attention on a major bump.

`copier_cache_location` also models one piece of documented Copier behaviour --
where the git-mirror cache lives and how `COPIER_CACHE_DIR` overrides it, added
in Copier 9.16 -- so `doctor` can report it and a cache failure can be
explained instead of misattributed to the network. `tests/test_copier_cache.py`
pins that model against Copier's own private resolver so a drift fails CI.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from copier import run_copy, run_update
from copier.errors import CopierError
from platformdirs import user_cache_dir
from plumbum.commands.processes import ProcessExecutionError

from create_forge import staging
from create_forge.sources import SourceError, validate_source

if TYPE_CHECKING:
    from collections.abc import Mapping


class ScaffoldError(Exception):
    """A failure the user can act on, already phrased for display."""


_PROCESS_FAILURE_MESSAGE = (
    "Git could not complete the template operation.\n"
    "  Check the template URL and --ref, your network connection, repository "
    "access, and Git credentials, then retry."
)

COPIER_CACHE_ENV_VAR = "COPIER_CACHE_DIR"

_CACHE_FAILURE_SIGNAL = "not a git repository"


@dataclass(frozen=True, slots=True)
class CacheLocation:
    """Where Copier stores its git-mirror cache, and how it was chosen."""

    path: Path
    overridden: bool
    """True when COPIER_CACHE_DIR selected the path, not the default."""


@dataclass(frozen=True, slots=True)
class CacheProbe:
    """Whether Copier's cache directory exists and accepts writes."""

    exists: bool
    writable: bool


def copier_cache_location() -> CacheLocation:
    """Resolve Copier's cache directory by its own documented rule.

    Copier uses `COPIER_CACHE_DIR` verbatim when it is set and non-empty,
    otherwise `<platformdirs user cache for "copier">/git`. This mirrors
    `copier._vcs._get_cache_dir`, which is private and has moved between
    supported releases; `tests/test_copier_cache.py` pins the two together so
    a drift fails CI rather than silently misreporting in `doctor`.
    """
    override = os.environ.get(COPIER_CACHE_ENV_VAR)
    if override:
        return CacheLocation(path=Path(override), overridden=True)
    default = Path(user_cache_dir("copier", appauthor=False)) / "git"
    return CacheLocation(path=default, overridden=False)


def _write_probe(directory: Path) -> None:
    """Create and immediately remove a uniquely named file in `directory`."""
    fd, name = tempfile.mkstemp(dir=directory, prefix=".create-forge-probe-")
    os.close(fd)
    Path(name).unlink(missing_ok=True)


def cache_probe(location: CacheLocation) -> CacheProbe:
    """Report whether Copier could use `location` without changing it.

    Never creates the cache directory: when it is absent, the deepest existing
    ancestor is probed instead, because that is what Copier's own
    `mirror.parent.mkdir(parents=True)` writes into. The probe creates a
    uniquely named file and deletes it immediately -- it never reads, writes,
    or lists a `<sha>.git` mirror, and leaves nothing persistent behind.

    `os.access` is deliberately not used: on Windows it ignores ACLs and
    reports a locked-down corporate cache directory as writable, which is the
    exact condition this probe exists to catch.
    """
    exists = location.path.is_dir()
    probe_dir = location.path
    while not probe_dir.is_dir():
        if probe_dir.parent == probe_dir:
            return CacheProbe(exists=exists, writable=False)
        probe_dir = probe_dir.parent
    try:
        _write_probe(probe_dir)
    except OSError:
        return CacheProbe(exists=exists, writable=False)
    return CacheProbe(exists=exists, writable=True)


@dataclass(frozen=True, slots=True)
class ScaffoldRequest:
    """Everything needed to render a template."""

    src: str
    dst: Path
    data: Mapping[str, object]
    vcs_ref: str | None = None
    """None means Copier resolves the latest PEP440 tag."""

    dry_run: bool = False


def scaffold(request: ScaffoldRequest) -> None:
    """Render a template into a new directory.

    `unsafe=True` is the API equivalent of `--trust` and is required because the
    templates declare `_tasks`. This is a deliberate decision: the registry only
    ever points at first-party repositories, so the code being trusted is code
    the same team publishes. Never widen the registry to arbitrary URLs without
    revisiting this.
    """
    try:
        validate_source(request.src)
    except SourceError as exc:
        raise ScaffoldError(str(exc)) from None
    try:
        staging.ensure_available(request.dst)
    except staging.DestinationConflictError as exc:
        raise ScaffoldError(str(exc)) from exc

    # Copier cannot be staged and moved into place the way the engine path
    # is (ADR 0015): its templates declare `_tasks` that run `uv sync` and
    # `pre-commit install`, baking dst's absolute path into `.venv/pyvenv.cfg`,
    # console-script shims, and `.git/hooks/pre-commit`. Renaming a completed
    # output afterward would silently break all three. So this only cleans up
    # a failure at the path Copier already wrote to -- it never stages.
    with staging.discard_on_failure(request.dst):
        try:
            run_copy(
                src_path=request.src,
                dst_path=request.dst,
                data=dict(request.data),
                vcs_ref=request.vcs_ref,
                # Anything not answered by the CLI falls back to the
                # template's own default, so copier.yml stays the source of
                # truth.
                defaults=True,
                unsafe=True,
                quiet=True,
                pretend=request.dry_run,
            )
        except (CopierError, ProcessExecutionError) as exc:
            raise ScaffoldError(_explain(exc)) from exc
        except OSError as exc:
            # ProcessExecutionError is itself an OSError subclass, so it stays
            # matched by the clause above. This one is Copier failing to
            # create or use its cache directory directly (Copier >=9.16) -- a
            # redirected or ACL-restricted cache on a managed machine surfaces
            # here, before git runs. Errors outside the cache path are not
            # ours to translate.
            if (message := _explain_cache_os_error(exc)) is None:
                raise
            raise ScaffoldError(message) from exc


def update(project: Path, *, vcs_ref: str | None = None, dry_run: bool = False) -> None:
    """Pull template changes into an existing project, or validate them."""
    answers = project / ".copier-answers.yml"
    if not answers.is_file():
        msg = (
            f"No .copier-answers.yml in {project}. This project was not created "
            "by forge, or the answers file was deleted."
        )
        raise ScaffoldError(msg)

    try:
        recorded = yaml.safe_load(answers.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ScaffoldError(
            "Cannot read .copier-answers.yml. Repair its YAML before retrying; "
            "use a credential-free _src_path with a Git credential helper or SSH agent."
        ) from None
    if (
        not isinstance(recorded, dict)
        or not isinstance(recorded.get("_src_path"), str)
        or not recorded["_src_path"]
    ):
        raise ScaffoldError(
            ".copier-answers.yml needs a non-empty string _src_path. "
            "Restore a credential-free source with a Git credential helper "
            "or SSH agent."
        )
    try:
        validate_source(recorded["_src_path"], origin=".copier-answers.yml _src_path")
    except SourceError as exc:
        raise ScaffoldError(str(exc)) from None

    try:
        run_update(
            dst_path=project,
            vcs_ref=vcs_ref,
            defaults=True,
            unsafe=True,
            quiet=True,
            pretend=dry_run,
            # Only ask about questions that did not exist last time.
            skip_answered=True,
            conflict="inline",
            # Copier refuses to update without this. It is not the safety
            # relaxation it looks like: `update` already requires the
            # destination to be a clean git repo (checked above and by
            # Copier itself), so the user reviews a diff before committing
            # regardless. Copier's own CLI hardcodes this for `update` too.
            overwrite=True,
        )
    except (CopierError, ProcessExecutionError) as exc:
        raise ScaffoldError(_explain(exc)) from exc
    except OSError as exc:
        # See scaffold(): a cache-directory failure Copier raises directly,
        # not through git. Everything else re-raises untouched.
        if (message := _explain_cache_os_error(exc)) is None:
            raise
        raise ScaffoldError(message) from exc


def _cache_failure_message(cache_path: Path) -> str:
    """Recovery guidance for an unusable Copier cache, naming only our own
    resolved path -- never any part of the process output that revealed it.
    """  # noqa: D205
    return (
        f"Copier's template cache at {cache_path} is not usable.\n"
        "  This is common on managed machines where the cache location is "
        "redirected or restricted.\n"
        "  Point Copier at a fresh, writable directory and retry -- do not "
        "delete the existing one:\n"
        '    PowerShell:  $env:COPIER_CACHE_DIR = "C:\\forge-cache"\n'
        '    bash/zsh:    export COPIER_CACHE_DIR="$HOME/.cache/forge-copier"'
    )


def _under_cache_dir(candidate: object, cache_path: Path) -> bool:
    """True when `candidate` is a string path at or below `cache_path`."""
    if not isinstance(candidate, str):
        return False
    return os.path.normcase(candidate).startswith(os.path.normcase(str(cache_path)))


def _looks_like_cache_git_failure(exc: ProcessExecutionError, cache_path: Path) -> bool:
    """True only for a git failure that reports a missing repository *and*
    names the cache directory -- not for auth, network, or missing-source
    failures that merely happen to run against a cache path in argv.
    """  # noqa: D205
    if _CACHE_FAILURE_SIGNAL not in (exc.stderr or "").lower():
        return False
    if os.path.normcase(str(cache_path)) in os.path.normcase(exc.stderr or ""):
        return True
    return any(_under_cache_dir(arg, cache_path) for arg in exc.argv or [])


def _explain_cache_os_error(exc: OSError) -> str | None:
    """Explain an OS error Copier raised while preparing its cache directory.

    Returns None for any error whose filename is not under the resolved cache
    directory, so the caller re-raises it untouched -- create-forge only owns
    a failure at the cache path it can name.
    """
    cache_path = copier_cache_location().path
    names = (exc.filename, getattr(exc, "filename2", None))
    if any(_under_cache_dir(name, cache_path) for name in names):
        return _cache_failure_message(cache_path)
    return None


def _explain(exc: CopierError | ProcessExecutionError) -> str:
    """Translate Copier's internal errors into something actionable.

    Copier's messages assume familiarity with its model. Most users of this CLI
    will not have any, so the common failures get rewritten.
    """
    if isinstance(exc, ProcessExecutionError):
        # The raw exception contains argv, stdout and stderr. In addition to
        # being too implementation-specific for users, argv may contain
        # credentials embedded in a template URL, so none of it is displayed.
        # Only fixed signals are read out of it, and only create-forge's own
        # resolved cache path is ever shown.
        cache = copier_cache_location()
        return (
            _cache_failure_message(cache.path)
            if _looks_like_cache_git_failure(exc, cache.path)
            else _PROCESS_FAILURE_MESSAGE
        )

    text = str(exc)
    lowered = text.lower()

    if "dirty" in lowered or "uncommitted" in lowered:
        return (
            "The project has uncommitted changes. Copier needs a clean working "
            "tree to merge template updates.\n"
            "  Commit or stash first: git stash"
        )
    if "only supported in git-tracked subprojects" in lowered:
        return (
            "This project is not tracked by git. `update` needs it to be, so "
            "you can review the merge before committing.\n"
            "  Run: git init && git add -A && git commit -m 'initial'"
        )
    if "version from last update not detected" in lowered:
        return (
            "The version recorded in .copier-answers.yml isn't a released "
            "template version, so there is nothing to update from.\n"
            "  Check this project was created by create-forge, not hand-edited."
        )
    if "no valid version" in lowered or ("ref" in lowered and "not found" in lowered):
        return (
            "The template has no released version to use.\n"
            "  The template repository needs a PEP440 git tag, e.g. v0.1.0"
        )
    return (
        _PROCESS_FAILURE_MESSAGE
        if "authentication" in lowered or "permission denied" in lowered
        else "Copier could not complete the template operation. "
        "Check the template configuration, supplied answers, and --ref, then retry."
    )
