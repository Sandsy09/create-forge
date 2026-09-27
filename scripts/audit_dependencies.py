"""Audits this repository's locked dependencies for known vulnerabilities.

Dependabot and `scripts/check_workflows.py` keep dependencies current and
Actions pinned, but neither checks a resolved version against a vulnerability
database. This closes that gap with `uv audit` (preview), which reads
`uv.lock` directly and queries OSV.

Three scopes are audited and reported separately, derived from
`pyproject.toml` rather than hardcoded, so a new dependency group or extra
narrows the right scope automatically:

- `runtime`: `[project.dependencies]` and what they lock -- the graph the
  published wheel depends on. A finding here is provider-actionable.
- one scope per optional extra (today, only `legacy`): the runtime graph plus
  that extra.
- `full`: every extra and every dependency group -- the whole lock. Findings
  here that are not already in a narrower scope are development-only: they
  never reach a consumer, but still fail, labelled `[full]`.

`uv audit --no-default-groups`/`--only-dev` do **not** narrow the audit (both
still cover the whole graph); only `--no-group <name>` does. So each scope's
`audited_packages` is cross-checked against an independent `uv export` count,
and a mismatch fails closed as scope drift, rather than silently auditing more
than the label claims.

Outcomes are kept distinct: clean, findings, a service outage (only
recognised connection failure text; downgradeable to a warning via
`--on-outage warn`, but never reported as clean), and a tool error (anything
else, including a stale lock -- always fails). An unexpected JSON schema, an
exit code that disagrees with the report, or scope drift are reported as
interface drift and always fail, so a new uv interface fails visibly instead
of passing quietly.

`.github/audit-exceptions.toml` is the only way to accept a finding: one
package, one advisory, an owner, a rationale, and an expiry at most 90 days
out. See `docs/dependency-audit.md` (ADR 0059) for the full contract.

Usage:
    uv run poe audit                        # fail on an outage too
    uv run poe audit -- --on-outage warn    # report an outage, don't fail
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "uv.lock"
DEFAULT_EXCEPTIONS = REPO_ROOT / ".github" / "audit-exceptions.toml"

_SCHEMA_VERSION = "preview"
_MAX_EXCEPTION_DAYS = 90
_REQUIRED_EXCEPTION_KEYS = frozenset(
    {"id", "package", "rationale", "owner", "added", "expires"}
)

# Only this recognised connection-failure text may be treated as an outage
# rather than a tool error -- verified against a real unreachable
# `--service-url` (see docs/dependency-audit.md's evidence).
_OUTAGE_PATTERNS = (
    re.compile(r"Request failed after \d+ retries"),
    re.compile(r"error sending request for url"),
)

# Strips `scheme://user:pass@` and a query string from anything echoed, so a
# credential-bearing service URL never reaches a log.
_USERINFO_RE = re.compile(r"://[^/\s@]+@")
_QUERY_RE = re.compile(r"\?[^\s'\")]*")


def _sanitize(text: str) -> str:
    """Strip embedded credentials and query strings before this is printed."""
    text = _USERINFO_RE.sub("://", text)
    return _QUERY_RE.sub("", text)


# -----------------------------------------------------------------------------
# Scopes
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScopeSpec:
    """One audited scope: which packages it covers and how to ask uv for it."""

    name: str
    audit_args: tuple[str, ...]
    export_args: tuple[str, ...]
    floor_relevant: bool
    """Whether a finding here should prompt the declared-floor review -- true
    for runtime and every extra, false for `full` (development-only)."""


def discover_groups(pyproject: dict[str, Any]) -> tuple[str, ...]:
    """Dependency group names declared in `[dependency-groups]`, sorted."""
    return tuple(sorted(pyproject.get("dependency-groups", {})))


def discover_extras(pyproject: dict[str, Any]) -> tuple[str, ...]:
    """Optional extra names declared in `[project.optional-dependencies]`."""
    return tuple(sorted(pyproject.get("project", {}).get("optional-dependencies", {})))


def _flags(flag: str, values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        result += [flag, value]
    return tuple(result)


def build_scopes(pyproject: dict[str, Any]) -> tuple[ScopeSpec, ...]:
    """The scopes to audit: `runtime`, one per extra, then `full`.

    `uv audit`'s default already covers every extra and group (verified: 73
    packages on this lock with no flags at all), so `full` needs none. Every
    narrower scope must instead say what to *exclude*.
    """
    groups = discover_groups(pyproject)
    extras = discover_extras(pyproject)
    no_groups = _flags("--no-group", groups)

    scopes = [
        ScopeSpec(
            name="runtime",
            audit_args=_flags("--no-extra", extras) + no_groups,
            export_args=("--no-default-groups",),
            floor_relevant=True,
        )
    ]
    for extra in extras:
        other_extras = tuple(e for e in extras if e != extra)
        scopes.append(
            ScopeSpec(
                name=extra,
                audit_args=_flags("--no-extra", other_extras) + no_groups,
                export_args=("--no-default-groups", "--extra", extra),
                floor_relevant=True,
            )
        )
    scopes.append(
        ScopeSpec(
            name="full",
            audit_args=(),
            export_args=("--all-extras", "--all-groups"),
            floor_relevant=False,
        )
    )
    return tuple(scopes)


def audit_argv(scope: ScopeSpec) -> list[str]:
    """The `uv audit` command line for one scope."""
    return ["uv", "audit", "--frozen", "--output-format", "json", *scope.audit_args]


def export_argv(scope: ScopeSpec) -> list[str]:
    """The independent `uv export` command line used to cross-check a scope."""
    return [
        "uv",
        "export",
        "--frozen",
        "--no-hashes",
        "--no-emit-project",
        "--no-header",
        "--no-annotate",
        *scope.export_args,
    ]


def count_export_lines(stdout: bytes) -> int:
    """Count the packages an export lists: one non-comment, non-blank line each."""
    text = stdout.decode("utf-8", errors="replace")
    return sum(
        1
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


# -----------------------------------------------------------------------------
# Running uv
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandResult:
    """A finished subprocess, captured as bytes -- never `text=True`."""

    returncode: int
    stdout: bytes
    stderr: bytes


Runner = Callable[[list[str]], CommandResult]


def _default_runner(argv: list[str]) -> CommandResult:
    """Runs a fixed uv subcommand with reviewed, non-shell arguments."""
    proc = subprocess.run(  # noqa: S603 -- fixed "uv" subcommands, args built above
        argv, capture_output=True, check=False
    )
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


# -----------------------------------------------------------------------------
# Findings and outcomes
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finding:
    """One advisory matched against a locked package.

    Identity fields (`id`, `aliases`, `package`, `version`) are required and
    strict; a missing one is interface drift, not a finding with a hole in
    it. Descriptive fields may be null -- a real OSV entry has a null
    `summary` (see `tests/fixtures/dependency_audit/vulnerable.json`).
    """

    id: str
    aliases: tuple[str, ...]
    package: str
    version: str
    fix_versions: tuple[str, ...]
    summary: str | None
    link: str | None
    modified: str | None


def _parse_findings(raw: list[Any]) -> list[Finding]:
    """Parse `uv audit`'s `vulnerabilities` array.

    Raises:
        KeyError: an entry is missing an identity field -- the caller treats
            this as interface drift.
    """
    findings = []
    for entry in raw:
        dependency = entry["dependency"]
        findings.append(
            Finding(
                id=entry["id"],
                aliases=tuple(entry.get("aliases") or ()),
                package=dependency["name"],
                version=dependency["version"],
                fix_versions=tuple(entry.get("fix_versions") or ()),
                summary=entry.get("summary"),
                link=entry.get("link"),
                modified=entry.get("modified"),
            )
        )
    return findings


class ScopeOutcome(StrEnum):
    """What happened when one scope was audited -- kept distinct on purpose."""

    CLEAN = "clean"
    FINDINGS = "findings"
    OUTAGE = "outage"
    TOOL_ERROR = "tool_error"
    DRIFT = "drift"


@dataclass(frozen=True, slots=True)
class ScopeAuditData:
    """The parsed, trusted contents of a clean or findings-bearing report."""

    audited_packages: int
    findings: tuple[Finding, ...]
    adverse_statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScopeReport:
    """The outcome of auditing (and cross-checking) one scope."""

    scope: ScopeSpec
    outcome: ScopeOutcome
    data: ScopeAuditData | None
    detail: str
    """Human-readable stderr or reasoning; empty for clean/findings."""


def _decode_json_object(data: bytes) -> tuple[dict[str, Any] | None, str]:
    """Decode `data` as a UTF-8 JSON object; `(None, reason)` if it is not."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"stdout was not valid UTF-8: {exc}"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"stdout was not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "stdout JSON was not an object"
    return parsed, ""


