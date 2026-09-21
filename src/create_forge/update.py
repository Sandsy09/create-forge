"""Engine-native `update` application.

Routing, the clean-tree precondition, Git-backed application of a
provider-computed update plan, and the client-owned degraded two-way
fallback.

ADR 0041 (CF-16.02) decided the rules this module builds; ADR 0046 (CF-18.04)
records this module's boundary, the merge mechanism, and the degraded
algorithm. See `docs/engine-project-lifecycle.md` and `docs/cli-conventions.md`'s
`update` section.

`forge_template.plan_update` already performs the reproducible-render
classification -- target-by-target `unchanged`/`added`/`removed`/`changed`/
`renamed`, owner-declared rename-window resolution, and digest verification
of the reproduced old render against the recorded document
(CF-ROADMAP-01-EX-01: no component-resource read or provider-validation
duplication in the client). This module owns exactly what the provider does
not and never will: the Git working tree, the per-target three-way merge
(`git merge-file`), and the degraded fallback the provider explicitly
declines to compute for the client.

Deliberately engine-free, like `staging.py`/`lifecycle.py`/`engine_source.py`:
nothing here imports `forge_template`, not even under `TYPE_CHECKING`
(`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard covers this
module for exactly that reason). `UpdateTargetView`/`AppliedRenameView`
mirror `descriptors.py`'s `DescriptorView` pattern: structural `Protocol`s the
real `forge_template.UpdateTarget`/`AppliedRename` satisfy without this
module importing either.

Every string this module turns into a filesystem path -- plan targets, rename
endpoints, the metadata filename, and the `output[].target` strings read back
out of the project's own editable `.forge/generation.json` -- goes through
`paths.ProjectBoundary` (ADR 0052). `preflight_update` validates the complete
update before the first rename, write, or delete; each filesystem operation
then revalidates its own target, which narrows but does not close the window
for a concurrent mutation (`paths.py` states the threat model and claims no
race-safety).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from create_forge import paths, staging

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

COPIER_ANSWERS_FILE = ".copier-answers.yml"
"""The direct-Copier route's own recorded-source file (`runner.update`'s)."""

ROLLBACK_HINT = "git restore . && git clean -fd"
"""Rule 18's printed-not-run recovery command for any failed or cancelled
engine-native update. `create-forge` never runs this itself -- a tool
invoking `git clean -fd` can delete untracked files the user cared about.
"""

_MERGE_CONFLICT_TRUNCATION = 127
"""`git merge-file`'s own documented cap: its exit status is the conflict
count, truncated to 127, or negative on an internal error. A subprocess
return code above this is therefore never a genuine conflict count.
"""


class UpdateError(Exception):
    """A safe, actionable failure preparing or applying an engine-native update.

    Never carries raw git/uv subprocess stdout or stderr -- a `git`/`uv`
    failure can carry a package-index credential or another sensitive
    process detail, mirroring `lifecycle.py`'s and `engine_source.py`'s own
    rule.
    """


def _contain(boundary: paths.ProjectBoundary, target: str) -> Path:
    """Resolve one target through the boundary, as an `UpdateError`.

    Names the target and the rule it broke, never a filesystem path.
    """
    try:
        return boundary.resolve(target)
    except paths.PathContainmentError as exc:
        msg = f"refusing an unsafe update target {exc}"
        raise UpdateError(msg) from exc


def _contain_all(boundary: paths.ProjectBoundary, targets: Iterable[str]) -> None:
    """Validate every target before a caller acts on the first."""
    for target in targets:
        _contain(boundary, target)


class Route(StrEnum):
    """Which update path a project's on-disk files select (ADR 0041 rule 7)."""

    ENGINE = "engine"
    COPIER = "copier"


