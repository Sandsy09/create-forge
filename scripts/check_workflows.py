"""Checks that every GitHub Actions workflow pins its external actions to an
immutable commit and keeps write permissions off the workflow level.

A mutable reference -- a branch, or a `v7`/`v1.2.3` tag -- can be repointed
after the workflow was reviewed, so a release-capable job could execute code
that was never assessed. `.github/workflows/` therefore pins every external
`uses:` to a full 40-character commit SHA with the human-readable version in
an adjacent comment, and grants `contents: write` / `id-token: write` only on
the individual jobs that need them. This check makes both properties
impossible to regress, including through a Dependabot upgrade that reintroduces
a floating tag. See docs/workflow-security.md and ADR 0037.

Both CI (via ``tests/test_workflows.py`` in the fast suite) and ``poe
check:workflows`` run these checks.

This is the first script under ``scripts/`` to import a third-party package;
PyYAML is a hard runtime dependency of ``create-forge`` (see
``[project.dependencies]`` in pyproject.toml), so it is always installed.
"""  # noqa: D205

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# A `uses:` line, as a list item (`- uses: x`) or a mapped key (`  uses: x`),
# with an optional trailing `# comment`.
_USES_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s*(?P<ref>[^\s#]+)(?:\s+#\s?(?P<comment>.*\S))?\s*$"
)
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")

# References that are not external actions and so sit outside the SHA rule.
_LOCAL_PREFIXES = ("./", "docker://")

# GitHub token permission scopes. `metadata` is always read-only and cannot be
# granted `write`, so it is not listed.
_PERMISSION_SCOPES = (
    "actions",
    "attestations",
    "checks",
    "contents",
    "deployments",
    "discussions",
    "id-token",
    "issues",
    "models",
    "packages",
    "pages",
    "pull-requests",
    "repository-projects",
    "security-events",
    "statuses",
)


def discover(workflow_dir: Path = WORKFLOW_DIR) -> list[Path]:
    """Return every workflow file, sorted, matching `*.yml` or `*.yaml`."""
    return sorted(
        p
        for p in workflow_dir.iterdir()
        if p.is_file() and p.suffix in {".yml", ".yaml"}
    )


def _load(path: Path) -> dict[str, Any]:
    """Parse a workflow file, returning `{}` for anything that is not a mapping."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def check_pinned_references(paths: list[Path]) -> list[str]:
    """Every external `uses:` must be a full 40-char commit SHA with a comment."""
    errors = []
    for path in paths:
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _USES_RE.match(line)
            if match is None:
                continue
            ref = match.group("ref")
            if ref.startswith(_LOCAL_PREFIXES):
                continue

            where = f"{path.name}:{lineno}"
            action, _, git_ref = ref.partition("@")
            if not git_ref:
                errors.append(f"{where}: {action} has no '@<sha>' pin")
                continue

            if _FULL_SHA_RE.match(git_ref):
                if match.group("comment") is None:
                    errors.append(
                        f"{where}: {action} is SHA-pinned but has no adjacent "
                        "'# <version>' comment"
                    )
            elif _HEX_RE.match(git_ref):
                errors.append(
                    f"{where}: {action} is pinned to {git_ref!r}, not a full "
                    "40-character lowercase commit SHA"
                )
            else:
                errors.append(
                    f"{where}: {action} is pinned to the mutable ref "
                    f"{git_ref!r}; use a full 40-character commit SHA with a "
                    "'# <version>' comment"
                )
    return errors


def check_declares_permissions(paths: list[Path]) -> list[str]:
    """Every workflow must set a top-level `permissions:` key."""
    errors = []
    for path in paths:
        if "permissions" not in _load(path):
            errors.append(
                f"{path.name}: no top-level 'permissions:' key; declare one "
                "(use 'permissions: {}' to grant nothing by default)"
            )
    return errors


def _write_scopes(permissions: Any) -> list[str]:
    """Return the write-granting scopes named by a `permissions:` value."""
    if permissions == "write-all":
        return ["write-all"]
    if isinstance(permissions, dict):
        return [
            scope for scope in _PERMISSION_SCOPES if permissions.get(scope) == "write"
        ]
    return []


def check_permission_placement(paths: list[Path]) -> list[str]:
    """Write permissions must sit on a job, never at the workflow level."""
    errors = []
    for path in paths:
        for scope in _write_scopes(_load(path).get("permissions")):
            detail = (
                "'permissions: write-all'"
                if scope == "write-all"
                else f"'{scope}: write'"
            )
            errors.append(
                f"{path.name}: {detail} at the workflow level; grant it only "
                "on the job that needs it"
            )
    return errors


def check_all(workflow_dir: Path = WORKFLOW_DIR) -> list[str]:
    """Run every check and return the combined list of errors."""
    paths = discover(workflow_dir)
    return [
        *check_pinned_references(paths),
        *check_declares_permissions(paths),
        *check_permission_placement(paths),
    ]


def main() -> int:
    """Print any failures and return a process exit code."""
    errors = check_all()
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} workflow check(s) failed.", file=sys.stderr)
        return 1
    print("ok: .github/workflows/ pins external actions and scopes permissions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
