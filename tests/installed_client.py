"""Shared harness for the installed-candidate end-to-end suites.

`tests/test_e2e_installed_data_science.py` (CF-14.02, ADR 0032) and
`tests/test_e2e_installed_rollout.py` (CF-14.03, ADR 0033) both drive the real
`create-forge` console script installed from a freshly built `0.3.0` wheel,
rather than the editable development environment `tests/conftest.py`'s
`create_forge_command` resolves. Building that wheel and its virtual
environments is the most expensive thing either suite does, so the build, the
environment construction, and the subprocess plumbing live here and are shared.

Nothing in this module imports `create_forge` or `forge_template`: it reads the
installed distributions through subprocesses in the candidate environment, the
same isolation boundary CF-14.02 established.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

CLIENT_VERSION = "0.3.0"
ENGINE_VERSION = "0.4.1"
DEFAULT_PYTHON = "3.13"
SUBPROCESS_TIMEOUT = 1800
FORGE_DISTRIBUTIONS = {
    canonicalize_name("create-forge"),
    canonicalize_name("forge-template"),
}


@dataclass(frozen=True, slots=True)
class InstalledClient:
    """One virtual environment with the candidate wheel installed.

    `engine` is the exact `forge-template` version resolved into the
    environment, or `None` when the wheel was installed without its `engine`
    extra -- the shape a plain `pip install create-forge` produces. `uv` is
    always present (installed explicitly when the `engine` extra did not pull
    it) so a suite can run generated-project checks regardless.
    """

    root: Path
    venv: Path
    python: Path
    console: Path
    uv: Path
    wheel: Path
    engine: str | None
    env: Mapping[str, str]


def run(
    command: Sequence[str],
    cwd: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one child command, capturing output, never raising on exit status."""
    return subprocess.run(  # noqa: S603 - reviewed argv, no shell
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
        check=False,
    )