def route_for(project: Path, *, metadata_filename: str, legacy: bool) -> Route:
    """The rule-7 routing table, from two file checks only.

    Neither file present is exit `1` naming both routes regardless of
    `--legacy` -- an explicit flag does not fabricate an answers file for a
    project that never had one. Otherwise `--legacy` always selects the
    Copier route; the engine route is chosen only when `.forge/generation.json`
    exists and `--legacy` was not passed.

    A pre-cutover `--engine-preview` project is one of the "neither file"
    causes rather than a detected case of its own (ADR 0047 rule 1): that flag
    wrote no answers file and no metadata document, so it is byte-for-byte
    indistinguishable on disk from any directory create-forge never touched.
    The message below names all three causes in one diagnostic; no migration
    helper is offered (ADR 0047 rule 2) -- no metadata is fabricated and no
    answers are invented.
    """
    boundary = paths.ProjectBoundary.for_project(project)
    has_metadata = _contain(boundary, metadata_filename).is_file()
    has_answers = (project / COPIER_ANSWERS_FILE).is_file()
    if not has_metadata and not has_answers:
        msg = (
            f"Neither {metadata_filename} nor {COPIER_ANSWERS_FILE} was found "
            f"in {project}. create-forge update needs one of them -- "
            f"{metadata_filename} selects the engine-native route, "
            f"{COPIER_ANSWERS_FILE} the --legacy Copier route. This project "
            "was not created by create-forge, its provenance file was "
            "deleted, or it was created by the removed development-only "
            "--engine-preview flag, which wrote neither file and never "
            "supported updates. Generate a fresh project with `create-forge "
            "new` and port your changes across -- create-forge will not "
            "invent answers for an existing tree."
        )
        raise UpdateError(msg)
    if legacy:
        return Route.COPIER
    return Route.ENGINE if has_metadata else Route.COPIER


@dataclass(frozen=True, slots=True)
class RecordedDocument:
    """The facts needed to reproduce the old render and run the degraded fallback.

    Also carries the raw text `forge_template.plan_update` validates
    authoritatively. Read leniently and structurally here -- no protocol
    negotiation, no component-version check, no digest verification against a
    render. `plan_update` is the provider's own authoritative validator once
    `old` exists (CF-ROADMAP-01-EX-01); this only extracts what is needed to
    *produce* `old` in the first place, and the recorded per-target digests
    the degraded path uses in place of an old render it cannot obtain.
    """

    raw: str
    provider_version: str
    spec: Mapping[str, object]
    digests: Mapping[str, str]


def read_recorded(project: Path, *, metadata_filename: str) -> RecordedDocument:
    """Read and structurally parse the recorded generation-metadata document."""
    path = _contain(paths.ProjectBoundary.for_project(project), metadata_filename)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"could not read {metadata_filename} in {project}: {exc}"
        raise UpdateError(msg) from exc

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{metadata_filename} is not valid JSON; repair or regenerate it"
        raise UpdateError(msg) from exc
    if not isinstance(document, dict):
        msg = f"{metadata_filename} must contain a JSON object"
        raise UpdateError(msg)

    provider = document.get("provider")
    version = provider.get("version") if isinstance(provider, dict) else None
    if not isinstance(version, str) or not version:
        msg = f"{metadata_filename} has no provider.version"
        raise UpdateError(msg)

    spec = document.get("spec")
    if not isinstance(spec, dict):
        msg = f"{metadata_filename} has no spec object"
        raise UpdateError(msg)

    digests: dict[str, str] = {}
    output = document.get("output")
    if isinstance(output, list):
        for entry in output:
            if not isinstance(entry, dict):
                continue
            target, digest = entry.get("target"), entry.get("digest")
            if isinstance(target, str) and isinstance(digest, str):
                digests[target] = digest

    return RecordedDocument(
        raw=raw, provider_version=version, spec=spec, digests=digests
    )


def write_recorded(project: Path, *, metadata_filename: str, content: str) -> None:
    """Write the refreshed generation-metadata document (rule 19: written last).

    The counterpart of `read_recorded`: the filename is an engine-supplied
    string, so it is resolved through the boundary here too (ADR 0052).
    """
    path = _contain(paths.ProjectBoundary.for_project(project), metadata_filename)
    path.write_text(content, encoding="utf-8")


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _git_output(args: Sequence[str], cwd: Path) -> str:
    """Run one git command, returning stdout on success.

    Raises `UpdateError` on a missing executable, a launch failure, or a
    non-zero exit -- never leaking raw stdout/stderr.
    """
    command = ["git", *args]
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        msg = "git is not on PATH; install git and retry"
        raise UpdateError(msg) from exc
    except OSError as exc:
        msg = f"could not launch git: {exc}"
        raise UpdateError(msg) from exc
    if result.returncode != 0:
        msg = f"`git {' '.join(args)}` failed in {cwd}"
        raise UpdateError(msg)
    return result.stdout


