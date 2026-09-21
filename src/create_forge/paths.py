"""The one client-owned boundary between an engine-supplied target string and the disk.

Every route that turns a project-relative *string* into a filesystem path --
`staging.write_files` (the `new` path) and `update.py` (provider-classified
plan targets, owner-declared rename endpoints, the metadata filename, and the
`output[].target` strings read back out of a project's own, editable
`.forge/generation.json`) -- resolves it here, so there is one definition of
what a target may look like and one place that states the threat model
(ADR 0052, canonical `docs/filesystem-generation.md`).

Deliberately engine-free, like `staging.py`, `lifecycle.py`, and `update.py`:
nothing here imports `forge_template`, not even under `TYPE_CHECKING`
(`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard covers this module
for exactly that reason).

**Accepted spelling.** A target is a relative, forward-slash POSIX path with no
dot components: `src/pkg/module.py`. It is rejected on *every* host -- not only
where it would misbehave -- so a target that works on one host works on the
other. Rejected: empty or root-only, absolute, drive-qualified or drive-relative
(`C:x`), UNC, any backslash, a `:` (an NTFS alternate data stream), `.`/`..`/
empty components, control characters, Windows-reserved device names (`aux.py`),
and a component ending in a dot or space.

**Refusals by name.** A `.git` segment anywhere is refused -- load-bearing,
because a written `.git/hooks/pre-commit` runs on the next commit -- along with
Copier's hygiene patterns (ADR 0045).

**Containment.** The validated parts are joined to the project's real root and
fully resolved, so an escaping final symlink, an escaping symlinked parent, and
a Windows junction or reparse-point escape are all one rule: the resolved
location must be a strict descendant of the root. A symlink that resolves back
*inside* the project is left working -- a user's own internal link is a
legitimate local edit. A leaf that does not exist yet is contained by its
resolved existing prefix.

**Threat model -- and its limit.** This defends against a malformed, hostile,
or tampered *target string*. Validation and use are separate system calls, so a
process that can mutate the project tree concurrently can swap a component
between them. Callers revalidate immediately before each filesystem operation,
which narrows that window; it does not close it, and **no race-safety guarantee
is made**. Nor is this a defence against someone who already has write access
to the tree.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Copier's `copier.yml` `_exclude` list, minus `copier.yml` itself (which has no
# engine analogue -- ADR 0045) and `.git` (handled separately in `is_excluded`,
# since it is load-bearing rather than merely hygienic). `PurePosixPath.match`
# applies each pattern to the whole target, so `*.py[co]` and `__pycache__`
# catch a match at any depth, not only at the root.
_EXCLUDED_PATTERNS = ("*.py[co]", "__pycache__", "__pycache__/*", "~*", ".DS_Store")

# Reserved on Windows whatever the extension (`aux.py` is `AUX`), and after
# trailing spaces are stripped. `CONIN$`/`CONOUT$` are the console handles.
_RESERVED_DEVICE_NAMES = re.compile(
    r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]"
    r"|CONIN\$|CONOUT\$)",
    re.IGNORECASE,
)


class Violation(StrEnum):
    """Which rule a rejected target broke, so callers can phrase it for their route."""

    SPELLING = "spelling"
    EXCLUDED = "excluded"
    ESCAPE = "escape"


class PathContainmentError(Exception):
    """A target string is not an acceptable project-relative path.

    Carries the offending `target` and a short `reason` naming the rule --
    never a filesystem path, so a message built from it cannot leak layout the
    caller did not already hold.
    """

    def __init__(self, target: str, violation: Violation, reason: str) -> None:
        super().__init__(f"{target!r}: {reason}")
        self.target = target
        self.violation = violation
        self.reason = reason


def _reject(target: str, reason: str) -> PathContainmentError:
    return PathContainmentError(target, Violation.SPELLING, reason)


def _component_problem(component: str) -> str | None:
    """Why one path component is unacceptable, or `None` if it is fine."""
    if component == "":
        return "an empty path component"
    if component in (".", ".."):
        return f"a `{component}` path component"
    if ":" in component:
        return "a `:` (drive letter or alternate data stream)"
    if component != component.rstrip(". "):
        return "a component ending in a dot or space"
    if _RESERVED_DEVICE_NAMES.fullmatch(
        component.split(".", maxsplit=1)[0].rstrip(" ")
    ):
        return "a Windows-reserved device name"
    return None


def relative_parts(target: str) -> tuple[str, ...]:
    """Validate the accepted POSIX spelling and return its components.

    Pure: no filesystem access, identical on every host.

    Raises:
        PathContainmentError: `target` breaks the spelling rules above.
    """
    if not target or target.strip("/") == "":
        raise _reject(target, "empty or root-only")
    if any(unicodedata.category(char) == "Cc" for char in target):
        raise _reject(target, "contains a control character")
    if "\\" in target:
        raise _reject(target, "contains a backslash")
    if target.startswith("/"):
        raise _reject(target, "absolute")
    parts = tuple(target.split("/"))
    for component in parts:
        problem = _component_problem(component)
        if problem is not None:
            raise _reject(target, problem)
    return parts


def is_excluded(target: str) -> bool:
    """Whether `target` falls under the engine's `_exclude` refusal (ADR 0045).

    A `.git` path segment anywhere is refused outright; the rest are Copier's
    hygiene patterns, matched against the whole target so a nested
    `sub/__pycache__/mod.pyc` is caught the same as a root-level one.
    """
    posix_target = PurePosixPath(target)
    if ".git" in posix_target.parts:
        return True
    return any(posix_target.match(pattern) for pattern in _EXCLUDED_PATTERNS)


@dataclass(frozen=True, slots=True)
class ProjectBoundary:
    """A project root that engine-supplied target strings are resolved against."""

    root: Path
    """The project root with symlinks and junctions already resolved."""

    @classmethod
    def for_project(cls, project: Path) -> ProjectBoundary:
        """A boundary rooted at `project`, resolved once up front."""
        return cls(project.resolve())

    def resolve(self, target: str) -> Path:
        """Validate `target` and return where it lives under the root.

        The returned path is the *lexical* location under the resolved root,
        not the fully-resolved one, so an internal symlink leaf is operated on
        as itself (an unlink removes the link, not what it points at) exactly
        as it was before this boundary existed. Containment was proven on the
        fully-resolved form.

        Raises:
            PathContainmentError: the spelling is unacceptable, the name is
                excluded, or the resolved location is not strictly inside the
                root.
        """
        parts = relative_parts(target)
        if is_excluded(target):
            msg = "an excluded target"
            raise PathContainmentError(target, Violation.EXCLUDED, msg)
        lexical = self.root.joinpath(*parts)
        try:
            resolved = lexical.resolve()
        except (OSError, RuntimeError) as exc:
            # A symlink loop or an unresolvable component: not provably inside.
            msg = "cannot be resolved inside the project"
            raise PathContainmentError(target, Violation.ESCAPE, msg) from exc
        if resolved == self.root or self.root not in resolved.parents:
            msg = "resolves outside the project"
            raise PathContainmentError(target, Violation.ESCAPE, msg)
        return lexical

    def resolve_all(self, targets: Iterable[str]) -> dict[str, Path]:
        """Resolve every target, or raise before returning any.

        The whole batch is validated before a caller can act on the first
        entry, which is what lets a caller preflight an entire update.
        """
        return {target: self.resolve(target) for target in targets}
