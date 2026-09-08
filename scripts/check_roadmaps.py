"""Validate the prepared cross-repository roadmap packs without GitHub writes."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SECTION_PARTS = 2
ISSUE_COUNT = 38
HEADINGS = (
    "Outcome",
    "Issue context",
    "Problem statement",
    "Proposed resolution",
    "Acceptance criteria",
    "Exclusions",
    "Dependencies",
    "Parent epic",
    "Milestone",
    "Roadmap",
    "Labels",
    "Required completion evidence",
)


def require(condition: bool, message: str) -> None:
    """Reject an incomplete or inconsistent pack."""
    if not condition:
        raise ValueError(message)


def markdown_links(path: Path) -> None:
    """Check local Markdown targets and anchors, including technical docs."""
    content = path.read_text(encoding="utf-8")
    for raw in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
        target = raw.strip().strip("<>")
        if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        filename, _, anchor = unquote(target).partition("#")
        resolved = (path.parent / filename).resolve() if filename else path
        require(resolved.exists(), f"{path}: missing link {target}")
        if anchor and resolved.suffix == ".md":
            headings = re.findall(
                r"^#+ (.+)$", resolved.read_text(encoding="utf-8"), re.MULTILINE
            )
            anchors = {
                re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                for heading in headings
            }
            require(anchor in anchors, f"{path}: missing anchor {target}")


def validate_graph(issues: dict[str, dict[str, Any]]) -> None:
    """Check native dependency and parent-completion edges for cycles."""
    visiting: set[str] = set()
    complete: set[str] = set()

    def visit(identifier: str) -> None:
        require(identifier in issues, f"Unknown dependency: {identifier}")
        require(identifier not in visiting, f"Dependency cycle: {identifier}")
        if identifier in complete:
            return
        visiting.add(identifier)
        item = issues[identifier]
        for dependency in [*item["blocked_by"], *item.get("children", [])]:
            visit(dependency)
        visiting.remove(identifier)
        complete.add(identifier)

    for identifier in issues:
        visit(identifier)
    actionable = {
        key
        for key, item in issues.items()
        if item["kind"] == "child" and not item["blocked_by"]
    }
    require(actionable == {"FT-15.01"}, "Unexpected initially actionable children")
    require(
        issues["FT-19.01"]["blocked_by"] == ["CF-16.03"],
        "Streamlit must enter after client contract approval, not full cutover",
    )
    require(
        issues["CF-16.01"]["blocked_by"] == ["FT-15.04"],
        "Client design must depend on the provider contract, not publication",
    )
    require(
        issues["CF-18.01"]["blocked_by"] == ["FT-17.06"],
        "Cutover adoption must wait for provider publication",
    )
    require(
        set(issues["CF-18.07"]["blocked_by"]) == {"FT-18.01", "CF-18.06"},
        "Cutover publication must require both integrated validations",
    )
    require(
        issues["CF-21.01"]["blocked_by"] == ["FT-20.04"],
        "Streamlit adoption must wait for provider publication",
    )

    def ancestors(identifier: str) -> set[str]:
        result: set[str] = set()
        for dependency in issues[identifier]["blocked_by"]:
            result.add(dependency)
            result.update(ancestors(dependency))
        return result

    require(
        {"CF-18.04", "CF-18.05"} <= ancestors("CF-18.07"),
        "Engine-native and legacy updates must gate cutover publication",
    )


def check_metadata(
    item: dict[str, Any], stage_info: dict[str, Any], labels: set[str]
) -> None:
    """Check an entry's owner, milestone and proposed labels."""
    identifier = item["id"]
    require(item["title"].startswith(identifier + " — "), "Invalid title")
    require(
        not {"number", "url", "assignees", "due_date", "project"} & item.keys(),
        f"{identifier}: invented filing metadata",
    )
    expected_repo = (
        "Sandsy09/forge-template"
        if identifier.startswith("FT-")
        else "Sandsy09/create-forge"
    )
    require(item["repository"] == expected_repo, f"{identifier}: wrong repo")
    stage = item["stage"]
    require(expected_repo in stage_info["owners"], "Unowned stage milestone")
    stage_title = stage_info["title"]
    require(
        item["milestone"] == f"{stage_title} — Stage {stage}",
        f"{identifier}: wrong milestone",
    )
    assigned = item["labels"]
    require(len(assigned) == len(set(assigned)), "Duplicate label")
    require(set(assigned) <= labels, f"{identifier}: unknown label")
    for group in ("type:", "priority:", "roadmap:"):
        require(
            sum(label.startswith(group) for label in assigned) == 1,
            f"{identifier}: expected one {group} label",
        )
    require(f"roadmap:{stage}" in assigned, "Wrong stage label")
    require("priority:medium" in assigned, "Wrong priority")
    require(
        ("status:blocked" in assigned) == bool(item["blocked_by"]),
        f"{identifier}: inconsistent blocked status",
    )
    if item["kind"] == "child":
        require(
            item["parent"] == f"{identifier[:2]}-EPIC-{stage}",
            f"{identifier}: wrong parent",
        )
        require(
            sum(label.startswith("size:") for label in assigned) == 1,
            f"{identifier}: missing size",
        )
        require(
            ("status:needs-decision" in assigned) == ("type:decision" in assigned),
            f"{identifier}: inconsistent decision status",
        )
    else:
        require(item["parent"] is None, "Epics must not invent a parent")
        require({"type:epic", "cross-repo"} <= set(assigned), "Epic labels")