def _is_git_repository(project: Path) -> bool:
    command = ["git", "rev-parse", "--is-inside-work-tree"]
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
            command, cwd=project, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        msg = "git is not on PATH; install git and retry"
        raise UpdateError(msg) from exc
    except OSError as exc:
        msg = f"could not launch git: {exc}"
        raise UpdateError(msg) from exc
    return result.returncode == 0 and result.stdout.strip() == "true"


def require_clean_tree(project: Path) -> None:
    """Rule 10: refuse to start unless `project` is a clean Git working tree.

    This precondition is what makes `ROLLBACK_HINT` a correct recovery
    command for any later failure (rule 18): nothing this module does is
    ever the project's first uncommitted change.
    """
    if not _is_git_repository(project):
        msg = f"{project} is not a Git repository; an engine-native update requires one"
        raise UpdateError(msg)
    status = _git_output(["status", "--porcelain"], project)
    if status.strip():
        msg = (
            f"{project} has uncommitted changes. Commit or stash them first -- "
            "an engine-native update requires a clean working tree."
        )
        raise UpdateError(msg)


class AppliedRenameView(Protocol):
    """The engine's `AppliedRename` shape `apply_renames` needs."""

    @property
    def component_id(self) -> str:
        """The owning component's canonical identifier."""
        ...

    @property
    def from_(self) -> str:
        """The path this update moves the target away from."""
        ...

    @property
    def to(self) -> str:
        """The path this update moves the target to."""
        ...

    @property
    def since(self) -> str:
        """The owner version that introduced the move."""
        ...


def apply_renames(project: Path, renames: Sequence[AppliedRenameView]) -> None:
    """Rule 11: apply each owner-declared rename to the working tree before diffing.

    So a local edit under the old path travels with the move, rather than
    being stranded. A source that no longer exists (already moved, or
    removed by the user) is skipped -- nothing to carry.

    Both endpoints of every rename are validated before the first move, and
    revalidated as each move happens (ADR 0052). `--` keeps a target that
    begins with `-` from being read as a `git mv` option.
    """
    boundary = paths.ProjectBoundary.for_project(project)
    for rename in renames:
        _contain_all(boundary, (rename.from_, rename.to))
    for rename in renames:
        source = _contain(boundary, rename.from_)
        if not source.exists():
            continue
        destination = _contain(boundary, rename.to)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            _git_output(["mv", "-f", "--", rename.from_, rename.to], project)
        except UpdateError:
            # An untracked source (a partially-applied prior update, say)
            # cannot be `git mv`-ed -- fall back to a plain filesystem move.
            shutil.move(str(source), str(destination))


def merge_target(*, base: bytes, ours: bytes, theirs: bytes) -> tuple[bytes, bool]:
    """Three-way merge one target's bytes with `git merge-file -p`.

    `ours` is the working-tree content, `base` is the old (recorded) render,
    `theirs` is the new render -- the same roles `git merge-file` itself
    documents. Writes nothing to disk itself; the caller decides whether and
    where to write the result. Returns `(merged_bytes, conflicted)`.
    """
    with tempfile.TemporaryDirectory(prefix="create-forge-merge-") as scratch:
        scratch_path = Path(scratch)
        ours_path = scratch_path / "ours"
        base_path = scratch_path / "base"
        theirs_path = scratch_path / "theirs"
        ours_path.write_bytes(ours)
        base_path.write_bytes(base)
        theirs_path.write_bytes(theirs)
        command = [
            "git",
            "merge-file",
            "-p",
            "-L",
            "current",
            "-L",
            "template (recorded)",
            "-L",
            "template (new)",
            str(ours_path),
            str(base_path),
            str(theirs_path),
        ]
        try:
            result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
                command, capture_output=True, check=False
            )
        except FileNotFoundError as exc:
            msg = "git is not on PATH; install git and retry"
            raise UpdateError(msg) from exc
        except OSError as exc:
            msg = f"could not launch git: {exc}"
            raise UpdateError(msg) from exc

    if result.returncode < 0 or result.returncode > _MERGE_CONFLICT_TRUNCATION:
        msg = "git merge-file failed unexpectedly"
        raise UpdateError(msg)
    return result.stdout, result.returncode > 0


