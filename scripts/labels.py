"""Syncs GitHub issue labels to the taxonomy declared in `.github/labels.toml`.

Without a checked-in manifest, "labels shared with forge-template" stops being
true the first time either repo's labels are edited by hand in the GitHub UI.
This reads the manifest, diffs it against whatever a repo's labels actually
are, and reconciles them via `gh label create --force` (create-or-update, so
re-running after drift is always safe) and, opt-in via `--prune`, `gh label
delete` for anything present on the repo but absent from the manifest.

`--repo OWNER/NAME` is the mechanism that makes the manifest actually shared:
the same `.github/labels.toml` drives both create-forge and forge-template.
Omitted, `gh` infers the repository from the current directory's git remote.

Usage:
    uv run poe labels:sync -- --dry-run          # preview, change nothing
    uv run poe labels:sync -- --prune            # apply, deleting extras
    uv run python scripts/labels.py --repo Sandsy09/forge-template --prune
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_FILE = REPO_ROOT / ".github" / "labels.toml"

# GitHub's own limits -- a create-time API rejection is a worse place to
# discover a manifest slip than a local test.
_MAX_NAME_LENGTH = 50
_MAX_DESCRIPTION_LENGTH = 100


@dataclass(frozen=True)
class LabelSpec:
    """A label's colour and description, independent of its final name."""

    color: str
    description: str


def load_manifest(path: Path = MANIFEST_FILE) -> dict[str, Any]:
    """Parse the label manifest as raw TOML data."""
    with path.open("rb") as f:
        return tomllib.load(f)


def desired_labels(manifest: dict[str, Any]) -> dict[str, LabelSpec]:
    """Flatten the manifest's groups and unprefixed labels into name -> spec.

    Group labels are namespaced "<group>:<label>"; entries under
    `[unprefixed]` keep their bare name.
    """
    labels: dict[str, LabelSpec] = {}
    for group_name, group in manifest.get("groups", {}).items():
        for label_name, spec in group.get("labels", {}).items():
            labels[f"{group_name}:{label_name}"] = LabelSpec(
                color=spec["color"], description=spec["description"]
            )
    for label_name, spec in manifest.get("unprefixed", {}).items():
        labels[label_name] = LabelSpec(
            color=spec["color"], description=spec["description"]
        )
    return labels


def current_labels(repo: str | None) -> dict[str, LabelSpec]:
    """Fetch the labels that currently exist on `repo` (or the inferred repo)."""
    cmd = ["gh", "label", "list", "--json", "name,color,description", "--limit", "200"]
    if repo:
        cmd += ["--repo", repo]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
    rows = json.loads(result.stdout)
    return {
        row["name"]: LabelSpec(
            color=row["color"].lower(), description=row["description"]
        )
        for row in rows
    }


@dataclass(frozen=True)
class Plan:
    """The create/update/prune actions needed to reach the desired state."""

    creates: dict[str, LabelSpec]
    updates: dict[str, LabelSpec]
    unchanged: tuple[str, ...]
    prunes: tuple[str, ...]


def build_plan(
    desired: dict[str, LabelSpec], current: dict[str, LabelSpec], *, prune: bool
) -> Plan:
    """Diff desired against current, including prune candidates only if asked."""
    creates = {name: spec for name, spec in desired.items() if name not in current}
    updates = {
        name: spec
        for name, spec in desired.items()
        if name in current and current[name] != spec
    }
    unchanged = tuple(
        name for name, spec in desired.items() if current.get(name) == spec
    )
    prunes = tuple(sorted(set(current) - set(desired))) if prune else ()
    return Plan(creates=creates, updates=updates, unchanged=unchanged, prunes=prunes)


def print_plan(plan: Plan) -> None:
    """Print a human-readable summary of what would change."""
    for name, spec in sorted(plan.creates.items()):
        print(f"create    {name:<20} #{spec.color}  {spec.description}")
    for name, spec in sorted(plan.updates.items()):
        print(f"update    {name:<20} #{spec.color}  {spec.description}")
    for name in sorted(plan.unchanged):
        print(f"unchanged {name}")
    for name in sorted(plan.prunes):
        print(f"prune     {name}")
    print(
        f"\n{len(plan.creates)} to create, {len(plan.updates)} to update, "
        f"{len(plan.unchanged)} unchanged, {len(plan.prunes)} to prune."
    )


def apply_plan(plan: Plan, repo: str | None) -> None:
    """Execute the plan against `repo` via `gh label create`/`gh label delete`."""
    for name, spec in {**plan.creates, **plan.updates}.items():
        cmd = [
            "gh",
            "label",
            "create",
            name,
            "--color",
            spec.color,
            "--description",
            spec.description,
            "--force",
        ]
        if repo:
            cmd += ["--repo", repo]
        subprocess.run(cmd, check=True)  # noqa: S603

    for name in plan.prunes:
        cmd = ["gh", "label", "delete", name, "--yes"]
        if repo:
            cmd += ["--repo", repo]
        subprocess.run(cmd, check=True)  # noqa: S603


def main(argv: list[str] | None = None) -> int:
    """Parse args, build the plan, print it, and apply it unless `--dry-run`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=None, help="OWNER/NAME; defaults to the current repo"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan, change nothing"
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete labels present on the repo but absent from the manifest",
    )
    args = parser.parse_args(argv)

    desired = desired_labels(load_manifest())
    current = current_labels(args.repo)
    plan = build_plan(desired, current, prune=args.prune)
    print_plan(plan)

    if args.dry_run:
        print("\ndry run -- nothing changed")
        return 0

    apply_plan(plan, args.repo)
    print("\nok: labels synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
