"""`commands/doctor.py` -- `doctor` and `doctor --json`."""

from __future__ import annotations

import importlib.metadata
import json
from importlib.metadata import PackageNotFoundError
from io import BytesIO, TextIOWrapper
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

import create_forge.runner as runner_module
from create_forge.cli import app
from create_forge.commands import _output as output_module
from create_forge.commands import doctor as doctor_module

runner = CliRunner()


def test_doctor_reports_on_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """doctor exits 1 when any check is unhealthy, and a fresh CI runner has
    no global git identity configured -- unlike the author's own machine,
    where this always happened to pass. Monkeypatch it so the test verifies
    doctor's registry reporting, not the host's git config."""
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    result = runner.invoke(app, ["doctor"])
    assert result.exception is None
    assert "registry" in result.output


def _hide_engine_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force `importlib.metadata.version("forge-template")` to raise, as it
    would in a real environment without the `engine` extra installed --
    deterministic regardless of whether *this* dev checkout happens to have
    `--all-extras` resolved. Every other distribution resolves normally.
    """

    def fake(name: str) -> str:
        if name == "forge-template":
            raise PackageNotFoundError(name)
        return importlib.metadata.version(name)

    monkeypatch.setattr(doctor_module, "version", fake)


def _show_engine_extra(monkeypatch: pytest.MonkeyPatch, installed_version: str) -> None:
    """The inverse of `_hide_engine_extra`: force a specific installed
    `forge-template` version, deterministic regardless of the ambient venv.
    """

    def fake(name: str) -> str:
        if name == "forge-template":
            return installed_version
        return importlib.metadata.version(name)

    monkeypatch.setattr(doctor_module, "version", fake)


def test_doctor_fails_when_the_engine_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0040 decision 1/6 (CF-18.01): `forge-template` is a required
    dependency now, so its absence is a genuinely broken environment -- a
    failing check and exit `1`, not the informational "not installed" row
    the optional `engine` extra used to get.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    _hide_engine_extra(monkeypatch)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1, result.output
    assert "create-forge" in result.output
    assert "copier" in result.output
    assert "not installed" in result.output
    assert "forge-template>=0.7,<0.8" in result.output
    assert "engine" in result.output
    assert "integration line" in result.output
    assert "v0.5.x-engine" in result.output


def test_doctor_reports_the_installed_engine_package_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the (now required) engine dependency is installed, doctor names
    the installed version rather than "not installed", and the engine check
    passes.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    _show_engine_extra(monkeypatch, "0.7.0")

    table_result = runner.invoke(app, ["doctor"])
    result = runner.invoke(app, ["doctor", "--json"])

    assert table_result.exit_code == 0, table_result.output
    assert "integration line" in table_result.output
    assert "v0.5.x-engine" in table_result.output
    payload = json.loads(result.output)
    assert payload["integration"]["engine_package"] == "0.7.0"
    assert payload["integration"]["line"] == "v0.5.x-engine"


@pytest.mark.parametrize("installed", ["0.6.0", "0.8.0"])
def test_doctor_fails_an_installed_engine_outside_the_supported_range(
    monkeypatch: pytest.MonkeyPatch, installed: str
) -> None:
    """ADR 0061 (CF-29.01): `doctor` applies the same package-range check
    `new` does. Before it, the `engine` row passed on presence alone, so
    `doctor --json` reported `ok: true` for an engine `new` refuses with exit
    `3`. Both neighbours of the range are exercised: the previous line and the
    excluded upper bound.

    Protocol negotiation still runs against the real engine, so it keeps
    passing -- the failure is attributable to the package range alone.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    _show_engine_extra(monkeypatch, installed)

    table_result = runner.invoke(app, ["doctor"])
    result = runner.invoke(app, ["doctor", "--json"])

    assert table_result.exit_code == 1, table_result.output
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    checks = {c["name"]: c for c in payload["checks"]}
    assert checks["engine"]["ok"] is False
    assert installed in checks["engine"]["detail"]
    assert "forge-template>=0.7,<0.8" in checks["engine"]["detail"]
    assert checks["engine negotiation"]["ok"] is True
    assert payload["integration"]["engine_package"] == installed
    assert payload["integration"]["projectspec_protocol"]["detected"] is not None


@pytest.mark.parametrize("installed", ["0.7.0", "0.7.9"])
def test_doctor_passes_an_installed_engine_inside_the_supported_range(
    monkeypatch: pytest.MonkeyPatch, installed: str
) -> None:
    """The lower bound and a later patch of the line both pass the `engine` row."""
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    _show_engine_extra(monkeypatch, installed)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    checks = {c["name"]: c for c in json.loads(result.output)["checks"]}
    assert checks["engine"]["ok"] is True