def _looks_like_text(content: bytes) -> bool:
    """A conservative binary sniff: a NUL byte anywhere means "don't merge this".

    Decision 7's rule: never splice conflict markers into binary content.
    """
    return b"\x00" not in content


@dataclass(frozen=True, slots=True)
class TargetResult:
    """One target's outcome after `apply_plan`/`degraded_plan`.

    `status` is one of `clean` (written, no conflict), `conflict` (left for
    manual review -- markers written, or a locally-modified file left as-is),
    `skipped` (a `skip-if-exists` target, or a target the user deleted
    locally and whose deletion is respected), or `unchanged`.
    """

    target: str
    classification: str
    status: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class UpdateOutcome:
    """Every target's result from one `apply_plan`/`degraded_plan` call."""

    results: tuple[TargetResult, ...]

    @property
    def conflicts(self) -> int:
        """How many targets were left for manual review."""
        return sum(1 for result in self.results if result.status == "conflict")

    @property
    def changed(self) -> int:
        """How many targets were written or flagged.

        Excludes `unchanged` and `skipped` targets, which nothing
        meaningfully happened to.
        """
        statuses = ("clean", "conflict")
        return sum(1 for result in self.results if result.status in statuses)


def _write(
    boundary: paths.ProjectBoundary, target: str, content: bytes, *, dry_run: bool
) -> None:
    path = _contain(boundary, target)  # revalidated at the point of use
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _remove(boundary: paths.ProjectBoundary, target: str, *, dry_run: bool) -> None:
    path = _contain(boundary, target)  # revalidated at the point of use
    if dry_run:
        return
    path.unlink(missing_ok=True)


def _merge_changed(  # noqa: PLR0913 - one keyword per merge input; the working/old/new triad and dry_run cannot collapse further
    boundary: paths.ProjectBoundary,
    target: str,
    classification: str,
    *,
    working_bytes: bytes,
    old_bytes: bytes | None,
    new_bytes: bytes,
    dry_run: bool,
) -> TargetResult:
    if old_bytes is not None and working_bytes == old_bytes:
        # Pristine: no local edit to preserve, take the new bytes outright.
        _write(boundary, target, new_bytes, dry_run=dry_run)
        return TargetResult(target, classification, "clean")
    if working_bytes == new_bytes:
        return TargetResult(target, classification, "unchanged")
    if not _looks_like_text(working_bytes) or not _looks_like_text(new_bytes):
        detail = "locally modified binary target; left as-is"
        return TargetResult(target, classification, "conflict", detail)
    merged, conflicted = merge_target(
        base=old_bytes or b"", ours=working_bytes, theirs=new_bytes
    )
    _write(boundary, target, merged, dry_run=dry_run)
    return TargetResult(target, classification, "conflict" if conflicted else "clean")


class UpdateTargetView(Protocol):
    """The engine's `UpdateTarget` shape `apply_plan` needs."""

    @property
    def target(self) -> str:
        """The project-relative POSIX path."""
        ...

    @property
    def classification(self) -> str:
        """One of `unchanged`, `added`, `removed`, `changed`, `renamed`."""
        ...

    @property
    def regeneration(self) -> str:
        """`replace` or `skip-if-exists`."""
        ...


