"""Fault injection for the installed console (CF-23.02, ADR 0057).

Two hand-built wheels, installed with `uv pip install <local .whl>` into their
own throwaway environment so `uv` generates real, Windows-native launcher
executables for their console scripts -- what `CreateProcess` finds by a bare
name (`git`, `uv`) is not something a `.cmd`/`.bat` file reliably is, and
building a real launcher by hand would mean reimplementing what `uv`/`pip`
already do for every other installed console script in this project.

- **The tool shim** (`build_shim_wheel`) provides `git`/`uv` console scripts
  that delegate to the real tool named by `CF_FAKE_REAL_GIT`/`CF_FAKE_REAL_UV`,
  except for one behaviour a `CF_FAKE_GIT_MODE`/`CF_FAKE_UV_MODE` environment
  variable selects: undecodable bytes from the one diagnostic subcommand each
  production site reads (`git config --get`, `uv --version`), proving
  `docs/subprocess-output.md`'s diagnostic rule holds through the installed
  console and not only against a synthetic child in `test_subprocess_decoding.py`;
  or a `git commit` that fails for real, with a credential-shaped string in its
  stderr, proving `lifecycle._run_git`'s fixed warning never forwards it.
- **The fake engine** (`build_fake_engine_wheel`) is a `forge_template`
  look-alike exporting the six names `_engine_worker.py` imports, so
  `--engine-source <local path>` provisions it with no network and no real
  build backend. `CF_FAKE_ENGINE_MODE` selects what its `info` response's raw
  bytes look like, proving `_call_worker`'s strict protocol decode rejects
  each one through the real out-of-process worker.

Neither wheel is ever installed alongside `create_forge` itself: the shim
lives on `PATH` only for the one subprocess call under test, and the fake
engine is provisioned into its own throwaway `--engine-source` environment,
which never has `create-forge` installed (ADR 0044).
"""

from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

_SHIM_DIST = "create_forge_fake_tools"
_SHIM_VERSION = "0.0.1"

_ENGINE_DIST = "forge_template"
_ENGINE_VERSION = "0.0.1"

# Not UTF-8, and cp1252 has no character for the last five -- the same bytes
# `tests/test_subprocess_decoding.py` uses, so a failure here means exactly
# the same thing it would there.
UNDECODABLE = bytes([0xFF, 0xFE, 0x81, 0x8D, 0x8F, 0x90, 0x9D])