def check_body(item: dict[str, Any], folder: Path) -> str:
    """Check complete issue prose against its filing metadata."""
    identifier = item["id"]
    assigned = item["labels"]
    body_path: Path = folder / item["body"]
    require(
        body_path.resolve().is_relative_to(folder.resolve()),
        "Body path escapes roadmap",
    )
    body = body_path.read_text(encoding="utf-8")
    require(body.startswith("# " + item["title"] + "\n"), "Body title mismatch")
    for heading in HEADINGS:
        sections = re.split(rf"(?m)^## {re.escape(heading)}\n", body)
        require(len(sections) == SECTION_PARTS, f"{identifier}: missing {heading}")
        require(
            bool(sections[1].split("\n## ")[0].strip()),
            f"{identifier}: empty {heading}",
        )
    require("- [ ] " in body, f"{identifier}: no acceptance checklist")
    label_section = body.split("## Labels\n")[1].split("\n## ")[0]
    require(
        re.findall(r"`([^`]+)`", label_section) == assigned,
        f"{identifier}: body/manifest labels differ",
    )
    require(item["milestone"] in body, "Body milestone mismatch")
    if item["parent"]:
        require(f"[{item['parent']}]" in body, "Body parent mismatch")
    dependency_section = body.split("## Dependencies\n")[1].split("\n## ")[0]
    body_dependencies = re.findall(r"Blocked\s+by\s+\[([^\]]+)\]", dependency_section)
    require(body_dependencies == item["blocked_by"], "Body dependency mismatch")
    return body


def check_traceability(
    traces: list[dict[str, Any]],
    issues: dict[str, dict[str, Any]],
    bodies: dict[str, str],
) -> None:
    """Require every source review criterion and exclusion to have body owners."""
    expected_trace_ids = {
        f"{owner}-ROADMAP-{draft:02}-{kind}-{number:02}"
        for owner, draft, ac_count, ex_count in (
            ("FT", 1, 7, 4),
            ("CF", 1, 7, 4),
            ("FT", 2, 8, 4),
            ("CF", 2, 8, 3),
        )
        for kind, count in (("AC", ac_count), ("EX", ex_count))
        for number in range(1, count + 1)
    }
    require(
        len(traces) == len(expected_trace_ids)
        and {trace["id"] for trace in traces} == expected_trace_ids,
        "Missing or duplicate review criteria",
    )
    for trace in traces:
        require(bool(trace["criterion"].strip()), "Empty review criterion")
        require(bool(trace["children"]), "Unowned review criterion")
        parents = {issues[child]["parent"] for child in trace["children"]}
        require(set(trace["epics"]) == parents, "Traceability epic mismatch")
        for child in trace["children"]:
            require(issues[child]["kind"] == "child", "Traceability owner is not child")
            normalized = " ".join(bodies[child].split())
            require(trace["id"] in normalized, "Missing body review obligation")
            require(
                " ".join(trace["criterion"].split()) in normalized,
                "Body review criterion differs from traceability",
            )


