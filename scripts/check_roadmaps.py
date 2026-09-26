"""Validate prepared or filed cross-repository roadmap packs without writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SECTION_PARTS = 2
PACK_STATUSES = {"prepared-not-filed", "filed-open"}
FILED_ISSUE_FIELDS = {"number", "url", "body_sha256"}
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
# Roadmap 5 imports bodies exactly as they were filed by a later filing session,
# which used a different section layout and carries no milestone or roadmap
# section (that metadata is reconciled afterwards, and recorded in the manifest).
HEADINGS_V5 = (
    "Outcome",
    "Issue context",
    "Problem statement",
    "Proposed resolution",
    "Scope",
    "Acceptance criteria",
    "Exclusions",
    "Dependencies and blocking requirements",
    "Parent epic",
    "Tracking and roadmap",
    "Labels",
    "Required completion evidence",
)


@dataclass(frozen=True)
class Rules:
    """What one roadmap pack must satisfy; v3 and v4 keep their original rules."""

    version: int
    counts: tuple[int, int]  # (epics, children)
    stages: frozenset[int]
    headings: tuple[str, ...]
    dependencies_heading: str
    filed_at_import: bool  # bodies imported as filed; metadata reconciled later


LEGACY_HEADINGS_DEPENDENCIES = "Dependencies"
PACKS = (
    Rules(3, (5, 21), frozenset(range(15, 19)), HEADINGS, "Dependencies", False),
    Rules(4, (3, 9), frozenset(range(19, 22)), HEADINGS, "Dependencies", False),
    Rules(
        5,
        (10, 27),
        frozenset(range(22, 30)),
        HEADINGS_V5,
        "Dependencies and blocking requirements",
        True,
    ),
)
LEGACY_VERSIONS = (3, 4)
ALL_STAGES = frozenset(range(15, 30))


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


def validate_graph(
    issues: dict[str, dict[str, Any]], legacy_ids: set[str] | None = None
) -> None:
    """Check native dependency and parent-completion edges for cycles.

    The named-issue assertions below encode roadmap v3 and v4 decisions, so they
    apply only to those packs' issues (`legacy_ids`); the acyclicity check
    covers every pack.
    """
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
    legacy = set(issues) if legacy_ids is None else legacy_ids
    actionable = {
        key
        for key, item in issues.items()
        if key in legacy and item["kind"] == "child" and not item["blocked_by"]
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
    item: dict[str, Any],
    stage_info: dict[str, Any],
    labels: set[str],
    status: str,
    rules: Rules,
) -> None:
    """Check an entry's owner, milestone, labels and filing identity."""
    identifier = item["id"]
    require(item["title"].startswith(identifier + " — "), "Invalid title")
    require(
        not {"assignees", "due_date", "project"} & item.keys(),
        f"{identifier}: unsupported filing metadata",
    )
    expected_repo = (
        "Sandsy09/forge-template"
        if identifier.startswith("FT-")
        else "Sandsy09/create-forge"
    )
    require(item["repository"] == expected_repo, f"{identifier}: wrong repo")
    if status == "prepared-not-filed":
        require(
            not FILED_ISSUE_FIELDS & item.keys(),
            f"{identifier}: invented filing metadata",
        )
    else:
        require(
            item.keys() >= FILED_ISSUE_FIELDS,
            f"{identifier}: missing filed metadata",
        )
        require(
            isinstance(item["number"], int) and item["number"] > 0,
            f"{identifier}: invalid issue number",
        )
        require(
            item["url"]
            == f"https://github.com/{expected_repo}/issues/{item['number']}",
            f"{identifier}: invalid issue URL",
        )
        require(
            re.fullmatch(r"[0-9a-f]{64}", item["body_sha256"]) is not None,
            f"{identifier}: invalid body hash",
        )
    stage = item["stage"]
    require(expected_repo in stage_info["owners"], "Unowned stage milestone")
    # Roadmap 5 stages 24 and 25 have differently titled epics in each
    # repository, so each owner records its own milestone title.
    stage_title = (
        stage_info["titles"][expected_repo]
        if rules.filed_at_import
        else stage_info["title"]
    )
    require(
        item["milestone"] == f"{stage_title} — Stage {stage}",
        f"{identifier}: wrong milestone",
    )
    assigned = item["labels"]
    require(len(assigned) == len(set(assigned)), "Duplicate label")
    require(set(assigned) <= labels, f"{identifier}: unknown label")
    groups = (
        ("type:", "priority:")
        if rules.filed_at_import
        else (
            "type:",
            "priority:",
            "roadmap:",
        )
    )
    for group in groups:
        require(
            sum(label.startswith(group) for label in assigned) == 1,
            f"{identifier}: expected one {group} label",
        )
    if rules.filed_at_import:
        # The filed labels carry no roadmap label; reconciliation adds it.
        require(
            item["added_labels"] == [f"roadmap:{stage}"],
            f"{identifier}: wrong reconciled roadmap label",
        )
        require(f"roadmap:{stage}" in labels, f"{identifier}: unknown roadmap label")
    else:
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
        if not rules.filed_at_import:
            require(
                ("status:needs-decision" in assigned) == ("type:decision" in assigned),
                f"{identifier}: inconsistent decision status",
            )
    else:
        require(item["parent"] is None, "Epics must not invent a parent")
        required = (
            {"type:epic"} if rules.filed_at_import else {"type:epic", "cross-repo"}
        )
        require(required <= set(assigned), "Epic labels")


