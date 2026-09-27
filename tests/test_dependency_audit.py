"""Tests for scripts/audit_dependencies.py against real fixtures and workflows.

`scripts` is on `pythonpath` (see `[tool.pytest.ini_options]` in
pyproject.toml), so this imports the module directly, matching
`tests/test_workflows.py` and `tests/test_adr.py`.

No network: every `uv audit`/`uv export` call is a fake `Runner`, using
either constructed JSON or the real recorded fixtures under
`tests/fixtures/dependency_audit/`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

from audit_dependencies import (
    AppliedFindings,
    AuditException,
    AuditRun,
    CommandResult,
    ExceptionsFileError,
    Finding,
    Runner,
    ScopeAuditData,
    ScopeOutcome,
    ScopeReport,
    ScopeSpec,
    _sanitize,
    apply_exceptions,
    attribute_findings,
    audit_argv,
    audit_scope,
    build_scopes,
    classify,
    count_export_lines,
    discover_extras,
    discover_groups,
    export_argv,
    final_exit_code,
    main,
    parse_exceptions,
    render_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "dependency_audit"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
EXCEPTIONS_FILE = REPO_ROOT / ".github" / "audit-exceptions.toml"

TODAY = dt.date(2026, 9, 27)


def _real_pyproject() -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _clean_json(count: int) -> bytes:
    payload = {
        "schema": {"version": "preview"},
        "summary": {
            "audited_packages": count,
            "vulnerabilities": 0,
            "adverse_statuses": 0,
        },
        "vulnerabilities": [],
        "adverse_statuses": [],
    }
    return json.dumps(payload).encode()


def _vuln(id_: str, package: str, **overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "version": "1.0",
        "aliases": [],
        "fix_versions": ["2.0"],
        "summary": "a bad thing happens",
    }
    defaults.update(overrides)
    return {
        "dependency": {"name": package, "version": defaults.pop("version")},
        "id": id_,
        "link": f"https://example.invalid/{id_}",
        "modified": "2026-01-01T00:00:00Z",
        **defaults,
    }


def _findings_json(count: int, vulns: list[dict[str, Any]]) -> bytes:
    payload = {
        "schema": {"version": "preview"},
        "summary": {
            "audited_packages": count,
            "vulnerabilities": len(vulns),
            "adverse_statuses": 0,
        },
        "vulnerabilities": vulns,
        "adverse_statuses": [],
    }
    return json.dumps(payload).encode()


def _export_bytes(count: int) -> bytes:
    return "\n".join(f"pkg{i}==1.0" for i in range(count)).encode() + b"\n"


def _finding(id_: str = "GHSA-1", package: str = "pkg", **kwargs: Any) -> Finding:
    defaults: dict[str, Any] = {
        "aliases": (),
        "version": "1.0",
        "fix_versions": (),
        "summary": None,
        "link": None,
        "modified": None,
    }
    defaults.update(kwargs)
    return Finding(id=id_, package=package, **defaults)


_SCOPE = ScopeSpec(
    name="runtime",
    audit_args=(),
    export_args=("--no-default-groups",),
    floor_relevant=True,
)
_FULL_SCOPE = ScopeSpec(
    name="full",
    audit_args=(),
    export_args=("--all-extras", "--all-groups"),
    floor_relevant=False,
)


def _scope_report(
    scope: ScopeSpec,
    outcome: ScopeOutcome,
    findings: list[Finding],
    *,
    audited: int = 10,
) -> ScopeReport:
    data = None
    if outcome in (ScopeOutcome.CLEAN, ScopeOutcome.FINDINGS):
        data = ScopeAuditData(
            audited_packages=audited, findings=tuple(findings), adverse_statuses=()
        )
    return ScopeReport(scope, outcome, data, "")


def _exc(id_: str = "GHSA-1", package: str = "pkg", **overrides: Any) -> AuditException:
    defaults: dict[str, Any] = {
        "rationale": "no fix yet",
        "owner": "alex",
        "added": dt.date(2026, 9, 1),
        "expires": dt.date(2026, 11, 25),
    }
    defaults.update(overrides)
    return AuditException(id=id_, package=package, **defaults)


# -----------------------------------------------------------------------------
# Scope discovery and construction
# -----------------------------------------------------------------------------


def test_discover_groups_matches_real_pyproject() -> None:
    assert discover_groups(_real_pyproject()) == (
        "dev",
        "docs",
        "lint",
        "test",
        "typecheck",
    )


def test_discover_extras_matches_real_pyproject() -> None:
    assert discover_extras(_real_pyproject()) == ("legacy",)


def test_build_scopes_orders_runtime_then_each_extra_then_full() -> None:
    scopes = build_scopes(_real_pyproject())
    assert [s.name for s in scopes] == ["runtime", "legacy", "full"]
    assert scopes[0].floor_relevant is True
    assert scopes[1].floor_relevant is True
    assert scopes[-1].floor_relevant is False


def test_build_scopes_with_no_groups_or_extras() -> None:
    scopes = build_scopes({"project": {}, "dependency-groups": {}})
    assert [s.name for s in scopes] == ["runtime", "full"]
    assert scopes[0].export_args == ("--no-default-groups",)
    assert scopes[1].export_args == ("--all-extras", "--all-groups")


def test_runtime_scope_excludes_groups_via_no_group_not_no_default_groups() -> None:
    """`--no-default-groups` is silently ineffective on `uv audit` (verified:
    still audits the whole graph); only `--no-group <name>` narrows it.
    """
    runtime = build_scopes(_real_pyproject())[0]
    assert "--no-default-groups" not in runtime.audit_args
    assert runtime.audit_args.count("--no-group") == len(
        discover_groups(_real_pyproject())
    )


def test_count_export_lines_ignores_comments_and_blanks() -> None:
    text = b"# header\n\npkg-a==1.0\npkg-b==2.0\n\n# trailer\n"
    assert count_export_lines(text) == 2


# -----------------------------------------------------------------------------
# classify() -- constructed edge cases
# -----------------------------------------------------------------------------


def test_classify_clean() -> None:
    outcome, data, detail = classify(CommandResult(0, _clean_json(5), b""))
    assert outcome is ScopeOutcome.CLEAN
    assert data is not None
    assert data.audited_packages == 5
    assert detail == ""


def test_classify_findings() -> None:
    vulns = [_vuln("GHSA-1", "pkg")]
    outcome, data, _ = classify(CommandResult(1, _findings_json(3, vulns), b""))
    assert outcome is ScopeOutcome.FINDINGS
    assert data is not None
    assert data.findings[0].id == "GHSA-1"


def test_classify_tolerates_null_descriptive_fields() -> None:
    vuln = _vuln("GHSA-1", "pkg", summary=None)
    vuln["link"] = None
    vuln["modified"] = None
    outcome, data, _ = classify(CommandResult(1, _findings_json(1, [vuln]), b""))
    assert outcome is ScopeOutcome.FINDINGS
    assert data is not None
    assert data.findings[0].summary is None


def test_classify_outage_from_recognised_connection_text() -> None:
    stderr = (FIXTURES / "outage_stderr.txt").read_bytes()
    outcome, data, detail = classify(CommandResult(2, b"", stderr))
    assert outcome is ScopeOutcome.OUTAGE
    assert data is None
    assert "Request failed after" in detail


def test_classify_tool_error_on_stale_lock() -> None:
    stderr = (FIXTURES / "tool_error_stderr.txt").read_bytes()
    outcome, data, _ = classify(CommandResult(2, b"", stderr))
    assert outcome is ScopeOutcome.TOOL_ERROR
    assert data is None


def test_classify_unrecognised_exit_code_is_a_tool_error() -> None:
    outcome, _, _ = classify(CommandResult(5, b"", b"boom"))
    assert outcome is ScopeOutcome.TOOL_ERROR


def test_classify_invalid_json_is_drift() -> None:
    outcome, data, _ = classify(CommandResult(0, b"not json", b""))
    assert outcome is ScopeOutcome.DRIFT
    assert data is None


def test_classify_drift_on_unexpected_schema_version() -> None:
    bad = json.loads(_clean_json(5))
    bad["schema"]["version"] = "v2"
    outcome, _, detail = classify(CommandResult(0, json.dumps(bad).encode(), b""))
    assert outcome is ScopeOutcome.DRIFT
    assert "schema version" in detail


def test_classify_drift_on_missing_identity_key() -> None:
    bad = json.loads(_findings_json(1, [_vuln("GHSA-1", "pkg")]))
    del bad["vulnerabilities"][0]["dependency"]
    outcome, _, _ = classify(CommandResult(1, json.dumps(bad).encode(), b""))
    assert outcome is ScopeOutcome.DRIFT


def test_classify_drift_when_exit_zero_but_report_has_findings() -> None:
    payload = json.loads(_findings_json(2, [_vuln("GHSA-1", "pkg")]))
    outcome, _, _ = classify(CommandResult(0, json.dumps(payload).encode(), b""))
    assert outcome is ScopeOutcome.DRIFT


def test_classify_drift_when_exit_one_but_report_is_clean() -> None:
    payload = json.loads(_clean_json(5))
    outcome, _, _ = classify(CommandResult(1, json.dumps(payload).encode(), b""))
    assert outcome is ScopeOutcome.DRIFT


def test_classify_drift_on_vulnerability_count_mismatch() -> None:
    payload = json.loads(_findings_json(2, [_vuln("GHSA-1", "pkg")]))
    payload["summary"]["vulnerabilities"] = 5
    outcome, _, _ = classify(CommandResult(1, json.dumps(payload).encode(), b""))
    assert outcome is ScopeOutcome.DRIFT


# -----------------------------------------------------------------------------
# classify() -- real recorded fixtures
# -----------------------------------------------------------------------------


def test_classify_real_clean_fixture_from_this_repo() -> None:
    outcome, data, _ = classify(
        CommandResult(0, (FIXTURES / "clean.json").read_bytes(), b"")
    )
    assert outcome is ScopeOutcome.CLEAN
    assert data is not None
    assert data.audited_packages == 22


def test_classify_real_vulnerable_fixture_has_a_null_summary() -> None:
    """A real OSV entry (`PYSEC-2021-108`) has `summary: null`."""
    outcome, data, _ = classify(
        CommandResult(1, (FIXTURES / "vulnerable.json").read_bytes(), b"")
    )
    assert outcome is ScopeOutcome.FINDINGS
    assert data is not None
    by_id = {f.id: f for f in data.findings}
    assert by_id["PYSEC-2021-108"].summary is None
    assert "CVE-2021-33503" in by_id["PYSEC-2021-108"].aliases


# -----------------------------------------------------------------------------
# audit_scope() -- the export cross-check
# -----------------------------------------------------------------------------


def _runner_for(
    audit_result: CommandResult, export_result: CommandResult | None = None
) -> Runner:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> CommandResult:
        calls.append(argv)
        if argv[1] == "audit":
            return audit_result
        if argv[1] == "export":
            if export_result is None:
                raise AssertionError("export should not have been called")
            return export_result
        raise AssertionError(f"unexpected command: {argv}")

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def test_audit_scope_clean_and_export_agree() -> None:
    runner = _runner_for(
        CommandResult(0, _clean_json(3), b""), CommandResult(0, _export_bytes(3), b"")
    )
    report = audit_scope(_SCOPE, runner)
    assert report.outcome is ScopeOutcome.CLEAN
    assert report.data is not None
    assert report.data.audited_packages == 3


def test_audit_scope_flags_scope_drift_on_count_mismatch() -> None:
    runner = _runner_for(
        CommandResult(0, _clean_json(3), b""), CommandResult(0, _export_bytes(5), b"")
    )
    report = audit_scope(_SCOPE, runner)
    assert report.outcome is ScopeOutcome.DRIFT
    assert "scope drift" in report.detail


def test_audit_scope_flags_drift_when_export_itself_fails() -> None:
    runner = _runner_for(
        CommandResult(0, _clean_json(3), b""),
        CommandResult(1, b"", b"uv export exploded"),
    )
    report = audit_scope(_SCOPE, runner)
    assert report.outcome is ScopeOutcome.DRIFT


def test_audit_scope_skips_the_cross_check_on_outage() -> None:
    stderr = (FIXTURES / "outage_stderr.txt").read_bytes()
    runner = _runner_for(CommandResult(2, b"", stderr))
    report = audit_scope(_SCOPE, runner)
    assert report.outcome is ScopeOutcome.OUTAGE
    assert len(runner.calls) == 1  # type: ignore[attr-defined]


def test_audit_scope_skips_the_cross_check_on_tool_error() -> None:
    stderr = (FIXTURES / "tool_error_stderr.txt").read_bytes()
    runner = _runner_for(CommandResult(2, b"", stderr))
    report = audit_scope(_SCOPE, runner)
    assert report.outcome is ScopeOutcome.TOOL_ERROR
    assert len(runner.calls) == 1  # type: ignore[attr-defined]


# -----------------------------------------------------------------------------
# Narrowest-scope attribution
# -----------------------------------------------------------------------------


def test_attribute_findings_prefers_the_narrower_scope() -> None:
    shared = _finding("GHSA-1", "pkg-a")
    runtime_report = _scope_report(_SCOPE, ScopeOutcome.FINDINGS, [shared])
    full_report = _scope_report(_FULL_SCOPE, ScopeOutcome.FINDINGS, [shared])
    attributed = attribute_findings((runtime_report, full_report))
    assert attributed == [(_SCOPE, shared)]


def test_attribute_findings_keeps_a_full_only_finding_labelled_full() -> None:
    dev_only = _finding("GHSA-2", "pytest-thing")
    runtime_report = _scope_report(_SCOPE, ScopeOutcome.CLEAN, [])
    full_report = _scope_report(_FULL_SCOPE, ScopeOutcome.FINDINGS, [dev_only])
    attributed = attribute_findings((runtime_report, full_report))
    assert attributed == [(_FULL_SCOPE, dev_only)]


def test_attribute_findings_skips_scopes_with_no_data() -> None:
    outage_report = ScopeReport(_SCOPE, ScopeOutcome.OUTAGE, None, "boom")
    assert attribute_findings((outage_report,)) == []


# -----------------------------------------------------------------------------
# Exceptions file parsing
# -----------------------------------------------------------------------------


def test_parse_exceptions_missing_file_is_empty(tmp_path: Path) -> None:
    assert parse_exceptions(tmp_path / "nope.toml", today=TODAY) == ()


def test_parse_exceptions_real_file_ships_empty() -> None:
    assert parse_exceptions(EXCEPTIONS_FILE, today=TODAY) == ()


def _write_exceptions(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "exceptions.toml"
    path.write_text(body, encoding="utf-8")
    return path


_VALID_ENTRY = (
    "[[exception]]\n"
    'id = "GHSA-1"\n'
    'package = "pkg"\n'
    'rationale = "no fix yet"\n'
    'owner = "alex"\n'
    "added = 2026-09-01\n"
    "expires = 2026-11-25\n"
)


def test_parse_exceptions_accepts_a_valid_entry(tmp_path: Path) -> None:
    path = _write_exceptions(tmp_path, _VALID_ENTRY)
    exceptions = parse_exceptions(path, today=TODAY)
    assert len(exceptions) == 1
    assert exceptions[0] == _exc()


def test_parse_exceptions_accepts_quoted_iso_dates(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace("2026-09-01", '"2026-09-01"').replace(
        "2026-11-25", '"2026-11-25"'
    )
    exceptions = parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    assert exceptions[0].added == dt.date(2026, 9, 1)


def test_parse_exceptions_rejects_unknown_key(tmp_path: Path) -> None:
    body = _VALID_ENTRY + 'severity = "high"\n'
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "unknown key" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_missing_key(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace('owner = "alex"\n', "")
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "missing required key" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_wildcard_package(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace('package = "pkg"', 'package = "*"')
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "wildcard" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_wildcard_id(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace('id = "GHSA-1"', 'id = "*"')
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "wildcard" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_added_in_the_future(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace("added = 2026-09-01", "added = 2026-12-01")
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_expires_before_added(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace("expires = 2026-11-25", "expires = 2026-08-01")
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "before 'added'" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_lifetime_over_90_days(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace("expires = 2026-11-25", "expires = 2026-12-31")
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "90 days" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_a_non_date_value(tmp_path: Path) -> None:
    body = _VALID_ENTRY.replace("added = 2026-09-01", "added = 123")
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "must be a date" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_invalid_toml(tmp_path: Path) -> None:
    try:
        parse_exceptions(_write_exceptions(tmp_path, "not [ valid toml"), today=TODAY)
    except ExceptionsFileError as exc:
        assert "invalid TOML" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


def test_parse_exceptions_rejects_a_non_table_entry(tmp_path: Path) -> None:
    body = 'exception = ["oops"]\n'
    try:
        parse_exceptions(_write_exceptions(tmp_path, body), today=TODAY)
    except ExceptionsFileError as exc:
        assert "must be a table" in str(exc)
    else:
        raise AssertionError("expected ExceptionsFileError")


# -----------------------------------------------------------------------------
# apply_exceptions() -- matching, suppression and expiry
# -----------------------------------------------------------------------------


def test_apply_exceptions_suppresses_an_exact_match() -> None:
    finding = _finding("GHSA-1", "pkg")
    applied = apply_exceptions(
        [(_SCOPE, finding)], (_exc(),), today=dt.date(2026, 9, 27)
    )
    assert applied.active == ()
    assert len(applied.suppressed) == 1
    assert applied.matched_exception_keys == {("GHSA-1", "pkg")}


def test_apply_exceptions_matches_by_alias() -> None:
    finding = _finding("CVE-2025-1", "pkg", aliases=("GHSA-1",))
    applied = apply_exceptions(
        [(_SCOPE, finding)], (_exc(),), today=dt.date(2026, 9, 27)
    )
    assert len(applied.suppressed) == 1


def test_apply_exceptions_requires_the_package_to_match_too() -> None:
    finding = _finding("GHSA-1", "a-different-package")
    applied = apply_exceptions(
        [(_SCOPE, finding)], (_exc(),), today=dt.date(2026, 9, 27)
    )
    assert applied.active == ((_SCOPE, finding),)
    assert applied.suppressed == ()


def test_apply_exceptions_last_day_still_suppresses() -> None:
    finding = _finding("GHSA-1", "pkg")
    exc = _exc(expires=dt.date(2026, 11, 25))
    applied = apply_exceptions([(_SCOPE, finding)], (exc,), today=dt.date(2026, 11, 25))
    assert applied.suppressed == ((_SCOPE, finding, exc),)
    assert applied.active == ()


def test_apply_exceptions_day_after_expiry_lapses_and_reactivates() -> None:
    finding = _finding("GHSA-1", "pkg")
    exc = _exc(expires=dt.date(2026, 11, 25))
    applied = apply_exceptions([(_SCOPE, finding)], (exc,), today=dt.date(2026, 11, 26))
    assert applied.lapsed == ((_SCOPE, finding, exc),)
    assert applied.active == ((_SCOPE, finding),)


def test_apply_exceptions_reports_an_unmatched_exception_as_not_stale_here() -> None:
    """Staleness is computed by the caller from `matched_exception_keys`."""
    exc = _exc(package="unrelated-package")
    applied = apply_exceptions([], (exc,), today=dt.date(2026, 9, 27))
    assert applied.matched_exception_keys == frozenset()


# -----------------------------------------------------------------------------
# final_exit_code() -- worst outcome wins
# -----------------------------------------------------------------------------


_NO_FINDINGS = AppliedFindings((), (), (), frozenset())


def test_final_exit_code_clean_is_zero() -> None:
    assert final_exit_code((), _NO_FINDINGS, on_outage="fail") == 0


def test_final_exit_code_active_findings_always_fail() -> None:
    applied = AppliedFindings(((_SCOPE, _finding()),), (), (), frozenset())
    assert final_exit_code((), applied, on_outage="warn") == 1


def test_final_exit_code_outage_warn_passes() -> None:
    report = ScopeReport(_SCOPE, ScopeOutcome.OUTAGE, None, "boom")
    assert final_exit_code((report,), _NO_FINDINGS, on_outage="warn") == 0


def test_final_exit_code_outage_fail_fails() -> None:
    report = ScopeReport(_SCOPE, ScopeOutcome.OUTAGE, None, "boom")
    assert final_exit_code((report,), _NO_FINDINGS, on_outage="fail") == 1


def test_final_exit_code_drift_always_fails_even_under_warn() -> None:
    report = ScopeReport(_SCOPE, ScopeOutcome.DRIFT, None, "boom")
    assert final_exit_code((report,), _NO_FINDINGS, on_outage="warn") == 1


def test_final_exit_code_tool_error_always_fails_even_under_warn() -> None:
    report = ScopeReport(_SCOPE, ScopeOutcome.TOOL_ERROR, None, "boom")
    assert final_exit_code((report,), _NO_FINDINGS, on_outage="warn") == 1


# -----------------------------------------------------------------------------
# Sanitisation
# -----------------------------------------------------------------------------


def test_sanitize_strips_userinfo_and_query_string() -> None:
    text = (
        "error sending request for url "
        "(https://svc-user:s3cr3t@osv.example.invalid/v1/query?key=topsecret)"
    )
    sanitized = _sanitize(text)
    assert "svc-user" not in sanitized
    assert "s3cr3t" not in sanitized
    assert "topsecret" not in sanitized
    assert "osv.example.invalid" in sanitized  # the host itself is kept


# -----------------------------------------------------------------------------
# render_report() -- content, not exact formatting
# -----------------------------------------------------------------------------


def test_render_report_includes_findings_suppressions_lapses_and_stale() -> None:
    active_finding = _finding("GHSA-1", "pkg-a", fix_versions=("2.0",))
    suppressed_finding = _finding("GHSA-2", "pkg-b")
    lapsed_finding = _finding("GHSA-3", "pkg-c")
    applied = AppliedFindings(
        active=((_SCOPE, active_finding), (_SCOPE, lapsed_finding)),
        suppressed=((_SCOPE, suppressed_finding, _exc(id_="GHSA-2", package="pkg-b")),),
        lapsed=((_SCOPE, lapsed_finding, _exc(id_="GHSA-3", package="pkg-c")),),
        matched_exception_keys=frozenset({("GHSA-2", "pkg-b"), ("GHSA-3", "pkg-c")}),
    )
    stale = (_exc(id_="GHSA-9", package="pkg-z"),)
    run = AuditRun(
        scope_reports=(_scope_report(_SCOPE, ScopeOutcome.FINDINGS, [active_finding]),),
        applied=applied,
        stale_exceptions=stale,
        uv_version="uv 0.12.0",
        query_time=dt.datetime(2026, 9, 27, tzinfo=dt.UTC),
        locked_forge_template="0.6.0",
    )
    text = render_report(run)
    assert "GHSA-1" in text
    assert "Suppressed by exception" in text
    assert "GHSA-2" in text
    assert "Lapsed exceptions" in text
    assert "GHSA-3" in text
    assert "Stale exceptions" in text
    assert "GHSA-9" in text
    assert "0.6.0" in text


def test_render_report_flags_an_outage_as_not_clean() -> None:
    run = AuditRun(
        scope_reports=(
            ScopeReport(_SCOPE, ScopeOutcome.OUTAGE, None, "connection refused"),
        ),
        applied=_NO_FINDINGS,
        stale_exceptions=(),
        uv_version="uv 0.12.0",
        query_time=dt.datetime(2026, 9, 27, tzinfo=dt.UTC),
        locked_forge_template=None,
    )
    text = render_report(run)
    assert "NOT A CLEAN RESULT" in text


# -----------------------------------------------------------------------------
# main() -- end-to-end wiring, still with a fake runner
# -----------------------------------------------------------------------------

# One dependency group and no extras -- gives distinct runtime/full argv,
# without the combinatorial size of the real pyproject.toml.
_TWO_SCOPE_TOML = (
    "[project]\n\n[project.optional-dependencies]\n\n[dependency-groups]\n"
    'test = ["pytest"]\n'
)


def _two_scope_pyproject(tmp_path: Path) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(_TWO_SCOPE_TOML, encoding="utf-8")
    return path


def _main_runner(
    runtime_audit: CommandResult,
    full_audit: CommandResult,
    runtime_export: CommandResult | None,
    full_export: CommandResult | None,
) -> Runner:
    pyproject = tomllib.loads(_TWO_SCOPE_TOML)
    runtime_scope, full_scope = build_scopes(pyproject)
    mapping: dict[tuple[str, ...], CommandResult] = {
        tuple(audit_argv(runtime_scope)): runtime_audit,
        tuple(audit_argv(full_scope)): full_audit,
    }
    if runtime_export is not None:
        mapping[tuple(export_argv(runtime_scope))] = runtime_export
    if full_export is not None:
        mapping[tuple(export_argv(full_scope))] = full_export

    def runner(argv: list[str]) -> CommandResult:
        if argv[:2] == ["uv", "--version"]:
            return CommandResult(0, b"uv 0.12.0 (test)\n", b"")
        key = tuple(argv)
        if key not in mapping:
            raise AssertionError(f"unexpected command: {argv}")
        return mapping[key]

    return runner


def test_main_clean_exits_zero_and_prints_the_table(
    tmp_path: Path, capsys: Any
) -> None:
    runner = _main_runner(
        CommandResult(0, _clean_json(2), b""),
        CommandResult(0, _clean_json(5), b""),
        CommandResult(0, _export_bytes(2), b""),
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
            "--on-outage",
            "warn",
        ],
        runner=runner,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "runtime" in out
    assert "full" in out


def test_main_findings_exit_one_and_names_the_advisory(
    tmp_path: Path, capsys: Any
) -> None:
    vulns = [_vuln("GHSA-1", "pkg")]
    runner = _main_runner(
        CommandResult(1, _findings_json(2, vulns), b""),
        CommandResult(0, _clean_json(5), b""),
        CommandResult(0, _export_bytes(2), b""),
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
        ],
        runner=runner,
    )
    assert code == 1
    assert "GHSA-1" in capsys.readouterr().out


def test_main_an_exception_suppresses_and_exits_zero(
    tmp_path: Path, capsys: Any
) -> None:
    vulns = [_vuln("GHSA-1", "pkg")]
    runner = _main_runner(
        CommandResult(1, _findings_json(2, vulns), b""),
        CommandResult(0, _clean_json(5), b""),
        CommandResult(0, _export_bytes(2), b""),
        CommandResult(0, _export_bytes(5), b""),
    )
    exceptions_path = _write_exceptions(tmp_path, _VALID_ENTRY)
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(exceptions_path),
            "--lockfile",
            str(tmp_path / "no.lock"),
        ],
        runner=runner,
    )
    assert code == 0
    assert "Suppressed by exception" in capsys.readouterr().out


def test_main_service_outage_warns_and_passes_under_warn(
    tmp_path: Path, capsys: Any
) -> None:
    stderr = (FIXTURES / "outage_stderr.txt").read_bytes()
    runner = _main_runner(
        CommandResult(2, b"", stderr),
        CommandResult(0, _clean_json(5), b""),
        None,
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
            "--on-outage",
            "warn",
        ],
        runner=runner,
    )
    assert code == 0
    assert "NOT A CLEAN RESULT" in capsys.readouterr().out


def test_main_service_outage_fails_under_fail(tmp_path: Path) -> None:
    stderr = (FIXTURES / "outage_stderr.txt").read_bytes()
    runner = _main_runner(
        CommandResult(2, b"", stderr),
        CommandResult(0, _clean_json(5), b""),
        None,
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
            "--on-outage",
            "fail",
        ],
        runner=runner,
    )
    assert code == 1


def test_main_tool_error_fails_even_under_warn(tmp_path: Path) -> None:
    stderr = (FIXTURES / "tool_error_stderr.txt").read_bytes()
    runner = _main_runner(
        CommandResult(2, b"", stderr),
        CommandResult(0, _clean_json(5), b""),
        None,
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
            "--on-outage",
            "warn",
        ],
        runner=runner,
    )
    assert code == 1


def test_main_invalid_exceptions_file_fails_before_auditing(
    tmp_path: Path, capsys: Any
) -> None:
    bad = _write_exceptions(tmp_path, _VALID_ENTRY + 'severity = "high"\n')

    def runner(_argv: list[str]) -> CommandResult:
        raise AssertionError(
            "uv should never be invoked when the exceptions file is invalid"
        )

    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(bad),
            "--lockfile",
            str(tmp_path / "no.lock"),
        ],
        runner=runner,
    )
    assert code == 1
    assert "unknown key" in capsys.readouterr().err


def test_main_reports_a_stale_exception(tmp_path: Path, capsys: Any) -> None:
    runner = _main_runner(
        CommandResult(0, _clean_json(2), b""),
        CommandResult(0, _clean_json(5), b""),
        CommandResult(0, _export_bytes(2), b""),
        CommandResult(0, _export_bytes(5), b""),
    )
    exceptions_path = _write_exceptions(tmp_path, _VALID_ENTRY)  # matches nothing here
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(exceptions_path),
            "--lockfile",
            str(tmp_path / "no.lock"),
        ],
        runner=runner,
    )
    assert code == 0  # a stale exception is a warning, not a failure
    assert "Stale exceptions" in capsys.readouterr().out


def test_main_writes_the_github_step_summary(tmp_path: Path, monkeypatch: Any) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    runner = _main_runner(
        CommandResult(0, _clean_json(2), b""),
        CommandResult(0, _clean_json(5), b""),
        CommandResult(0, _export_bytes(2), b""),
        CommandResult(0, _export_bytes(5), b""),
    )
    code = main(
        [
            "--pyproject",
            str(_two_scope_pyproject(tmp_path)),
            "--exceptions",
            str(tmp_path / "no-exceptions.toml"),
            "--lockfile",
            str(tmp_path / "no.lock"),
        ],
        runner=runner,
    )
    assert code == 0
    assert "Dependency audit" in summary.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# Structural guards over the real workflows
# -----------------------------------------------------------------------------


def _workflow(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{name} did not parse to a mapping"
    return data


def test_ci_gates_all_green_on_the_audit_job() -> None:
    ci = _workflow("ci.yml")
    assert "audit" in ci["jobs"]["all-green"]["needs"]


def test_release_requires_the_audit_job() -> None:
    release = _workflow("release.yml")
    assert release["jobs"]["release"]["needs"] == "audit"


def test_audit_is_absent_from_the_reusable_linux_workflow() -> None:
    """It doesn't depend on the runner image; the canary would only repeat it."""
    linux_checks = _workflow("linux-checks.yml")
    assert "audit" not in linux_checks["jobs"]


def test_ci_audit_job_fails_on_outage_for_schedule_and_dispatch_only() -> None:
    ci_text = (WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
    start = ci_text.index("audit:")
    end = ci_text.index("\n  linux:", start)
    audit_job_text = ci_text[start:end]
    assert "schedule" in audit_job_text
    assert "workflow_dispatch" in audit_job_text
    assert re.search(r"mode=fail", audit_job_text)
    assert re.search(r"mode=warn", audit_job_text)


def test_release_audit_job_always_fails_on_outage() -> None:
    release = _workflow("release.yml")
    audit_job = release["jobs"]["audit"]
    steps = audit_job["steps"]
    audit_step = next(s for s in steps if "audit_dependencies.py" in s.get("run", ""))
    assert "--on-outage fail" in audit_step["run"]
    assert "dry_run" not in audit_step["run"]  # no bypass input


def test_real_audit_exceptions_file_parses_and_is_valid() -> None:
    assert parse_exceptions(EXCEPTIONS_FILE, today=dt.date.today()) == ()
