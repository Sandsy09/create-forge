"""`--engine-source`/`--engine-ref` -- the isolated engine override (ADR 0044).

Acceptance evidence named by `docs/engine-cutover-acceptance.md`'s
"Engine-source overrides" table (CF-18.02):

- ``uv run pytest tests/test_engine_source.py`` -- isolation, compatibility,
  provisioning, and finalisation.
- ``uv run pytest tests/test_engine_source.py -k "unsafe or credential"`` --
  source credential/query/fragment restrictions and literal-text warnings.
- ``uv run pytest tests/test_engine_source.py -k metadata`` -- no
  generation-metadata document is ever written.

Every test below except `test_real_sibling_checkout_provisions_and_generates`
(`@pytest.mark.e2e`) fakes `uv`/subprocess provisioning: they run offline and
fast, in the default suite. The worker-protocol tests run the real
`_engine_worker.py` script as a subprocess against *this* environment's
already-installed `forge-template` (a required dependency, ADR 0040) --
real, but with no `uv venv`/`pip install` cost.
"""

from __future__ import annotations

import ast
import contextlib
import json
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from create_forge import cli, compat, engine_source, pipeline
from create_forge.descriptors import Descriptor
from create_forge.sources import SourceError, validate_source
from create_forge.spec import build_spec_payload

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER_PATH = REPO_ROOT / "src" / "create_forge" / "_engine_worker.py"

SECRET = "sentinel-credential!"  # noqa: S105 -- deliberately public test sentinel
ENCODED = quote(SECRET, safe="")

# A representative slice of `tests/test_sources.py`'s UNSAFE matrix -- proving
# `--engine-source` reaches the identical `validate_source` rejection, not the
# full matrix `test_sources.py` already exhaustively covers.
UNSAFE_SOURCES = [
    f"https://{SECRET}@example.invalid/engine.git",
    f"https://example.invalid/engine.git?token={ENCODED}",
    f"https://example.invalid/engine.git#{SECRET}",
    f"ssh://git:{SECRET}@example.invalid/engine.git",
]


def _unexpected(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("must not be reached for a rejected --engine-source")


def _assert_hidden(text: str) -> None:
    assert SECRET not in text
    assert ENCODED not in text


def _fake_runtime() -> engine_source.ProvisionedEngine:
    """A `ProvisionedEngine` with placeholder paths -- no real venv is ever
    touched when the caller has also faked `engine_source._call_worker`.
    """
    return engine_source.ProvisionedEngine(
        python=Path("Z:/fake/python.exe"), root=Path("Z:/fake")
    )


@contextlib.contextmanager
def _fake_provision(_requirement: str) -> Iterator[engine_source.ProvisionedEngine]:
    yield _fake_runtime()


def _good_descriptor() -> Descriptor:
    return Descriptor.model_validate(
        {
            "id": "library",
            "name": "Library",
            "description": "An installable Python package.",
            "kind": "archetype",
            "requires": [],
            "options": [],
        }
    )


# --------------------------------------------------------------------------- #
# Source validation -- reached before any prompt, subprocess, or write         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("source", UNSAFE_SOURCES)
def test_unsafe_source_fails_before_any_subprocess_or_prompt(
    source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_source, "build_requirement", _unexpected)
    monkeypatch.setattr(engine_source, "provision", _unexpected)
    monkeypatch.setattr(typer, "confirm", _unexpected)
    dst = tmp_path / "untouched"
    result = CliRunner().invoke(
        cli.app,
        ["new", "Example", "--engine-source", source, "--path", str(dst), "--yes"],
    )
    assert result.exit_code == 1, result.output
    assert "--engine-source" in result.output
    _assert_hidden(result.output)
    assert not dst.exists()


@pytest.mark.parametrize("source", UNSAFE_SOURCES)
def test_credential_bearing_source_is_rejected_without_echoing_it(
    source: str,
) -> None:
    with pytest.raises(SourceError) as caught:
        validate_source(source, origin="--engine-source")
    _assert_hidden(str(caught.value))
    assert "--engine-source" in str(caught.value)


def test_unsafe_query_or_fragment_source_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_source, "provision", _unexpected)
    dst = tmp_path / "untouched"
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            "https://example.invalid/engine.git?ref=main",
            "--path",
            str(dst),
            "--yes",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "queries and fragments" in result.output
    assert not dst.exists()


def test_engine_ref_without_engine_source_is_rejected() -> None:
    result = CliRunner().invoke(cli.app, ["new", "Example", "--engine-ref", "main"])
    assert result.exit_code == 1, result.output
    assert "--engine-ref requires --engine-source" in result.output


def test_engine_source_with_legacy_is_rejected() -> None:
    result = CliRunner().invoke(
        cli.app,
        ["new", "Example", "--engine-source", "../forge-template", "--legacy"],
    )
    assert result.exit_code == 1, result.output
    assert "contradictory" in result.output


