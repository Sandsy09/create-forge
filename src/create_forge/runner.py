"""Thin wrapper over Copier's Python API.

Copier's Python API is public but not versioned as strictly as its CLI, so this
module is the single place that touches it. Pin copier narrowly in
pyproject.toml (`copier>=9.4,<10`) and this file is the only thing that needs
attention on a major bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from copier import run_copy, run_update
from copier.errors import CopierError, UserMessageError

if TYPE_CHECKING:
    from collections.abc import Mapping


class ScaffoldError(Exception):
    """A failure the user can act on, already phrased for display."""


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
    if request.dst.exists() and any(request.dst.iterdir()):
        msg = f"{request.dst} already exists and is not empty"
        raise ScaffoldError(msg)

    try:
        run_copy(
            src_path=request.src,
            dst_path=request.dst,
            data=dict(request.data),
            vcs_ref=request.vcs_ref,
            # Anything not answered by the CLI falls back to the template's own
            # default, so copier.yml stays the source of truth.
            defaults=True,
            unsafe=True,
            quiet=True,
            pretend=request.dry_run,
        )
    except UserMessageError as exc:
        raise ScaffoldError(str(exc)) from exc
    except CopierError as exc:
        raise ScaffoldError(_explain(exc)) from exc


def update(project: Path, *, vcs_ref: str | None = None) -> None:
    """Pull template changes into an existing project."""
    answers = project / ".copier-answers.yml"
    if not answers.is_file():
        msg = (
            f"No .copier-answers.yml in {project}. This project was not created "
            "by forge, or the answers file was deleted."
        )
        raise ScaffoldError(msg)

    try:
        run_update(
            dst_path=project,
            vcs_ref=vcs_ref,
            defaults=True,
            unsafe=True,
            quiet=True,
            # Only ask about questions that did not exist last time.
            skip_answered=True,
            conflict="inline",
        )
    except UserMessageError as exc:
        raise ScaffoldError(str(exc)) from exc
    except CopierError as exc:
        raise ScaffoldError(_explain(exc)) from exc


def _explain(exc: CopierError) -> str:
    """Translate Copier's internal errors into something actionable.

    Copier's messages assume familiarity with its model. Most users of this CLI
    will not have any, so the common failures get rewritten.
    """
    text = str(exc)
    lowered = text.lower()

    if "dirty" in lowered or "uncommitted" in lowered:
        return (
            "The project has uncommitted changes. Copier needs a clean working "
            "tree to merge template updates.\n"
            "  Commit or stash first: git stash"
        )
    if "no valid version" in lowered or ("ref" in lowered and "not found" in lowered):
        return (
            "The template has no released version to use.\n"
            "  The template repository needs a PEP440 git tag, e.g. v0.1.0"
        )
    if "authentication" in lowered or "permission denied" in lowered:
        return (
            "Could not access the template repository.\n"
            "  Check you have read access and that your git credentials are set up."
        )
    return text