def check_epics(issues: dict[str, dict[str, Any]]) -> None:
    """Check parent membership and native child inventories agree."""
    for identifier, item in issues.items():
        if item["kind"] == "epic":
            children = {
                key for key, child in issues.items() if child["parent"] == identifier
            }
            require(set(item["children"]) == children, "Epic child membership mismatch")


def check_packs(root: Path, mirror: Path | None = None) -> None:
    """Validate both manifests, complete bodies, traceability and mirrors."""
    labels_path = root / ".github/labels.toml"
    taxonomy = tomllib.loads(labels_path.read_text(encoding="utf-8"))
    labels = {
        f"{group}:{name}"
        for group, values in taxonomy["groups"].items()
        for name in values["labels"]
    } | set(taxonomy["unprefixed"])
    issues: dict[str, dict[str, Any]] = {}
    bodies: dict[str, str] = {}
    traces: list[dict[str, Any]] = []
    all_paths: set[Path] = {labels_path, root / "scripts/check_roadmaps.py"}
    stage_owners: dict[int, list[str]] = {}
    for version, expected in ((3, (5, 21)), (4, (3, 9))):
        folder = root / f"docs/roadmap-v{version}"
        manifest_path = folder / "github-issues/filing-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest["schema_version"] == 1, "Unsupported manifest schema")
        require(manifest["status"] == "prepared-not-filed", "Unexpected pack status")
        require(manifest["roadmap"] == version, "Wrong roadmap number")
        entries = manifest["issues"]
        counts = tuple(
            sum(item["kind"] == kind for item in entries) for kind in ("epic", "child")
        )
        require(counts == expected, f"Roadmap {version}: incorrect issue counts")
        for stage in manifest["stages"]:
            number = stage["number"]
            require(number not in stage_owners, f"Duplicate stage: {number}")
            stage_owners[number] = stage["owners"]
            require(f"roadmap:{number}" in labels, f"Missing stage label: {number}")
        for item in entries:
            identifier = item["id"]
            require(identifier not in issues, f"Duplicate issue ID: {identifier}")
            stage_info = next(
                value
                for value in manifest["stages"]
                if value["number"] == item["stage"]
            )
            check_metadata(item, stage_info, labels)
            body = check_body(item, folder)
            issues[identifier] = item
            bodies[identifier] = body
        traces.extend(manifest["traceability"])
        paths = {path for path in folder.rglob("*") if path.is_file()}
        all_paths.update(paths)
        expected_bodies = {folder / item["body"] for item in entries}
        actual_bodies = {
            path
            for path in folder.glob("github-issues/*/*.md")
            if path.name != "ISSUE-INDEX.md"
        }
        require(actual_bodies == expected_bodies, "Orphan or missing issue body")
        for path in paths:
            if path.suffix == ".md":
                markdown_links(path)
        if mirror:
            mirrored = mirror / folder.relative_to(root)
            require(
                {p.relative_to(folder) for p in paths}
                == {
                    p.relative_to(mirrored) for p in mirrored.rglob("*") if p.is_file()
                },
                f"Roadmap {version}: mirror inventory differs",
            )

    require(set(stage_owners) == set(range(15, 22)), "Missing stage")
    require(
        len({item["title"] for item in issues.values()}) == ISSUE_COUNT,
        "Duplicate title",
    )
    require("breaking-change" in issues["CF-18.01"]["labels"], "Unmarked cutover")
    check_epics(issues)
    validate_graph(issues)
    check_traceability(traces, issues, bodies)
    if mirror:
        for path in all_paths:
            other = mirror / path.relative_to(root)
            require(
                other.is_file() and path.read_bytes() == other.read_bytes(),
                f"Mirror differs: {path.relative_to(root)}",
            )
    print(
        "Roadmaps valid: 8 epics, 30 children, 45 review obligations; links and DAG OK."
    )


def main() -> None:
    """Run the read-only pack validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mirror", type=Path)
    args = parser.parse_args()
    try:
        check_packs(args.root.resolve(), args.mirror.resolve() if args.mirror else None)
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(1, f"Roadmap validation failed: {error}\n")


if __name__ == "__main__":
    main()