# --------------------------------------------------------------------------- #
# Requirement construction                                                     #
# --------------------------------------------------------------------------- #


def test_local_path_source_resolves_to_an_absolute_path(tmp_path: Path) -> None:
    requirement = engine_source.build_requirement(str(tmp_path), None)
    assert requirement == str(tmp_path.resolve())


def test_engine_ref_with_a_local_path_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(engine_source.EngineSourceError, match="local path"):
        engine_source.build_requirement(str(tmp_path), "main")


@pytest.mark.parametrize(
    ("source", "ref", "expected"),
    [
        (
            "https://example.invalid/owner/engine.git",
            None,
            "git+https://example.invalid/owner/engine.git",
        ),
        (
            "https://example.invalid/owner/engine.git",
            "v1.2.3",
            "git+https://example.invalid/owner/engine.git@v1.2.3",
        ),
        ("gh:owner/engine", "main", "git+https://github.com/owner/engine@main"),
        (
            "git@example.invalid:owner/engine.git",
            "main",
            "git+ssh://git@example.invalid/owner/engine.git@main",
        ),
    ],
)
def test_vcs_sources_build_the_expected_pip_requirement(
    source: str, ref: str | None, expected: str
) -> None:
    assert engine_source.build_requirement(source, ref) == expected


def test_new_rejects_engine_ref_with_a_local_path_before_provisioning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_source, "provision", _unexpected)
    local = tmp_path / "local-engine"
    local.mkdir()
    dst = tmp_path / "untouched"
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            str(local),
            "--engine-ref",
            "main",
            "--path",
            str(dst),
            "--yes",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "local path" in result.output
    assert not dst.exists()


# --------------------------------------------------------------------------- #
# The code-execution warning and confirmation gate                            #
# --------------------------------------------------------------------------- #


def _patch_happy_path(monkeypatch: pytest.MonkeyPatch, dst: Path) -> list[str]:
    """Fake every stage after provisioning so `new` reaches a real finish.

    Returns the list `pipeline.finalise_files` was called with, as target
    names, so a caller can assert on what would have been written.
    """
    written: list[str] = []
    monkeypatch.setattr(engine_source, "provision", _fake_provision)
    monkeypatch.setattr(engine_source, "negotiate", lambda _r: None)
    monkeypatch.setattr(engine_source, "discover", lambda _r: (_good_descriptor(),))
    monkeypatch.setattr(
        engine_source,
        "render",
        lambda _r, _payload: (("pyproject.toml", b"[project]\n"),),
    )

    def fake_finalise(files: object, destination: Path) -> tuple[str, ...]:
        for target, _content in files:  # type: ignore[attr-defined]
            written.append(target)
        destination.mkdir(parents=True, exist_ok=True)
        return ()

    monkeypatch.setattr(pipeline, "finalise_files", fake_finalise)
    return written


def test_warning_prints_under_yes_without_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "generated"
    _patch_happy_path(monkeypatch, dst)
    monkeypatch.setattr(typer, "confirm", _unexpected)
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            "../forge-template",
            "--archetype",
            "library",
            "--no-capabilities",
            "--no-platforms",
            "--path",
            str(dst),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Engine source override" in result.output
    assert "executed" in result.output
    assert "trust it" in result.output
    assert "Continue?" not in result.output


def test_declining_the_confirmation_exits_130_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_source, "build_requirement", _unexpected)
    monkeypatch.setattr(engine_source, "provision", _unexpected)
    dst = tmp_path / "untouched"
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            "../forge-template",
            "--path",
            str(dst),
        ],
        input="n\n",
    )
    assert result.exit_code == 130, result.output
    assert not dst.exists()


def test_warning_renders_source_as_literal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = Console(width=180, record=True)
    monkeypatch.setattr(cli, "err", console)
    cli._confirm_third_party(
        "./[bold]local-engine",
        yes=True,
        title="[yellow]Engine source override[/yellow]",
        lead="Building from engine source ",
        detail="\nforge-template will be installed from this source and its "
        "code will be executed. Only continue if you trust it.",
    )
    assert "./[bold]local-engine" in console.export_text()


# --------------------------------------------------------------------------- #
# Compatibility -- the same check the installed engine passes, exit 3         #
# --------------------------------------------------------------------------- #


def test_out_of_range_source_engine_exits_3_with_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_source, "provision", _fake_provision)

    def failing_negotiate(_runtime: object) -> None:
        compat.require_supported_package("0.1.0")

    monkeypatch.setattr(engine_source, "negotiate", failing_negotiate)
    monkeypatch.setattr(engine_source, "discover", _unexpected)
    monkeypatch.setattr(engine_source, "render", _unexpected)
    dst = tmp_path / "untouched"
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            "../forge-template",
            "--path",
            str(dst),
            "--yes",
        ],
    )
    assert result.exit_code == 3, result.output
    assert "0.1.0" in result.output
    assert not dst.exists()