def _adverse_status_labels(raw: list[Any]) -> tuple[str, ...]:
    """Render each adverse status (e.g. a deprecated package) as one line."""
    labels = []
    for entry in raw:
        if isinstance(entry, dict) and "dependency" in entry:
            dep = entry["dependency"]
            labels.append(f"{dep.get('name', '?')} {dep.get('version', '?')}: {entry}")
        else:
            labels.append(str(entry))
    return tuple(labels)


_EXIT_TOOL_ERROR = 2


def _classify_report(
    report: dict[str, Any], returncode: int
) -> tuple[ScopeOutcome, ScopeAuditData | None, str]:
    """Classify a decoded exit-0/1 report against the exit code it came with."""
    try:
        schema_version = report["schema"]["version"]
        summary = report["summary"]
        audited_packages = summary["audited_packages"]
        reported_count = summary["vulnerabilities"]
        raw_findings = report["vulnerabilities"]
        raw_adverse = report.get("adverse_statuses", [])
    except (KeyError, TypeError) as exc:
        return ScopeOutcome.DRIFT, None, f"unexpected JSON shape: {exc!r}"
    if schema_version != _SCHEMA_VERSION:
        drifted = f"unexpected schema version {schema_version!r}"
        return ScopeOutcome.DRIFT, None, drifted
    if not isinstance(raw_findings, list) or reported_count != len(raw_findings):
        return ScopeOutcome.DRIFT, None, "vulnerability count disagrees with the list"
    has_findings = len(raw_findings) > 0
    if (returncode == 0) == has_findings:
        found = "having" if has_findings else "having no"
        drifted = f"exit code {returncode} disagrees with {found} findings"
        return ScopeOutcome.DRIFT, None, drifted
    try:
        findings = _parse_findings(raw_findings)
    except (KeyError, TypeError) as exc:
        drifted = f"a finding was missing an identity field: {exc!r}"
        return ScopeOutcome.DRIFT, None, drifted
    data = ScopeAuditData(
        audited_packages=audited_packages,
        findings=tuple(findings),
        adverse_statuses=_adverse_status_labels(raw_adverse),
    )
    outcome = ScopeOutcome.FINDINGS if has_findings else ScopeOutcome.CLEAN
    return outcome, data, ""