def check_body(item: dict[str, Any], folder: Path, status: str, rules: Rules) -> str:
    """Check complete issue prose against its filing metadata."""
    identifier = item["id"]
    assigned = item["labels"]
    body_path: Path = folder / item["body"]
    require(
        body_path.resolve().is_relative_to(folder.resolve()),
        "Body path escapes roadmap",
    )
    body = body_path.read_text(encoding="utf-8")
    if status == "filed-open":
        require(
            hashlib.sha256(body.encode()).hexdigest() == item["body_sha256"],
            f"{identifier}: body hash mismatch",
        )
    require(body.startswith("# " + item["title"] + "\n"), "Body title mismatch")
    for heading in rules.headings:
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
    if not rules.filed_at_import:
        require(item["milestone"] in body, "Body milestone mismatch")
    if item["parent"]:
        require(f"[{item['parent']}]" in body, "Body parent mismatch")
    heading = rules.dependencies_heading
    dependency_section = body.split(f"## {heading}\n")[1].split("\n## ")[0]
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


def derive_obligations(identifier: str, body: str) -> list[tuple[str, str, str]]:
    """The (id, kind, text) obligations a filed body states.

    Every checklist item under `## Acceptance criteria` and every paragraph under
    `## Exclusions` is one obligation, numbered in order.
    """
    found: list[tuple[str, str, str]] = []
    criteria = body.split("## Acceptance criteria\n")[1].split("\n## ", maxsplit=1)[0]
    number = 0
    for line in criteria.splitlines():
        match = re.match(r"^- \[[ xX]\] (.+)$", line)
        if match:
            number += 1
            found.append((f"{identifier}-AC-{number:02}", "acceptance", match[1]))
    exclusions = body.split("## Exclusions\n")[1].split("\n## ", maxsplit=1)[0]
    number = 0
    for paragraph in re.split(r"\n\s*\n", exclusions.strip()):
        text = " ".join(paragraph.split())
        if text:
            number += 1
            found.append((f"{identifier}-EX-{number:02}", "exclusion", text))
    return found