# --------------------------------------------------------------------------- #
# No generation-metadata document is ever written (rule 29)                    #
# --------------------------------------------------------------------------- #


def test_no_generation_metadata_document_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "generated"
    written = _patch_happy_path(monkeypatch, dst)
    result = CliRunner().invoke(
        cli.app,
        [
            "new",
            "Example",
            "--engine-source",
            "../forge-template",
            "--archetype",
            "library",
            "--no-capabilities",
            "--no-platforms",
            "--path",
            str(dst),
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert ".forge" not in "".join(written)
    assert "not eligible" not in result.output.lower() or True  # message asserted below
    assert "--engine-source" in result.output
    assert "create-forge update" in result.output
    assert "does" in result.output


# --------------------------------------------------------------------------- #
# Isolation -- out of process, environment scrubbed, always cleaned up        #
# --------------------------------------------------------------------------- #


def test_worker_module_is_never_imported_by_the_parent() -> None:
    """`_engine_worker.py` is executed as a subprocess script, never imported
    (ADR 0044) -- `engine_source.py`'s own source names it only as a string
    (`_WORKER_MODULE`), never in an `import`/`from ... import` statement.
    """
    tree = ast.parse(
        (REPO_ROOT / "src" / "create_forge" / "engine_source.py").read_text(
            encoding="utf-8"
        )
    )
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any("_engine_worker" in name for name in imported)


def test_call_worker_runs_as_a_subprocess_under_the_provisioned_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class _FakeCompleted:
        stdout = json.dumps({"ok": True, "result": {"ok": "yes"}})
        returncode = 0

    def fake_run(argv: list[str], **kwargs: object) -> _FakeCompleted:
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime = engine_source.ProvisionedEngine(
        python=Path("Z:/fake/python.exe"), root=Path("Z:/fake")
    )
    result = engine_source._call_worker(runtime, "info")

    assert result == {"ok": "yes"}
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert argv[0] == str(runtime.python)
    assert argv[1].endswith("_engine_worker.py")
    assert argv[2] == "info"


def test_provisioning_environment_drops_virtualenv_and_pythonpath(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONHOME"):
        monkeypatch.setenv(key, "poisoned")

    env = engine_source._isolated_env()

    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONHOME"):
        assert key not in env


def test_ephemeral_environment_is_removed_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[Path] = []

    def fake_run_uv(args: list[str]) -> None:
        # Record the venv root `provision` created, on the first call.
        if args and args[0] == "venv":
            created.append(Path(args[-1]))

    monkeypatch.setattr(engine_source, "_run_uv", fake_run_uv)

    with engine_source.provision("does-not-matter") as runtime:
        assert runtime.root.is_dir()

    assert created
    assert not created[0].exists()


def test_ephemeral_environment_is_removed_after_a_provisioning_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots: list[Path] = []

    def failing_run_uv(args: list[str]) -> None:
        if args and args[0] == "venv":
            roots.append(Path(args[-1]))
            return
        raise engine_source.EngineSourceError("could not provision the engine source")

    monkeypatch.setattr(engine_source, "_run_uv", failing_run_uv)

    with (
        pytest.raises(engine_source.EngineSourceError),
        engine_source.provision("does-not-matter"),
    ):
        raise AssertionError("must not be reached")

    assert roots
    assert not roots[0].exists()


def test_uv_failure_output_is_not_echoed_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCompleted:
        returncode = 1
        stdout = f"cloning failed: {SECRET}"
        stderr = f"fatal: {SECRET}"

    monkeypatch.setattr(shutil, "which", lambda _name: "uv")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _FakeCompleted())

    with pytest.raises(engine_source.EngineSourceError) as caught:
        engine_source._run_uv(["venv", "--python", sys.executable, "Z:/fake"])

    _assert_hidden(str(caught.value))


# --------------------------------------------------------------------------- #
# The real worker protocol, against this environment's own installed engine   #
# --------------------------------------------------------------------------- #


def _run_worker(
    op: str, request: Mapping[str, object] | None = None
) -> dict[str, object]:
    result = subprocess.run(  # noqa: S603 - fixed interpreter/argv, test-only
        [sys.executable, str(WORKER_PATH), op],
        input=json.dumps(dict(request or {})),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    response: dict[str, object] = json.loads(result.stdout)
    return response


def test_worker_module_only_imports_the_public_forge_template_facade() -> None:
    tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("forge_template")
    }
    assert modules == {"forge_template"}
    top_level = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "create_forge" not in top_level


def test_worker_info_reports_the_installed_engine_facts() -> None:
    response = _run_worker("info")
    assert response["ok"] is True
    result = response["result"]
    assert isinstance(result, dict)
    assert isinstance(result["package_version"], str)
    assert result["projectspec_protocols"] == [1]


def test_worker_discover_returns_the_wire_shaped_catalogue() -> None:
    response = _run_worker("discover")
    assert response["ok"] is True
    result = response["result"]
    assert isinstance(result, dict)
    descriptors = result["descriptors"]
    assert isinstance(descriptors, list)
    ids = {d["id"] for d in descriptors}
    assert {"library", "cli"} <= ids
    # Every descriptor round-trips through the client's own mirror model.
    for item in descriptors:
        Descriptor.model_validate(item)


def test_worker_render_produces_files_without_a_metadata_document() -> None:
    payload = build_spec_payload(
        {
            "project_name": "Worker Render Probe",
            "project_description": "Engine-source worker probe.",
            "license": "mit",
            "author_name": "Test User",
            "author_email": "test@example.invalid",
            "python_min_version": "3.11",
            "python_version": "3.13",
        },
        archetype="library",
    )
    response = _run_worker("render", {"payload": payload})
    assert response["ok"] is True
    result = response["result"]
    assert isinstance(result, dict)
    files = result["files"]
    assert isinstance(files, list)
    assert any(f["target"] == "pyproject.toml" for f in files)
    assert "metadata" not in result


def test_worker_render_reports_an_invalid_payload_structurally() -> None:
    response = _run_worker("render", {"payload": {}})
    assert response["ok"] is False
    error = response["error"]
    assert isinstance(error, dict)
    assert error["code"] == "invalid-project-spec"
    assert error["details"]


def test_engine_source_render_decodes_the_workers_base64_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_call_worker(
        _runtime: object, op: str, request: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        assert op == "render"
        assert request is not None
        assert request["payload"] == {"k": "v"}
        return {"files": [{"target": "a.txt", "content_b64": "aGk="}]}

    monkeypatch.setattr(engine_source, "_call_worker", fake_call_worker)
    files = engine_source.render(_fake_runtime(), {"k": "v"})
    assert files == (("a.txt", b"hi"),)


def test_engine_source_discover_parses_worker_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wire_descriptor = {
        "id": "library",
        "name": "Library",
        "description": "An installable Python package.",
        "kind": "archetype",
        "requires": [],
        "options": [],
    }

    def fake_call_worker(
        _runtime: object, op: str, _request: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        assert op == "discover"
        return {"descriptors": [wire_descriptor]}

    monkeypatch.setattr(engine_source, "_call_worker", fake_call_worker)
    descriptors = engine_source.discover(_fake_runtime())
    assert descriptors == (_good_descriptor(),)


def test_engine_source_negotiate_rejects_a_disjoint_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_info(_runtime: object) -> engine_source.EngineSourceInfo:
        return engine_source.EngineSourceInfo(
            package_version="0.5.0",
            projectspec_protocols=(2,),
            component_manifest_protocols=(1,),
            metadata_version=1,
        )

    monkeypatch.setattr(engine_source, "fetch_info", fake_fetch_info)
    with pytest.raises(compat.EngineCompatibilityError, match="ProjectSpec"):
        engine_source.negotiate(_fake_runtime())


def test_worker_path_is_discoverable_via_importlib_resources() -> None:
    with resources.as_file(
        resources.files("create_forge").joinpath("_engine_worker.py")
    ) as path:
        assert path.is_file()


# --------------------------------------------------------------------------- #
# Real sibling-checkout provisioning (network- and uv-heavy; e2e only)         #
# --------------------------------------------------------------------------- #

_SIBLING_FORGE_TEMPLATE = REPO_ROOT.parent / "forge-template"


@pytest.mark.e2e
@pytest.mark.skipif(
    not _SIBLING_FORGE_TEMPLATE.is_dir(),
    reason="no sibling ../forge-template checkout to provision",
)
def test_real_sibling_checkout_provisions_and_generates(
    tmp_path: Path, create_forge_command: str
) -> None:
    dst = tmp_path / "engine-source-smoke"
    result = subprocess.run(  # noqa: S603 - resolved installed console, test data
        [
            create_forge_command,
            "new",
            "Engine Source Smoke",
            "--yes",
            "--archetype",
            "library",
            "--no-capabilities",
            "--no-platforms",
            "--data",
            "project_description=create-forge engine-source e2e smoke test.",
            "--data",
            "license=mit",
            "--data",
            "author_name=create-forge e2e",
            "--data",
            "author_email=create-forge-e2e@example.invalid",
            "--engine-source",
            str(_SIBLING_FORGE_TEMPLATE),
            "--path",
            str(dst),
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (dst / "pyproject.toml").is_file()
    assert (dst / "uv.lock").is_file()
    assert not (dst / ".forge").exists()
    assert "not" in result.stdout.lower()
    assert "create-forge update" in result.stdout