def apply_plan(  # noqa: PLR0913 - one keyword per render side plus renames and dry_run; matches _merge_changed's own justification
    project: Path,
    targets: Sequence[UpdateTargetView],
    renames: Sequence[AppliedRenameView],
    *,
    old: Mapping[str, bytes],
    new: Mapping[str, bytes],
    dry_run: bool,
) -> UpdateOutcome:
    """Apply a provider-classified update plan to the working tree.

    `renames` must already have been applied to the working tree
    (`apply_renames`, before this call) -- this only needs them to look up a
    renamed target's *old* content, keyed by its pre-move path. `dry_run`
    classifies and would-write every target exactly like a real run but
    writes nothing (rule 16's "genuine preview" is this same code path).

    Every plan target -- including `skip-if-exists` and `unchanged` entries,
    which are never written but are still provider-supplied strings -- is
    validated before the first write or delete, so an invalid late target
    leaves no partial mutation and a `--dry-run` reads nothing outside the
    project (ADR 0052).
    """
    boundary = paths.ProjectBoundary.for_project(project)
    _contain_all(boundary, (item.target for item in targets))
    rename_source = {rename.to: rename.from_ for rename in renames}
    results: list[TargetResult] = []
    for item in sorted(targets, key=lambda target: target.target):
        if item.regeneration == "skip-if-exists":
            results.append(TargetResult(item.target, item.classification, "skipped"))
            continue
        old_key = rename_source.get(item.target, item.target)
        results.append(
            _apply_one(
                boundary,
                item,
                old_bytes=old.get(old_key),
                new_bytes=new.get(item.target),
                dry_run=dry_run,
            )
        )
    return UpdateOutcome(tuple(results))


def _apply_one(  # noqa: PLR0911 - one return per classification-dispatch branch; the table above each is exactly this function's contract
    boundary: paths.ProjectBoundary,
    item: UpdateTargetView,
    *,
    old_bytes: bytes | None,
    new_bytes: bytes | None,
    dry_run: bool = False,
) -> TargetResult:
    path = _contain(boundary, item.target)
    classification = item.classification

    if classification == "unchanged":
        return TargetResult(item.target, classification, "unchanged")

    if classification in ("added", "renamed"):
        if new_bytes is None:
            msg = f"the new render has no bytes for {item.target!r}"
            raise UpdateError(msg)
        if not path.exists():
            _write(boundary, item.target, new_bytes, dry_run=dry_run)
            return TargetResult(item.target, classification, "clean")
        return _merge_changed(
            boundary,
            item.target,
            classification,
            working_bytes=path.read_bytes(),
            old_bytes=old_bytes,
            new_bytes=new_bytes,
            dry_run=dry_run,
        )

    if classification == "changed":
        if old_bytes is None or new_bytes is None:
            msg = f"a changed target {item.target!r} is missing old or new render bytes"
            raise UpdateError(msg)
        if not path.exists():
            # Decision 8: the user deleted a target the template still
            # manages -- respect the deletion, never resurrect it.
            return TargetResult(
                item.target, classification, "skipped", "deleted locally; left absent"
            )
        return _merge_changed(
            boundary,
            item.target,
            classification,
            working_bytes=path.read_bytes(),
            old_bytes=old_bytes,
            new_bytes=new_bytes,
            dry_run=dry_run,
        )

    if classification == "removed":
        if old_bytes is None:
            msg = f"a removed target {item.target!r} is missing its recorded old bytes"
            raise UpdateError(msg)
        if not path.exists():
            return TargetResult(item.target, classification, "unchanged")
        working_bytes = path.read_bytes()
        if working_bytes == old_bytes:
            _remove(boundary, item.target, dry_run=dry_run)
            return TargetResult(item.target, classification, "clean")
        return TargetResult(
            item.target,
            classification,
            "conflict",
            "locally modified; the template no longer manages it, kept",
        )

    msg = f"unknown update classification {classification!r} for {item.target!r}"
    raise UpdateError(msg)