def test_doctor_json_emits_the_documented_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`doctor --json` must carry every field docs/engine-resolution.md's
    diagnostics contract documents, print no table, and still exit 0 when
    every check passes -- against the real installed engine, so the
    negotiated `*_detected` facts are genuinely populated (ADR 0040
    decision 6, CF-18.01), not left at a hardcoded `None`.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["create_forge"] == importlib.metadata.version("create-forge")
    assert payload["ok"] is True
    integration = payload["integration"]
    assert integration["line"] == "v0.5.x-engine"
    assert integration["engine_package"] is not None
    assert integration["engine_range"] == "forge-template>=0.7,<0.8"
    assert integration["projectspec_protocol"]["supported"] == "1"
    assert integration["projectspec_protocol"]["detected"] is not None
    assert integration["component_manifest_protocol"]["supported"] == "1,2,3"
    assert integration["component_manifest_protocol"]["detected"] is not None
    assert integration["metadata_version"]["supported"] == "1"
    assert integration["metadata_version"]["detected"] is not None
    assert integration["template_source"] is not None
    assert {"name", "ok", "detail"} <= payload["checks"][0].keys()
    # The table's own column header must not leak into --json output, and
    # informational rows (already under "integration") must not duplicate
    # into "checks".
    assert "Check" not in result.output
    assert all(c["name"] != "integration line" for c in payload["checks"])


def test_doctor_json_exits_1_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `--json` flag changes the output format only -- an unhealthy
    environment must still be reported through the exit status a script
    would check."""
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")

    def _broken_registry() -> object:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(doctor_module, "load_registry", _broken_registry)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    registry_check = next(c for c in payload["checks"] if c["name"] == "registry")
    assert registry_check["ok"] is False


def test_doctor_reports_the_copier_cache_and_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0039 / docs/engine-resolution.md diagnostics contract: `doctor`
    names Copier's cache directory, whether COPIER_CACHE_DIR overrides it, and
    whether it is writable, plus the `uv` binary it would actually run.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    override = tmp_path / "cache dir"
    override.mkdir()
    monkeypatch.setenv("COPIER_CACHE_DIR", str(override))

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["copier_cache"] == {
        "path": str(override),
        "override": True,
        "exists": True,
        "writable": True,
    }
    assert set(payload["uv"]) == {"path", "version", "package"}
    assert "copier cache" in result.output  # informational row in the table too


def test_doctor_fails_when_the_copier_cache_is_unwritable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unwritable cache means the environment genuinely cannot scaffold, so
    the check fails and `doctor` exits 1 -- the schema stays additive, only
    the boolean flips.
    """
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    # `_tooling_diagnostics` imports `cache_probe` lazily from
    # `create_forge.runner` on every call (ADR 0040, CF-18.01), so the patch
    # lands there, not on `doctor_module`.
    monkeypatch.setattr(
        runner_module,
        "cache_probe",
        lambda _location: runner_module.CacheProbe(exists=True, writable=False),
    )

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["copier_cache"]["writable"] is False
    check = next(c for c in payload["checks"] if c["name"] == "copier cache writable")
    assert check["ok"] is False


def test_doctor_survives_a_console_that_cannot_encode_check_marks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for #12: a Windows console on the cp1252 codepage --
    the default outside Windows Terminal -- cannot encode the check-mark
    glyphs doctor's table used unconditionally, and Rich let the resulting
    UnicodeEncodeError propagate instead of degrading. CliRunner's own output
    capture goes through UTF-8, so this has to install a real cp1252 console
    to reproduce the crash; test_doctor_reports_on_the_registry above never
    could have caught this."""
    monkeypatch.setattr(doctor_module, "_git_config", lambda _key: "test")
    cp1252_console = Console(file=TextIOWrapper(BytesIO(), encoding="cp1252"), width=80)
    monkeypatch.setattr(output_module, "console", cp1252_console)

    result = runner.invoke(app, ["doctor"])

    assert result.exception is None, result.output


def test_markers_are_ascii_when_the_encoding_cannot_take_glyphs() -> None:
    cp1252_console = Console(file=TextIOWrapper(BytesIO(), encoding="cp1252"), width=80)

    assert doctor_module._markers(cp1252_console) == ("OK", "FAIL")


def test_markers_use_glyphs_when_the_encoding_allows() -> None:
    """The cp1252 fallback must not flatten output for consoles that can
    render the real glyphs -- fixing this for some users should not cost
    everyone else the nicer marks."""
    utf8_console = Console(file=TextIOWrapper(BytesIO(), encoding="utf-8"), width=80)

    assert doctor_module._markers(utf8_console) == ("✓", "✗")
