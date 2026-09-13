"""`create_forge.update.route_for`/`read_recorded` -- ADR 0041 rule 7's
file-based routing table, and the CLI-level dispatch built on it (CF-18.04,
ADR 0046).

Engine-free, like `tests/test_lifecycle.py`/`tests/test_staging.py`: pure
filesystem checks, no real `git`/`uv` subprocess, no engine import. CLI-level
dispatch tests mock `create_forge.pipeline`/`create_forge.runner` rather than
running a real render or a real Copier update -- that behaviour is
`tests/test_update_engine.py`'s and `tests/test_update.py`'s job.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import create_forge.pipeline as pipeline_module
import create_forge.runner as runner_module
from create_forge.cli import app
from create_forge.update import (
    COPIER_ANSWERS_FILE,
    Route,
    UpdateError,
    read_recorded,
    route_for,
)

runner = CliRunner()
METADATA_FILE = ".forge/generation.json"


def _write_metadata(project: Path, **overrides: object) -> None:
    document: dict[str, object] = {
        "metadata_version": 1,
        "provider": {"distribution": "forge-template", "version": "0.5.0"},
        "protocols": {"projectspec": 1, "component_manifest": [1]},
        "spec": {"protocol_version": 1},
        "components": [],
        "output": [
            {
                "target": "pyproject.toml",
                "owner": "foundation",
                "digest": "sha256:" + "0" * 64,
                "regeneration": "replace",
            }
        ],
    }
    document.update(overrides)
    metadata_path = project / METADATA_FILE
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(document), encoding="utf-8")


def _write_answers(project: Path) -> None:
    (project / COPIER_ANSWERS_FILE).write_text("_src_path: x\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# route_for -- the rule-7 table                                               #
# --------------------------------------------------------------------------- #


def _route(project: Path, *, legacy: bool) -> Route:
    return route_for(project, metadata_filename=METADATA_FILE, legacy=legacy)


def test_metadata_only_routes_to_the_engine(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    assert _route(tmp_path, legacy=False) is Route.ENGINE


def test_answers_only_routes_to_copier(tmp_path: Path) -> None:
    _write_answers(tmp_path)
    assert _route(tmp_path, legacy=False) is Route.COPIER


def test_both_files_route_to_the_engine_unless_legacy(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    _write_answers(tmp_path)
    assert _route(tmp_path, legacy=False) is Route.ENGINE
    assert _route(tmp_path, legacy=True) is Route.COPIER


def test_legacy_forces_copier_even_with_only_metadata(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    assert _route(tmp_path, legacy=True) is Route.COPIER


def test_neither_file_raises_naming_both_routes(tmp_path: Path) -> None:
    with pytest.raises(UpdateError) as excinfo:
        route_for(tmp_path, metadata_filename=METADATA_FILE, legacy=False)
    message = str(excinfo.value)
    assert METADATA_FILE in message
    assert COPIER_ANSWERS_FILE in message


def test_neither_file_raises_even_under_legacy(tmp_path: Path) -> None:
    """An explicit `--legacy` does not fabricate an answers file."""
    with pytest.raises(UpdateError):
        route_for(tmp_path, metadata_filename=METADATA_FILE, legacy=True)


# --------------------------------------------------------------------------- #
# read_recorded -- lenient structural parsing                                 #
# --------------------------------------------------------------------------- #


def test_read_recorded_extracts_version_spec_and_digests(tmp_path: Path) -> None:
    _write_metadata(tmp_path)
    document = read_recorded(tmp_path, metadata_filename=METADATA_FILE)
    assert document.provider_version == "0.5.0"
    assert document.spec == {"protocol_version": 1}
    assert document.digests == {"pyproject.toml": "sha256:" + "0" * 64}
    assert json.loads(document.raw)["metadata_version"] == 1


def test_read_recorded_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="could not read"):
        read_recorded(tmp_path, metadata_filename=METADATA_FILE)


def test_read_recorded_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / METADATA_FILE
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(UpdateError, match="not valid JSON"):
        read_recorded(tmp_path, metadata_filename=METADATA_FILE)


def test_read_recorded_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / METADATA_FILE
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(UpdateError, match="JSON object"):
        read_recorded(tmp_path, metadata_filename=METADATA_FILE)


def test_read_recorded_missing_provider_version(tmp_path: Path) -> None:
    _write_metadata(tmp_path, provider={"distribution": "forge-template"})
    with pytest.raises(UpdateError, match=r"provider\.version"):
        read_recorded(tmp_path, metadata_filename=METADATA_FILE)


def test_read_recorded_missing_spec(tmp_path: Path) -> None:
    _write_metadata(tmp_path, spec="not-an-object")
    with pytest.raises(UpdateError, match="spec object"):
        read_recorded(tmp_path, metadata_filename=METADATA_FILE)


def test_read_recorded_tolerates_a_malformed_output_array(tmp_path: Path) -> None:
    """Digests are best-effort for the degraded path; a malformed entry is
    skipped rather than failing the whole read -- only `provider.version` and
    `spec` are load-bearing for `route_for`'s reproduction needs.
    """
    _write_metadata(tmp_path, output=[{"target": "x"}, "not-a-dict", {}])
    document = read_recorded(tmp_path, metadata_filename=METADATA_FILE)
    assert document.digests == {}


# --------------------------------------------------------------------------- #
# CLI-level dispatch                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_cli_exits_1_naming_both_routes_when_neither_file_exists(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 1, result.output
    assert METADATA_FILE in result.output
    assert COPIER_ANSWERS_FILE in result.output


def test_cli_rejects_ref_on_the_engine_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_metadata(project)

    def _unexpected(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("must not be reached when --ref is rejected")

    monkeypatch.setattr(pipeline_module, "prepare_update", _unexpected)

    result = runner.invoke(app, ["update", str(project), "--ref", "v1.0.0"])

    assert result.exit_code == 1, result.output
    assert "--ref" in result.output
    assert "--legacy" in result.output


def test_cli_rejects_degraded_on_the_copier_route(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_answers(project)

    result = runner.invoke(app, ["update", str(project), "--degraded"])

    assert result.exit_code == 1, result.output
    assert "--degraded" in result.output


def test_cli_legacy_forces_copier_even_with_metadata_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_metadata(project)
    _write_answers(project)

    calls: list[Path] = []

    def fake_update(
        resolved: Path, *, vcs_ref: str | None = None, dry_run: bool = False
    ) -> None:
        del vcs_ref, dry_run
        calls.append(resolved)

    monkeypatch.setattr(runner_module, "update", fake_update)

    result = runner.invoke(app, ["update", str(project), "--legacy"])

    assert result.exit_code == 0, result.output
    assert calls == [project.resolve()]