def classify(result: CommandResult) -> tuple[ScopeOutcome, ScopeAuditData | None, str]:
    """Classify one `uv audit` invocation's raw result.

    Exit 0/1 must carry a well-formed `preview`-schema report that agrees
    with the exit code; anything else at those codes is drift, not a finding
    with a quirk. Exit 2 is a service outage only for recognised connection
    text; every other failure -- including a stale lock -- is a tool error.
    """
    if result.returncode in (0, 1):
        report, reason = _decode_json_object(result.stdout)
        if report is None:
            return ScopeOutcome.DRIFT, None, reason
        return _classify_report(report, result.returncode)

    stderr_text = result.stderr.decode("utf-8", errors="replace")
    if result.returncode == _EXIT_TOOL_ERROR and any(
        p.search(stderr_text) for p in _OUTAGE_PATTERNS
    ):
        return ScopeOutcome.OUTAGE, None, stderr_text
    return (
        ScopeOutcome.TOOL_ERROR,
        None,
        stderr_text or f"unexpected exit code {result.returncode}",
    )


class _AuditScopeInvariantError(AssertionError):
    """`classify()` promised data for clean/findings; this means it lied."""


def audit_scope(scope: ScopeSpec, runner: Runner) -> ScopeReport:
    """Audit one scope and, if it produced a report, cross-check its size."""
    outcome, data, detail = classify(runner(audit_argv(scope)))
    if outcome in (ScopeOutcome.CLEAN, ScopeOutcome.FINDINGS):
        if data is None:
            raise _AuditScopeInvariantError(scope.name)
        export_result = runner(export_argv(scope))
        if export_result.returncode != 0:
            detail = (
                "uv export failed for the scope cross-check: "
                f"{export_result.stderr.decode('utf-8', errors='replace')}"
            )
            return ScopeReport(scope, ScopeOutcome.DRIFT, data, detail)
        exported = count_export_lines(export_result.stdout)
        if exported != data.audited_packages:
            detail = (
                f"scope drift: 'uv audit' reported {data.audited_packages} "
                f"audited packages for {scope.name!r}, but 'uv export' "
                f"independently counted {exported}"
            )
            return ScopeReport(scope, ScopeOutcome.DRIFT, data, detail)
    return ScopeReport(scope, outcome, data, detail)


