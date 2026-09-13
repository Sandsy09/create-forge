"""`--engine-source`/`--engine-ref`: an isolated, out-of-process engine override.

ADR 0044 (CF-18.02) implements the interface ADR 0011 reserved and ADR 0040
decision 4 specified: a named local path or VCS URL, with an optional ref, is
installed with `uv` into a throwaway environment containing *only* that
engine -- never `create-forge` itself -- and the whole generation runs
against it through `_engine_worker.py`, a plain script this module locates and
executes, never imports. The installed engine is never imported, shadowed, or
in-process `sys.path`-injected (rule 25, docs/engine-default-cli.md).

Engine-free by construction, like `sources.py`, `staging.py`, and `compat.py`:
nothing here imports `forge_template`, not even under `TYPE_CHECKING`
(`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard covers this
module for exactly that reason). `compat.py` holds the one shared
compatibility check this module and `engine.py` both apply (rule 28);
`sources.py`'s `validate_source`/`url_source` are the one shared source
classification both this module and `--template-url` apply (rule 26).
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from create_forge import compat, sources, staging
from create_forge.descriptors import Descriptor

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

_WORKER_MODULE = "_engine_worker.py"

# `uv venv`/`uv pip install` clone or download a source and resolve its own
# dependencies; `render` runs arbitrary code from that source (the whole
# reason for the code-execution warning). Generous but bounded, so a hung
# network call or an infinite loop in untrusted code cannot block forever.
_PROVISION_TIMEOUT_SECONDS = 600
_WORKER_TIMEOUT_SECONDS = 300

# git's own scp-like syntax (`user@host:path`), which forge-template's
# eventual `uv pip install` needs rewritten as `ssh://user@host/path` --
# unlike Copier/git, pip's VCS requirement syntax has no native scp-style
# form. The `(?!//)` guard keeps this disjoint from an actual `scheme://`
# URL, which `sources.url_source` already recognises on its own.
_SCP_RE = re.compile(r"^(?P<user_host>[\w.-]+@[\w.-]+):(?!//)(?P<path>.+)$")


class EngineSourceError(Exception):
    """A safe, actionable failure resolving, provisioning, or running the
    `--engine-source` override engine.

    Never carries raw subprocess stdout/stderr or an un-redacted source
    string (rule 26) -- messages are always create-forge's own fixed,
    sanitised text. Exit status `1` (docs/cli-conventions.md); a
    compatibility mismatch is `compat.EngineCompatibilityError` instead, at
    exit `3`, so the two failure classes stay distinguishable the same way
    they already are on the default engine route.
    """  # noqa: D205


@dataclass(frozen=True, slots=True)
class ProvisionedEngine:
    """One throwaway environment with exactly one engine installed into it."""

    python: Path
    """The venv's own interpreter -- what every worker call is run under."""

    root: Path
    """The environment's root directory, removed when `provision` exits."""


@dataclass(frozen=True, slots=True)
class EngineSourceInfo:
    """The provisioned engine's version/protocol facts, unchecked.

    Mirrors `forge_template.EngineInfo`'s fields without importing it --
    parsed from `_engine_worker.py`'s JSON `info` response, which is the only
    form these facts can take once they have crossed the process boundary.
    """

    package_version: str
    projectspec_protocols: tuple[int, ...]
    component_manifest_protocols: tuple[int, ...]
    metadata_version: int


def build_requirement(source: str, ref: str | None) -> str:
    """Turn a validated `--engine-source` (+ optional `--engine-ref`) into a
    `uv pip install` requirement.

    `source` has already passed `sources.validate_source(source,
    origin="--engine-source")` (rule 26) -- this only classifies and shapes
    it into an installable requirement; it never re-validates for
    credentials, and it uses `sources.url_source` as the single shared
    definition of "this is a URL" so the two features can never disagree
    about which sources get URL-shaped treatment.

    A local path never accepts a ref (there is no VCS reference to check
    out on a plain path) -- `--engine-ref` there is rejected outright rather
    than silently ignored.
    """  # noqa: D205
    candidate = source.strip()
    url = sources.url_source(candidate)
    if url is None:
        scp = _SCP_RE.match(candidate)
        if scp is not None:
            url = f"ssh://{scp['user_host']}/{scp['path']}"

    if url is not None:
        requirement = f"git+{url}"
        return f"{requirement}@{ref}" if ref else requirement

    if ref:
        msg = (
            "--engine-ref selects a VCS revision and cannot be used with a "
            "local path source. Check the revision out in the local clone "
            "first."
        )
        raise EngineSourceError(msg)
    return str(Path(candidate).expanduser().resolve())