def degraded_plan(
    project: Path,
    new: Mapping[str, bytes],
    *,
    recorded_digests: Mapping[str, str],
    dry_run: bool,
) -> UpdateOutcome:
    """The client-owned degraded two-way update (rule 22, decision 4).

    No old render exists, so there is no provider classification and no
    three-way merge base -- `forge_template.plan_update` explicitly declines
    to perform this comparison itself. "Pristine" is instead decided from
    the *recorded per-target digest* already in `.forge/generation.json`, not
    a reproduced render: a working-tree target whose bytes still match its
    recorded digest is replaced outright; anything else is left completely
    alone and reported for manual review, since there is no way to tell a
    local edit from an old template default without the old render.

    The recorded digest keys come from a file the user can edit, so they are
    the least trusted strings in an update: every new-render target *and*
    every recorded target is validated before anything is read, written, or
    deleted (ADR 0052) -- a tampered `output[].target` cannot make a
    `--dry-run` read outside the project either.
    """
    boundary = paths.ProjectBoundary.for_project(project)
    _contain_all(boundary, (*new, *recorded_digests))
    results: list[TargetResult] = []
    for target, new_bytes in sorted(new.items()):
        path = _contain(boundary, target)
        recorded_digest = recorded_digests.get(target)
        if not path.exists():
            _write(boundary, target, new_bytes, dry_run=dry_run)
            results.append(TargetResult(target, "added", "clean"))
            continue
        working_bytes = path.read_bytes()
        if working_bytes == new_bytes:
            results.append(TargetResult(target, "unchanged", "unchanged"))
            continue
        if recorded_digest is not None and _digest(working_bytes) == recorded_digest:
            _write(boundary, target, new_bytes, dry_run=dry_run)
            results.append(TargetResult(target, "changed", "clean"))
            continue
        results.append(
            TargetResult(
                target,
                "changed",
                "conflict",
                "no merge base available; left as-is for manual review",
            )
        )

    for target in sorted(set(recorded_digests) - set(new)):
        path = _contain(boundary, target)
        if not path.exists():
            continue
        working_bytes = path.read_bytes()
        if _digest(working_bytes) == recorded_digests[target]:
            _remove(boundary, target, dry_run=dry_run)
            results.append(TargetResult(target, "removed", "clean"))
        else:
            results.append(
                TargetResult(
                    target,
                    "removed",
                    "conflict",
                    "locally modified; the template no longer manages it, kept",
                )
            )
    return UpdateOutcome(tuple(results))


def preflight_update(
    project: Path,
    *,
    metadata_filename: str,
    targets: Iterable[str] = (),
    renames: Sequence[AppliedRenameView] = (),
    recorded_targets: Iterable[str] = (),
) -> None:
    """Validate a complete update before its first rename, write, or delete.

    ADR 0052. Covers every string the update will turn into a path: the
    metadata filename, every plan or new-render target (including
    `skip-if-exists` and `unchanged` entries, which are never written but are
    still provider-supplied), both endpoints of every rename, and every
    target recorded in `.forge/generation.json`. Reads and writes nothing
    itself. `apply_renames`, `apply_plan`, and `degraded_plan` each also
    validate their own inputs up front and revalidate at the point of use;
    this is the one call that lets `cli.py` refuse the whole update before
    `apply_renames`, the first mutating step on the normal path.

    Raises:
        UpdateError: naming the offending target and the rule it broke.
    """
    boundary = paths.ProjectBoundary.for_project(project)
    _contain(boundary, metadata_filename)
    for rename in renames:
        _contain_all(boundary, (rename.from_, rename.to))
    _contain_all(boundary, targets)
    _contain_all(boundary, recorded_targets)


def stage_result(project: Path) -> None:
    """Rule 12/19: leave the merge staged but uncommitted.

    Called last -- after every write (the merge, the relocked `uv.lock`, and
    the refreshed `.forge/generation.json`) has already happened.
    """
    _git_output(["add", "-A"], project)


def relock(project: Path) -> str | None:
    """Re-resolve `uv.lock` after a successful merge (decision 6, ADR 0046).

    `uv.lock` is client-owned (ADR 0021) and never one of the engine's
    classified targets, so it needs its own refresh step. A failure warns and
    keeps the project -- the same warn-and-continue posture `lifecycle.py`
    applies to the `new` path's own convenience steps -- rather than
    discarding an otherwise-good update.
    """
    try:
        staging.create_uv_lock(project)
    except staging.StagingError as exc:
        return str(exc)
    return None
