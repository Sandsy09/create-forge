"""Out-of-process mirror of `engine.py`, run inside a provisioned engine only.

ADR 0044 (CF-18.02): `--engine-source`/`--engine-ref` provision a named local
path or VCS URL into an isolated ephemeral environment containing *only* that
engine -- deliberately never `create-forge` itself (rule 25,
docs/engine-default-cli.md). This file is the thing that runs inside that
environment: `engine_source.py` locates it on disk with
`importlib.resources` and executes it as a plain script,
``<venv-python> _engine_worker.py <op>``, with a JSON request on stdin and a
JSON response on stdout. It is never imported as `create_forge._engine_worker`
by the parent process -- `create_forge` is not installed where this runs.

Stdlib and the public `forge_template` facade only, matching `engine.py`'s own
"only the public facade" rule (`tests/test_engine_contract.py`'s
`test_engine_adapter_imports_only_the_public_forge_template_facade`, mirrored
for this file by a sibling guard in `tests/test_engine_source.py`). No
`create_forge` import of any kind -- this module must run standalone in an
environment that does not have it.

Protocol, one call per operation:

- ``info``: no input. Returns the four `EngineInfo` facts, unchecked -- the
  parent runs `compat.py`'s compatibility check against them before doing
  anything else (rule 28).
- ``discover``: no input. Returns the discovered catalogue as plain dicts
  shaped like `create_forge.descriptors.Descriptor` -- only the fields the
  client consumes, not a full `ComponentDescriptor` dump.
- ``render``: ``{"payload": <ProjectSpec wire dict>}``. Parses, validates, and
  renders it against *this* engine, returning immutable in-memory files as
  base64 -- deliberately never `RenderedProject.metadata` (rule 29: an
  `--engine-source` render is not update-eligible, so no generation-metadata
  document is ever produced, let alone crosses this boundary).

A business failure (an invalid payload, an unsatisfied requirement, ...)
raises `forge_template.ForgeEngineError` inside this process; it is caught
here and reported as a structured `{"ok": false, "error": {...}}` response,
never as a non-zero exit or a raw traceback -- `engine_source.py` translates
it the same way `engine.explain()` does for the in-process route.
"""

from __future__ import annotations

import base64
import json
import sys

from forge_template import (
    ForgeEngineError,
    discover_components,
    get_engine_info,
    parse_project_spec,
    render_project,
    validate_project_spec,
)


def _info() -> dict[str, object]:
    info = get_engine_info()
    # `metadata_version` postdates the 0.5.0 cutover (engine.py's own
    # docstring for the in-process path; cli.py's doctor negotiation applies
    # the identical `getattr` fallback) -- a provisioned engine older than
    # that predates the attribute entirely. Substituting 0, never a real
    # supported value (compat.SUPPORTED_GENERATION_METADATA_VERSIONS starts
    # at 1), lets `fetch_info` succeed so `negotiate`'s own ordered checks
    # reach `compat.require_supported_package` and reject the engine as an
    # incompatible *package version* (exit 3) instead of this worker call
    # crashing first and surfacing as a generic, wrong-class `EngineSourceError`
    # (exit 1).
    return {
        "package_version": info.package_version,
        "projectspec_protocols": list(info.projectspec_protocols),
        "component_manifest_protocols": list(info.component_manifest_protocols),
        "metadata_version": getattr(info, "metadata_version", 0),
    }


def _discover() -> dict[str, object]:
    descriptors = [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "kind": d.kind,
            "requires": [{"id": r.id} for r in d.requires],
            "options": [
                {
                    "name": o.name,
                    "type": o.type,
                    "required": o.required,
                    "default": o.default,
                    "choices": list(o.choices),
                    "description": o.description,
                    "format": o.format,
                }
                for o in d.options
            ],
        }
        for d in discover_components()
    ]
    return {"descriptors": descriptors}


def _render(payload: object) -> dict[str, object]:
    spec = parse_project_spec(payload if isinstance(payload, dict) else {})
    validated = validate_project_spec(spec)
    rendered = render_project(validated)
    files = [
        {
            "target": file.target,
            "content_b64": base64.b64encode(file.content).decode("ascii"),
        }
        for file in rendered.files
    ]
    return {"files": files}


def _error_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, ForgeEngineError):
        return {
            "code": exc.code.value,
            "operation": exc.operation,
            "message": exc.message,
            "details": [
                {
                    "code": detail.code,
                    "path": list(detail.path),
                    "message": detail.message,
                }
                for detail in exc.details
            ],
        }
    return {
        "code": "internal-error",
        "operation": None,
        "message": f"{type(exc).__name__}: {exc}",
        "details": [],
    }


def _dispatch(op: str, request: dict[str, object]) -> dict[str, object]:
    if op == "info":
        return _info()
    if op == "discover":
        return _discover()
    if op == "render":
        return _render(request.get("payload"))
    msg = f"unknown operation {op!r}"
    raise ValueError(msg)


def _read_request() -> str:
    """The request, as strict UTF-8 from the binary stdin.

    The protocol is UTF-8 in both directions whatever this interpreter's locale
    is (CF-23.01, docs/subprocess-output.md), so the text layer -- which would
    decode with the locale -- is bypassed. A byte that is not valid UTF-8 raises
    here and is reported as a structured error by `main`, like any other bad
    request. This file cannot import `create_forge.capture`: it runs where
    `create_forge` is not installed.
    """
    return sys.stdin.buffer.read().decode("utf-8")


def _emit(response: dict[str, object]) -> None:
    """Write exactly one JSON object and a newline, as UTF-8, to the binary stdout.

    `json.dumps` keeps its default `ensure_ascii=True`, so the bytes are ASCII --
    valid UTF-8 -- and there is no newline translation to differ by platform.
    """
    sys.stdout.buffer.write((json.dumps(response) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def main(argv: list[str]) -> int:
    """Read one JSON request from stdin, write one JSON response to stdout.

    Always exits `0` and always writes exactly one JSON object -- a usage
    mistake or a business failure is reported in the response body
    (`{"ok": false, ...}`), not through the process exit status, so
    `engine_source.py` has exactly one place to look for a failure.
    """
    response: dict[str, object]
    if len(argv) != 2:  # noqa: PLR2004 - argv[0] plus exactly one operation name
        response = {
            "ok": False,
            "error": {
                "code": "usage-error",
                "operation": None,
                "message": "expected exactly one operation argument",
                "details": [],
            },
        }
        _emit(response)
        return 0

    op = argv[1]
    try:
        raw = _read_request()
        request = json.loads(raw) if raw.strip() else {}
        result = _dispatch(op, request)
    except Exception as exc:
        _emit({"ok": False, "error": _error_payload(exc)})
        return 0

    _emit({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