def released_requirement(version: str) -> str:
    """A `uv pip install` requirement pinning one exact PyPI release.

    Used by `pipeline.prepare_update` (ADR 0046, CF-18.04) to reproduce the
    `forge-template` release recorded in `.forge/generation.json` when it
    differs from the installed one -- a third, distinct source kind from
    `build_requirement`'s user-supplied path/VCS/scp forms above: a recorded
    release is always an exact PyPI version, never a path or a ref.
    """
    return f"{compat.ENGINE_DISTRIBUTION}=={version}"


def _isolated_env() -> dict[str, str]:
    """The subprocess environment for `uv` and the worker.

    Stripped of everything that could alias the ephemeral environment onto
    the caller's own virtual environment or Python installation, so a
    `--engine-source` render can never read from or write into either.
    """
    env = dict(os.environ)
    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    return env


def _venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _run_uv(args: Sequence[str]) -> None:
    uv = shutil.which("uv")
    if uv is None:
        msg = (
            "could not provision the engine source because the uv "
            "executable is unavailable; install uv>=0.12,<0.13 and retry"
        )
        raise EngineSourceError(msg)
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable, reviewed args
            [uv, *args],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
            timeout=_PROVISION_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        msg = f"could not launch uv to provision the engine source: {exc}"
        raise EngineSourceError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = "provisioning the engine source timed out"
        raise EngineSourceError(msg) from exc

    if result.returncode != 0:
        # uv's own stdout/stderr may echo the source path or URL verbatim
        # (rule 26): never forwarded, mirroring runner._explain()'s rule for
        # Copier's own process failures.
        msg = (
            "could not provision the engine source. Check the --engine-source "
            "path or VCS URL, --engine-ref, network access, and repository "
            "permissions, then retry."
        )
        raise EngineSourceError(msg)


@contextlib.contextmanager
def provision(requirement: str) -> Iterator[ProvisionedEngine]:
    """Install `requirement` into a fresh, throwaway environment.

    Created under the system temp directory -- deliberately not adjacent to
    the destination the way `staging.staged` stages a render, since this is
    disposable tooling, not the project being generated. Removed on every
    exit (success, a raised exception, or `Ctrl-C`) with
    `staging.remove_tree`, which clears read-only files a fresh install may
    have left behind on Windows.
    """
    root = Path(tempfile.mkdtemp(prefix="create-forge-engine-source-"))
    try:
        _run_uv(["venv", "--python", sys.executable, str(root)])
        python = _venv_python(root)
        _run_uv(["pip", "install", "--python", str(python), requirement])
        yield ProvisionedEngine(python=python, root=root)
    finally:
        staging.remove_tree(root)


def _explain_worker_error(error: Mapping[str, object]) -> str:
    """Format `_engine_worker.py`'s structured error the way `engine.explain`
    formats a `ForgeEngineError` -- the two are the same shape by design.
    """  # noqa: D205
    code = error.get("code")
    message = str(error.get("message", "the engine source worker failed"))
    lines = [f"{message} ({code})" if code else message]
    operation = error.get("operation")
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, Mapping):
                continue
            path = detail.get("path")
            parts = path if isinstance(path, list) else []
            location = ".".join(str(part) for part in parts) or str(operation or "")
            lines.append(f"  {location}: {detail.get('message', '')}")
    return "\n".join(lines)