def assert_success(result: subprocess.CompletedProcess[str], description: str) -> None:
    """Fail with the full child output when a command that must succeed did not."""
    assert result.returncode == 0, (
        f"{description} failed (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def _is_windows_venv(venv: Path) -> bool:
    return (venv / "Scripts").is_dir()


def venv_python(venv: Path) -> Path:
    """The interpreter inside a uv-created virtual environment."""
    return venv / ("Scripts/python.exe" if _is_windows_venv(venv) else "bin/python")


def venv_script(venv: Path, name: str) -> Path:
    """A console script inside a uv-created virtual environment."""
    if _is_windows_venv(venv):
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def installed_child_env(
    base: Mapping[str, str], venv: Path, config_root: Path
) -> dict[str, str]:
    """Isolate CLI configuration and put the candidate's scripts first on PATH.

    `VIRTUAL_ENV`, `UV_PROJECT_ENVIRONMENT`, `PYTHONHOME`, `PYTHONPATH`, and
    every `FORGE_*` override are removed so parent-environment state and user
    configuration cannot influence a generation; `XDG_CONFIG_HOME` is
    redirected to a throwaway root so `~/.config/create-forge/config.toml`
    cannot either. The host PATH is kept *after* the venv scripts so `git`
    still resolves.
    """
    env = {
        key: value
        for key, value in base.items()
        if not key.upper().startswith("FORGE_")
    }
    for leak in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONHOME", "PYTHONPATH"):
        env.pop(leak, None)

    path_key = next((key for key in env if key.upper() == "PATH"), "PATH")
    scripts = venv_python(venv).parent
    env[path_key] = f"{scripts}{os.pathsep}{env.get(path_key, '')}"
    env["XDG_CONFIG_HOME"] = str(config_root)
    return env


def build_candidate_wheel(dist_dir: Path, base_env: Mapping[str, str]) -> Path:
    """Build one `create_forge-0.3.0-*.whl` into `dist_dir`.

    Uses the repository's own `uv` -- the wheel build is a create-forge
    working-tree operation, not part of the isolated candidate environment.
    """
    build = run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        REPO_ROOT,
        env=base_env,
    )
    assert_success(build, "candidate wheel build")

    wheels = sorted(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    wheel = wheels[0]
    assert wheel.name.startswith(f"create_forge-{CLIENT_VERSION}-"), wheel.name
    return wheel


@contextlib.contextmanager
def build_client(
    wheel: Path,
    base_env: Mapping[str, str],
    *,
    extras: str = "",
    engine: str | None = None,
    python: str = DEFAULT_PYTHON,
) -> Iterator[InstalledClient]:
    """Install the candidate wheel into a fresh virtual environment.

    `extras` is appended to the wheel path (`"[engine]"` or `""`); `engine`
    pins `forge-template` when the wheel is installed without that extra. `uv`
    is always added to the install set -- the `engine` extra already carries
    it, and a wheel installed without that extra still needs it to run a
    generated project. The environment, and everything generated inside it,
    lives under a context-managed temporary root removed on any outcome.
    """
    with tempfile.TemporaryDirectory(prefix="create-forge-installed-client-") as tmp:
        root = Path(tmp)
        venv = root / "client-venv"
        created = run(
            ["uv", "venv", "--python", python, str(venv)],
            root,
            env=base_env,
        )
        assert_success(created, "candidate virtual environment creation")

        python_path = venv_python(venv)
        targets = [f"{wheel}{extras}", *([engine] if engine else []), "uv"]
        installed = run(
            ["uv", "pip", "install", "--python", str(python_path), *targets],
            root,
            env=base_env,
        )
        assert_success(installed, "candidate wheel installation")

        console = venv_script(venv, "create-forge")
        uv_path = venv_script(venv, "uv")
        assert console.is_file(), console
        assert uv_path.is_file(), uv_path

        yield InstalledClient(
            root=root,
            venv=venv,
            python=python_path,
            console=console,
            uv=uv_path,
            wheel=wheel,
            engine=engine.split("==")[-1] if engine else None,
            env=installed_child_env(base_env, venv, root / "config"),
        )


# A subprocess in the candidate environment that runs the *installed* shared
# pipeline for one archetype and selection, so a suite can derive its
# rendered-output and ownership expectations from the engine's own plan rather
# than a manifest copied into this repository (ADR 0032 decision 4, reused by
# ADR 0033). The archetype id is read from the JSON payload, never hard-coded.
OWNERSHIP_PROBE = """
import hashlib
import json
import sys

from create_forge.pipeline import build_generation_request
from create_forge.spec import SelectionRequest

payload = json.loads(sys.argv[1])
request = build_generation_request(
    payload["answers"],
    selection=SelectionRequest.of(
        archetype=payload["archetype"],
        capabilities=payload["capabilities"],
        platforms=[],
    ),
)
planned = [
    {
        "target": item.target,
        "owner": (
            item.owner.id if item.owner.kind == "component" else item.owner.kind
        ),
    }
    for item in request.rendered.plan.files
]
rendered = [
    {"target": item.target, "sha256": hashlib.sha256(item.content).hexdigest()}
    for item in request.rendered.files
]
print(json.dumps({"planned": planned, "rendered": rendered}))
"""


def file_bytes(root: Path) -> dict[str, bytes]:
    """Every file under `root`, keyed by its POSIX-relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def assert_output_matches_owned_plan(
    client: InstalledClient,
    project: Path,
    *,
    archetype: str,
    capabilities: Sequence[str],
    answers: Mapping[str, str],
) -> None:
    """Every generated byte matches the installed pipeline's own owned plan.

    Runs `OWNERSHIP_PROBE` in the candidate environment and asserts: planned
    and rendered target lists agree and are unique; every planned file is
    owned by Foundation or a selected component; every selected component
    contributes at least one file; and the generated tree is exactly the
    rendered targets plus the client-owned `uv.lock`, byte for byte.
    """
    payload = json.dumps(
        {
            "answers": dict(answers),
            "archetype": archetype,
            "capabilities": list(capabilities),
        }
    )
    probed = run(
        [str(client.python), "-c", OWNERSHIP_PROBE, payload],
        client.root,
        env=client.env,
    )
    assert_success(probed, "installed pipeline ownership probe")
    evidence = json.loads(probed.stdout)

    planned = evidence["planned"]
    rendered = evidence["rendered"]
    planned_targets = [item["target"] for item in planned]
    rendered_targets = [item["target"] for item in rendered]
    assert len(planned_targets) == len(set(planned_targets))
    assert len(rendered_targets) == len(set(rendered_targets))
    assert planned_targets == rendered_targets

    selected = {archetype, *capabilities}
    owners = {item["owner"] for item in planned}
    assert owners == {"foundation", *selected}
    for component_id in selected:
        assert any(item["owner"] == component_id for item in planned)

    actual = file_bytes(project)
    assert set(actual) == {*rendered_targets, "uv.lock"}
    for item in rendered:
        assert hashlib.sha256(actual[item["target"]]).hexdigest() == item["sha256"], (
            item["target"]
        )