def attribute_findings(
    reports: tuple[ScopeReport, ...],
) -> list[tuple[ScopeSpec, Finding]]:
    """Attach each finding to the narrowest scope that contains it.

    `reports` is iterated in the order `build_scopes` produced -- runtime,
    then each extra, then `full` -- each a superset of the ones before it, so
    the first scope a finding appears in is its narrowest.
    """
    seen: set[tuple[str, str, str]] = set()
    attributed: list[tuple[ScopeSpec, Finding]] = []
    for report in reports:
        if report.data is None:
            continue
        for finding in report.data.findings:
            key = (finding.id, finding.package, finding.version)
            if key in seen:
                continue
            seen.add(key)
            attributed.append((report.scope, finding))
    return attributed


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class ExceptionsFileError(RuntimeError):
    """`.github/audit-exceptions.toml` is malformed; the audit fails closed."""


@dataclass(frozen=True, slots=True)
class AuditException:
    """One reviewed, scoped, expiring exemption for a single advisory."""

    id: str
    package: str
    rationale: str
    owner: str
    added: dt.date
    expires: dt.date


def _coerce_date(value: Any, *, where: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ExceptionsFileError(f"{where}: {value!r} is not an ISO date") from exc
    raise ExceptionsFileError(f"{where}: must be a date, got {value!r}")


def _parse_one_exception(entry: Any, *, where: str, today: dt.date) -> AuditException:
    if not isinstance(entry, dict):
        raise ExceptionsFileError(f"{where}: must be a table")
    keys = set(entry)
    missing = _REQUIRED_EXCEPTION_KEYS - keys
    if missing:
        raise ExceptionsFileError(f"{where}: missing required key(s) {sorted(missing)}")
    extra = keys - _REQUIRED_EXCEPTION_KEYS
    if extra:
        raise ExceptionsFileError(f"{where}: unknown key(s) {sorted(extra)}")
    for text_key in ("id", "package", "rationale", "owner"):
        if not isinstance(entry[text_key], str) or not entry[text_key].strip():
            raise ExceptionsFileError(
                f"{where}: {text_key!r} must be a non-empty string"
            )
    if entry["id"] == "*" or entry["package"] == "*":
        raise ExceptionsFileError(f"{where}: wildcard exceptions are not allowed")

    added = _coerce_date(entry["added"], where=f"{where}.added")
    expires = _coerce_date(entry["expires"], where=f"{where}.expires")
    if added > today:
        raise ExceptionsFileError(f"{where}: 'added' ({added}) is in the future")
    if expires < added:
        raise ExceptionsFileError(
            f"{where}: 'expires' ({expires}) is before 'added' ({added})"
        )
    if (expires - added).days > _MAX_EXCEPTION_DAYS:
        raise ExceptionsFileError(
            f"{where}: exception lifetime exceeds {_MAX_EXCEPTION_DAYS} days "
            f"({added} to {expires}); re-review and renew instead of extending"
        )
    return AuditException(
        id=entry["id"],
        package=entry["package"],
        rationale=entry["rationale"],
        owner=entry["owner"],
        added=added,
        expires=expires,
    )


def parse_exceptions(path: Path, *, today: dt.date) -> tuple[AuditException, ...]:
    """Parse and validate `.github/audit-exceptions.toml`; `()` if absent.

    Raises:
        ExceptionsFileError: the file does not parse, or any entry is
            malformed -- the whole audit fails closed rather than silently
            dropping one bad entry.
    """
    if not path.is_file():
        return ()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ExceptionsFileError(f"{path}: invalid TOML: {exc}") from exc
    raw_entries = data.get("exception", [])
    if not isinstance(raw_entries, list):
        raise ExceptionsFileError(f"{path}: 'exception' must be an array of tables")
    return tuple(
        _parse_one_exception(entry, where=f"{path}: exception[{i}]", today=today)
        for i, entry in enumerate(raw_entries)
    )


def _matches(finding: Finding, exception: AuditException) -> bool:
    return finding.package == exception.package and (
        finding.id == exception.id or exception.id in finding.aliases
    )


@dataclass(frozen=True, slots=True)
class AppliedFindings:
    """Attributed findings, split by what an exceptions file did to them."""

    active: tuple[tuple[ScopeSpec, Finding], ...]
    suppressed: tuple[tuple[ScopeSpec, Finding, AuditException], ...]
    lapsed: tuple[tuple[ScopeSpec, Finding, AuditException], ...]
    matched_exception_keys: frozenset[tuple[str, str]]


def apply_exceptions(
    attributed: list[tuple[ScopeSpec, Finding]],
    exceptions: tuple[AuditException, ...],
    *,
    today: dt.date,
) -> AppliedFindings:
    """Suppress findings a valid, unexpired exception covers.

    A lapsed exception (`today > expires`) stops suppressing: its finding
    re-joins `active` and is also reported in `lapsed`, named, so the output
    says exactly which exception expired rather than just failing anew.
    """
    active: list[tuple[ScopeSpec, Finding]] = []
    suppressed: list[tuple[ScopeSpec, Finding, AuditException]] = []
    lapsed: list[tuple[ScopeSpec, Finding, AuditException]] = []
    matched_keys: set[tuple[str, str]] = set()

    for scope, finding in attributed:
        match = next((exc for exc in exceptions if _matches(finding, exc)), None)
        if match is None:
            active.append((scope, finding))
            continue
        matched_keys.add((match.id, match.package))
        if today <= match.expires:
            suppressed.append((scope, finding, match))
        else:
            lapsed.append((scope, finding, match))
            active.append((scope, finding))

    return AppliedFindings(
        tuple(active), tuple(suppressed), tuple(lapsed), frozenset(matched_keys)
    )


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


def _locked_version(lockfile: Path, name: str) -> str | None:
    """The version `uv.lock` records for `name`, or `None` if it is absent."""
    if not lockfile.is_file():
        return None
    data = tomllib.loads(lockfile.read_text(encoding="utf-8"))
    for package in data.get("package", []):
        if package.get("name") == name:
            version = package.get("version")
            return version if isinstance(version, str) else None
    return None


def _fix_hint(finding: Finding) -> str:
    if finding.fix_versions:
        return (
            f"fix: {', '.join(finding.fix_versions)} "
            f"(uv lock --upgrade-package {finding.package})"
        )
    return "no fixed version yet -- add a reviewed exception, or replace the dependency"


@dataclass(frozen=True, slots=True)
class AuditRun:
    """Everything one full `main()` invocation needs to render its report."""

    scope_reports: tuple[ScopeReport, ...]
    applied: AppliedFindings
    stale_exceptions: tuple[AuditException, ...]
    uv_version: str
    query_time: dt.datetime
    locked_forge_template: str | None


def _render_header(run: AuditRun) -> list[str]:
    lines = [
        "# Dependency audit",
        f"- Scanner: uv audit {run.uv_version}",
        f"- Query time (UTC): {run.query_time.isoformat()}",
    ]
    if run.locked_forge_template:
        lines.append(f"- forge-template (locked): {run.locked_forge_template}")
    lines += ["", "| Scope | Outcome | Audited packages |", "| --- | --- | --- |"]
    for report in run.scope_reports:
        audited = report.data.audited_packages if report.data else "-"
        lines.append(f"| {report.scope.name} | {report.outcome.value} | {audited} |")
    return lines


def _render_active_findings(applied: AppliedFindings) -> list[str]:
    if not applied.active:
        return []
    lines = ["\n## Findings (fail)\n"]
    for scope, finding in applied.active:
        aliases = ", ".join(finding.aliases) or "no aliases"
        summary = finding.summary or "(no summary)"
        lines.append(
            f"- [{scope.name}] {finding.id} ({aliases}) "
            f"{finding.package} {finding.version} -- {summary}"
        )
        lines.append(f"    {_fix_hint(finding)}")
        if finding.link:
            lines.append(f"    {finding.link}")
        if scope.floor_relevant and not finding.fix_versions:
            lines.append(
                "    review the declared floor: a lock-only upgrade does not "
                "by itself change what the published wheel permits"
            )
    return lines


def _render_suppressed(applied: AppliedFindings) -> list[str]:
    if not applied.suppressed:
        return []
    lines = ["\n## Suppressed by exception\n"]
    for scope, finding, exc in applied.suppressed:
        lines.append(
            f"- [{scope.name}] {finding.id} {finding.package} -- {exc.owner}: "
            f"{exc.rationale} (expires {exc.expires})"
        )
    return lines


def _render_lapsed(applied: AppliedFindings) -> list[str]:
    if not applied.lapsed:
        return []
    lines = ["\n## Lapsed exceptions (now failing again)\n"]
    lines += [
        f"- {exc.id} {exc.package} expired {exc.expires}, added by {exc.owner}"
        for _scope, _finding, exc in applied.lapsed
    ]
    return lines


def _render_stale(stale_exceptions: tuple[AuditException, ...]) -> list[str]:
    if not stale_exceptions:
        return []
    lines = ["\n## Stale exceptions (no matching finding)\n"]
    lines += [
        f"- {exc.id} {exc.package} (owner {exc.owner}) -- consider removing"
        for exc in stale_exceptions
    ]
    return lines


def _render_scope_diagnostic(report: ScopeReport) -> list[str]:
    """Adverse statuses (warning only), plus an outage/tool-error/drift block."""
    lines = []
    if report.data and report.data.adverse_statuses:
        lines.append(f"\n## {report.scope.name}: adverse statuses (warning only)\n")
        lines += [f"- {status}" for status in report.data.adverse_statuses]
    if report.outcome == ScopeOutcome.OUTAGE:
        lines.append(f"\n## {report.scope.name}: SERVICE OUTAGE -- AUDIT DID NOT RUN\n")
        lines.append("This is NOT A CLEAN RESULT.")
        lines.append(f"```\n{_sanitize(report.detail)}\n```")
    elif report.outcome in (ScopeOutcome.TOOL_ERROR, ScopeOutcome.DRIFT):
        lines.append(f"\n## {report.scope.name}: {report.outcome.value}\n")
        lines.append(f"```\n{_sanitize(report.detail)}\n```")
    return lines


def render_report(run: AuditRun) -> str:
    """Render the full audit report as Markdown-ish plain text."""
    lines = _render_header(run)
    lines += _render_active_findings(run.applied)
    lines += _render_suppressed(run.applied)
    lines += _render_lapsed(run.applied)
    lines += _render_stale(run.stale_exceptions)
    for report in run.scope_reports:
        lines += _render_scope_diagnostic(report)
    return "\n".join(lines)


def final_exit_code(
    scope_reports: tuple[ScopeReport, ...], applied: AppliedFindings, *, on_outage: str
) -> int:
    """Overall exit code, worst first: drift, tool error, findings, outage, clean."""
    if any(r.outcome == ScopeOutcome.DRIFT for r in scope_reports):
        return 1
    if any(r.outcome == ScopeOutcome.TOOL_ERROR for r in scope_reports):
        return 1
    if applied.active:
        return 1
    if any(r.outcome == ScopeOutcome.OUTAGE for r in scope_reports):
        return 0 if on_outage == "warn" else 1
    return 0


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    """Run the full audit and print its report.

    `runner` is an injection point for tests; the real CLI always uses the
    default, which calls `uv` as a subprocess.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0] if __doc__ else ""
    )
    parser.add_argument(
        "--on-outage",
        choices=["warn", "fail"],
        default="fail",
        help="warn (and pass) or fail when the advisory service is unreachable",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=DEFAULT_EXCEPTIONS,
        help="path to the exceptions TOML (default: .github/audit-exceptions.toml)",
    )
    parser.add_argument(
        "--pyproject", type=Path, default=PYPROJECT, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--lockfile", type=Path, default=LOCKFILE, help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    run = runner or _default_runner

    today = dt.datetime.now(dt.UTC).date()
    try:
        exceptions = parse_exceptions(args.exceptions, today=today)
    except ExceptionsFileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    pyproject = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))
    scopes = build_scopes(pyproject)
    query_time = dt.datetime.now(dt.UTC)
    scope_reports = tuple(audit_scope(scope, run) for scope in scopes)

    attributed = attribute_findings(scope_reports)
    applied = apply_exceptions(attributed, exceptions, today=today)
    stale = tuple(
        exc
        for exc in exceptions
        if (exc.id, exc.package) not in applied.matched_exception_keys
    )

    uv_version_raw = run(["uv", "--version"]).stdout
    uv_version = uv_version_raw.decode("utf-8", errors="replace").strip()
    locked_forge_template = _locked_version(args.lockfile, "forge-template")

    audit_run = AuditRun(
        scope_reports=scope_reports,
        applied=applied,
        stale_exceptions=stale,
        uv_version=uv_version,
        query_time=query_time,
        locked_forge_template=locked_forge_template,
    )
    report_text = render_report(audit_run)
    print(report_text)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary_file:
            summary_file.write(report_text + "\n")

    return final_exit_code(scope_reports, applied, on_outage=args.on_outage)


if __name__ == "__main__":
    sys.exit(main())