def check_derived_traceability(
    traces: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    bodies: dict[str, str],
) -> None:
    """Require the obligations to be exactly those the filed bodies state."""
    expected: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for item in entries:
        for trace_id, kind, text in derive_obligations(item["id"], bodies[item["id"]]):
            expected[trace_id] = (kind, " ".join(text.split()), item)
    require(
        len(traces) == len(expected) and {t["id"] for t in traces} == set(expected),
        "Missing or duplicate filed obligations",
    )
    for trace in traces:
        kind, text, item = expected[trace["id"]]
        require(trace["source"] == "filed-body", "Unexpected traceability source")
        require(trace["kind"] == kind, f"{trace['id']}: wrong obligation kind")
        require(
            " ".join(trace["criterion"].split()) == text,
            f"{trace['id']}: obligation differs from the filed body",
        )
        require(trace["owner"] == item["id"], f"{trace['id']}: wrong owner")
        require(
            trace["epic"] == (item["parent"] or item["id"]),
            f"{trace['id']}: wrong epic",
        )


def check_epics(issues: dict[str, dict[str, Any]]) -> None:
    """Check parent membership and native child inventories agree."""
    for identifier, item in issues.items():
        if item["kind"] == "epic":
            children = {
                key for key, child in issues.items() if child["parent"] == identifier
            }
            require(set(item["children"]) == children, "Epic child membership mismatch")


def check_filing(
    manifest: dict[str, Any], entries: list[dict[str, Any]], status: str
) -> None:
    """Validate the absence or complete shape of repository filing records."""
    if status == "prepared-not-filed":
        require("filing" not in manifest, "Prepared pack has filing record")
        return
    require("filing" in manifest, "Filed pack is missing filing record")
    filing = manifest["filing"]
    require(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", filing["verified_at"]) is not None,
        "Invalid filing date",
    )
    expected_labels = [
        f"roadmap:{stage['number']}"
        for stage in sorted(manifest["stages"], key=lambda stage: stage["number"])
    ]
    require(filing["labels_applied"] == expected_labels, "Filed label record differs")
    expected_pairs = {(item["repository"], item["milestone"]) for item in entries}
    records = filing["milestones"]
    require(
        {(item["repository"], item["title"]) for item in records} == expected_pairs
        and len(records) == len(expected_pairs),
        "Filed milestone record differs",
    )
    for record in records:
        require(
            isinstance(record["number"], int) and record["number"] > 0,
            "Invalid milestone number",
        )
        require(
            record["url"]
            == f"https://github.com/{record['repository']}/milestone/{record['number']}",
            "Invalid milestone URL",
        )


def check_native_record(
    manifest: dict[str, Any], entries: list[dict[str, Any]]
) -> None:
    """Require the recorded native-relationship counts to match the filed graph."""
    native = manifest["filing"]["native"]
    require(
        native["sub_issues"] == sum(1 for item in entries if item["parent"]),
        "Native sub-issue record differs from the manifest",
    )
    require(
        native["blocked_by"] == sum(len(item["blocked_by"]) for item in entries),
        "Native blocked-by record differs from the manifest",
    )
    require(
        native["status"] in {"applied-and-verified", "body-links-only"},
        "Unknown native relationship status",
    )


def check_resolved_issue_links(
    issues: dict[str, dict[str, Any]], bodies: dict[str, str], status: str
) -> None:
    """Require filed parent and blocker links to use durable issue URLs."""
    if status != "filed-open":
        return
    seen_numbers: set[tuple[str, int]] = set()
    for identifier, item in issues.items():
        key = (item["repository"], item["number"])
        require(key not in seen_numbers, f"Duplicate filed issue number: {key}")
        seen_numbers.add(key)
        body = bodies[identifier]
        references = [*item["blocked_by"]]
        if item["parent"]:
            references.append(item["parent"])
        for reference in references:
            require(
                f"[{reference}]({issues[reference]['url']})" in body,
                f"{identifier}: unresolved filed link to {reference}",
            )