def _record_line(archive_path: str, content: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return f"{archive_path},sha256={digest.decode('ascii')},{len(content)}"


def _write_wheel(
    out_dir: Path, distribution: str, version: str, files: Mapping[str, bytes]
) -> Path:
    """Build `<distribution>-<version>-py3-none-any.whl` from `files`.

    `files` maps an archive-relative path to its bytes; the `.dist-info`
    directory (`METADATA`, `WHEEL`, `RECORD`) is added on top -- callers supply
    only the package's own files and `entry_points.txt`, if any.
    """
    dist_info = f"{distribution}-{version}.dist-info"
    metadata = (
        f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n"
        "Summary: Test-only fixture; never published.\n"
    ).encode()
    wheel = (
        b"Wheel-Version: 1.0\nGenerator: create-forge-tests\n"
        b"Root-Is-Purelib: true\nTag: py3-none-any\n"
    )

    complete = {
        **files,
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": wheel,
    }
    record_lines = [_record_line(path, content) for path, content in complete.items()]
    record_lines.append(f"{dist_info}/RECORD,,")
    record = ("\n".join(record_lines) + "\n").encode()

    wheel_path = out_dir / f"{distribution}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in complete.items():
            archive.writestr(path, content)
        archive.writestr(f"{dist_info}/RECORD", record)
    return wheel_path


_SHIM_MODULE = '''\
"""Fake git/uv console-script bodies (CF-23.02). Delegates to the real tool
for everything except the one diagnostic subcommand its own mode targets.
"""

from __future__ import annotations

import os
import subprocess
import sys

UNDECODABLE = bytes([0xFF, 0xFE, 0x81, 0x8D, 0x8F, 0x90, 0x9D])


def _real(tool: str) -> str:
    path = os.environ.get(f"CF_FAKE_REAL_{tool.upper()}")
    if not path:
        sys.stderr.write(f"fake {tool} shim: CF_FAKE_REAL_{tool.upper()} is not set\\n")
        sys.exit(97)
    return path


def _passthrough(tool: str) -> int:
    completed = subprocess.run([_real(tool), *sys.argv[1:]], check=False)
    return completed.returncode


def git_main() -> None:
    mode = os.environ.get("CF_FAKE_GIT_MODE", "passthrough")
    if mode == "bad-config-bytes" and sys.argv[1:3] == ["config", "--get"]:
        sys.stdout.buffer.write(UNDECODABLE + b"\\n")
        sys.exit(0)
    if mode == "fail-commit" and sys.argv[1:2] == ["commit"]:
        secret = os.environ.get(
            "CF_FAKE_SECRET_URL", "https://user:hunter2@example.com/private/repo"
        )
        sys.stderr.write(f"fatal: hook rejected the commit ({secret})\\n")
        sys.exit(1)
    sys.exit(_passthrough("git"))


def uv_main() -> None:
    mode = os.environ.get("CF_FAKE_UV_MODE", "passthrough")
    if mode == "bad-version-bytes" and sys.argv[1:2] == ["--version"]:
        sys.stdout.buffer.write(UNDECODABLE + b"\\n")
        sys.exit(0)
    sys.exit(_passthrough("uv"))
'''

_SHIM_ENTRY_POINTS = (
    "[console_scripts]\n"
    "git = create_forge_fake_tools:git_main\n"
    "uv = create_forge_fake_tools:uv_main\n"
)


def build_shim_wheel(out_dir: Path) -> Path:
    """Build the `git`/`uv` shim wheel described in the module docstring."""
    dist_info = f"{_SHIM_DIST}-{_SHIM_VERSION}.dist-info"
    files = {
        "create_forge_fake_tools/__init__.py": _SHIM_MODULE.encode(),
        f"{dist_info}/entry_points.txt": _SHIM_ENTRY_POINTS.encode(),
    }
    return _write_wheel(out_dir, _SHIM_DIST, _SHIM_VERSION, files)


_ENGINE_MODULE = '''\
"""A `forge_template` look-alike for `--engine-source` (CF-23.02).

Exports the six names `_engine_worker.py` imports; `discover`/`render`/`validate`
are never reached by the scenarios this fixture serves (every one fails at the
`info` call, which `negotiate` always makes first) so they raise if ever
called, rather than pretending to implement the real engine's behaviour.
`CF_FAKE_ENGINE_MODE` controls what `get_engine_info` writes to its own stdout
*before* returning a valid result, corrupting the worker's one response the
same four ways `tests/test_subprocess_decoding.py` proves against a synthetic
child -- except here it is the real worker, talking to a real provisioned
engine, that produces the bytes `_call_worker` must reject.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


class ForgeEngineError(Exception):
    """Mirrors the real engine's business-failure exception."""


@dataclass(frozen=True)
class EngineInfo:
    package_version: str
    projectspec_protocols: tuple[int, ...]
    component_manifest_protocols: tuple[int, ...]
    metadata_version: int


def _corrupt() -> None:
    mode = os.environ.get("CF_FAKE_ENGINE_MODE", "")
    if mode == "malformed-utf8":
        sys.stdout.buffer.write(bytes([0xFF, 0xFE]))
    elif mode == "byte-order-mark":
        sys.stdout.buffer.write(b"\\xef\\xbb\\xbf")
    elif mode == "empty-body":
        sys.stdout.flush()
        sys.exit(0)
    elif mode == "non-json":
        sys.stdout.buffer.write(b"not json at all")
        sys.stdout.flush()
        sys.exit(0)


def get_engine_info() -> EngineInfo:
    _corrupt()
    return EngineInfo(
        package_version="0.0.1",
        projectspec_protocols=(1,),
        component_manifest_protocols=(1, 2, 3),
        metadata_version=1,
    )


def discover_components() -> object:
    raise ForgeEngineError("discover_components is not implemented by this fixture")


def parse_project_spec(payload: object) -> object:
    raise ForgeEngineError("parse_project_spec is not implemented by this fixture")


def validate_project_spec(spec: object) -> object:
    raise ForgeEngineError("validate_project_spec is not implemented by this fixture")


def render_project(spec: object) -> object:
    raise ForgeEngineError("render_project is not implemented by this fixture")
'''


def build_fake_engine_wheel(out_dir: Path) -> Path:
    """Build the `forge_template` look-alike wheel described in the module
    docstring, importable as `forge_template` once installed.
    """
    files = {"forge_template/__init__.py": _ENGINE_MODULE.encode()}
    return _write_wheel(out_dir, _ENGINE_DIST, _ENGINE_VERSION, files)