def _call_worker(
    runtime: ProvisionedEngine, op: str, request: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Run one `_engine_worker.py` operation inside `runtime` and return its result.

    Raises `EngineSourceError` for a launch failure, a timeout, an unreadable
    response, or the worker's own reported failure -- never lets a raw
    subprocess or JSON-decode exception escape to the caller.
    """
    with resources.as_file(
        resources.files("create_forge").joinpath(_WORKER_MODULE)
    ) as worker_path:
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, reviewed
                [str(runtime.python), str(worker_path), op],
                input=json.dumps(dict(request or {})),
                capture_output=True,
                text=True,
                check=False,
                env=_isolated_env(),
                timeout=_WORKER_TIMEOUT_SECONDS,
            )
        except OSError as exc:
            msg = f"could not launch the engine source worker: {exc}"
            raise EngineSourceError(msg) from exc
        except subprocess.TimeoutExpired as exc:
            msg = "the engine source worker timed out"
            raise EngineSourceError(msg) from exc

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        msg = f"the engine source worker produced an unreadable response for {op!r}"
        raise EngineSourceError(msg) from exc

    if not isinstance(response, dict) or not response.get("ok", False):
        error = response.get("error", {}) if isinstance(response, dict) else {}
        raise EngineSourceError(_explain_worker_error(error))

    result_body = response.get("result", {})
    return result_body if isinstance(result_body, dict) else {}


def _int(value: object) -> int:
    """Coerce one JSON-decoded worker response field to `int`.

    Raised as `EngineSourceError` rather than an uncaught `TypeError`/
    `ValueError`: a malformed field here means the worker (or the
    environment it ran in) is broken, and that is still this module's
    failure to explain, not a raw traceback.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = f"the engine source worker returned a malformed integer field: {value!r}"
        raise EngineSourceError(msg)
    return int(value)


def _int_tuple(value: object) -> tuple[int, ...]:
    """Coerce one JSON-decoded worker response field to `tuple[int, ...]`."""
    if not isinstance(value, list):
        msg = f"the engine source worker returned a malformed list field: {value!r}"
        raise EngineSourceError(msg)
    return tuple(_int(item) for item in value)


def fetch_info(runtime: ProvisionedEngine) -> EngineSourceInfo:
    """The provisioned engine's version/protocol facts, unchecked."""
    result = _call_worker(runtime, "info")
    return EngineSourceInfo(
        package_version=str(result["package_version"]),
        projectspec_protocols=_int_tuple(result["projectspec_protocols"]),
        component_manifest_protocols=_int_tuple(result["component_manifest_protocols"]),
        metadata_version=_int(result["metadata_version"]),
    )


def negotiate(runtime: ProvisionedEngine) -> EngineSourceInfo:
    """Confirm the provisioned engine matches the supported package/protocol
    range -- the identical check `engine.negotiate_protocol()` applies to the
    installed engine (rule 28), run here before discovery or render.
    """  # noqa: D205
    info = fetch_info(runtime)
    compat.require_supported_package(info.package_version)
    compat.require_projectspec_protocol(
        info.package_version, info.projectspec_protocols
    )
    compat.require_component_manifest_protocol(
        info.package_version, info.component_manifest_protocols
    )
    compat.require_metadata_version(info.package_version, info.metadata_version)
    return info


def discover(runtime: ProvisionedEngine) -> tuple[Descriptor, ...]:
    """The provisioned engine's own component catalogue.

    Call `negotiate` first -- this performs no compatibility check of its
    own, mirroring `engine.py`'s functions, which each re-check
    independently rather than trusting an earlier caller.
    """
    result = _call_worker(runtime, "discover")
    descriptors = result.get("descriptors", [])
    return tuple(
        Descriptor.model_validate(item)
        for item in (descriptors if isinstance(descriptors, list) else [])
    )


def render(
    runtime: ProvisionedEngine, payload: Mapping[str, object]
) -> tuple[tuple[str, bytes], ...]:
    """Parse, validate, and render `payload` against the provisioned engine.

    Returns plain `(target, content)` pairs -- `pipeline.finalise_files`
    (ADR 0044) accepts exactly this shape, so the parent never needs a real
    `RenderedProject` for this route. Deliberately returns no
    generation-metadata document: the worker's `render` operation never
    produces one to send (rule 29).
    """
    result = _call_worker(runtime, "render", {"payload": dict(payload)})
    files = result.get("files", [])
    return tuple(
        (str(item["target"]), base64.b64decode(item["content_b64"]))
        for item in (files if isinstance(files, list) else [])
    )