def check_global_invariants(
    stage_owners: dict[int, list[str]],
    statuses: set[str],
    issues: dict[str, dict[str, Any]],
    bodies: dict[str, str],
    traces: list[dict[str, Any]],
    legacy_ids: set[str],
) -> None:
    """Validate invariants spanning every roadmap manifest."""
    require(set(stage_owners) == set(ALL_STAGES), "Missing stage")
    require(len(statuses) == 1, "Roadmap pack filing states differ")
    require(
        len({item["title"] for item in issues.values()}) == len(issues),
        "Duplicate title",
    )
    require("breaking-change" in issues["CF-18.01"]["labels"], "Unmarked cutover")
    check_epics(issues)
    validate_graph(issues, legacy_ids)
    legacy = {key: value for key, value in issues.items() if key in legacy_ids}
    check_traceability(traces, legacy, bodies)
    check_resolved_issue_links(issues, bodies, next(iter(statuses)))


def check_packs(root: Path, mirror: Path | None = None) -> str:
    """Validate every manifest, complete bodies, traceability and mirrors."""
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
    obligations = 0
    statuses: set[str] = set()
    all_paths: set[Path] = {labels_path, root / "scripts/check_roadmaps.py"}
    stage_owners: dict[int, list[str]] = {}
    legacy_ids: set[str] = set()
    for rules in PACKS:
        version = rules.version
        folder = root / f"docs/roadmap-v{version}"
        manifest_path = folder / "github-issues/filing-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest["schema_version"] == 1, "Unsupported manifest schema")
        status = manifest["status"]
        require(status in PACK_STATUSES, "Unexpected pack status")
        statuses.add(status)
        require(manifest["roadmap"] == version, "Wrong roadmap number")
        entries = manifest["issues"]
        counts = tuple(
            sum(item["kind"] == kind for item in entries) for kind in ("epic", "child")
        )
        require(counts == rules.counts, f"Roadmap {version}: incorrect issue counts")
        require(
            {stage["number"] for stage in manifest["stages"]} == set(rules.stages),
            f"Roadmap {version}: incorrect stages",
        )
        for stage in manifest["stages"]:
            number = stage["number"]
            require(number not in stage_owners, f"Duplicate stage: {number}")
            stage_owners[number] = stage["owners"]
            require(f"roadmap:{number}" in labels, f"Missing stage label: {number}")
        pack_bodies: dict[str, str] = {}
        for item in entries:
            identifier = item["id"]
            require(identifier not in issues, f"Duplicate issue ID: {identifier}")
            stage_info = next(
                value
                for value in manifest["stages"]
                if value["number"] == item["stage"]
            )
            check_metadata(item, stage_info, labels, status, rules)
            body = check_body(item, folder, status, rules)
            issues[identifier] = item
            bodies[identifier] = body
            pack_bodies[identifier] = body
            if version in LEGACY_VERSIONS:
                legacy_ids.add(identifier)
        if version in LEGACY_VERSIONS:
            traces.extend(manifest["traceability"])
        else:
            check_derived_traceability(manifest["traceability"], entries, pack_bodies)
            obligations += len(manifest["traceability"])
        check_filing(manifest, entries, status)
        if rules.filed_at_import and status == "filed-open":
            check_native_record(manifest, entries)
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

    check_global_invariants(stage_owners, statuses, issues, bodies, traces, legacy_ids)
    if mirror:
        for path in all_paths:
            other = mirror / path.relative_to(root)
            require(
                other.is_file() and path.read_bytes() == other.read_bytes(),
                f"Mirror differs: {path.relative_to(root)}",
            )
    epics = sum(item["kind"] == "epic" for item in issues.values())
    children = len(issues) - epics
    return (
        f"Roadmaps valid: {epics} epics, {children} children, "
        f"{len(traces) + obligations} review obligations; "
        f"{next(iter(statuses))}; links and DAG OK."
    )


def main() -> None:
    """Run the read-only pack validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mirror", type=Path)
    args = parser.parse_args()
    try:
        print(
            check_packs(
                args.root.resolve(), args.mirror.resolve() if args.mirror else None
            )
        )
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(1, f"Roadmap validation failed: {error}\n")


if __name__ == "__main__":
    main()
