"""`doctor` -- environment diagnostics, table and `--json` forms.

Stays offline: reports the registry's bundled template source but never
resolves a ref, and negotiates against the installed engine (if any). An
installed engine outside the declared package range (ADR 0061) and a protocol
mismatch are each one failed check row here, never a crash.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from create_forge import capture
from create_forge.commands import _output
from create_forge.compat import (
    ENGINE_DISTRIBUTION,
    INTEGRATION_LINE,
    SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS,
    SUPPORTED_ENGINE_RANGE,
    SUPPORTED_GENERATION_METADATA_VERSIONS,
    SUPPORTED_PROJECTSPEC_PROTOCOLS,
    EngineCompatibilityError,
    require_supported_package,
)
from create_forge.config import config_path, load_config
from create_forge.registry import load_registry

if TYPE_CHECKING:
    from create_forge.models import Registry


def _dist_version(name: str) -> str:
    """Installed version of a distribution, or "unknown" if it can't be found.

    Editable installs of `create-forge` itself hit the fallback in normal
    development; a distribution genuinely not being installed (e.g. `copier`
    in some hypothetical stripped environment) hits it too.
    """
    try:
        return version(name)
    except PackageNotFoundError:  # pragma: no cover - editable installs
        return "unknown"


def _optional_dist_version(name: str) -> str | None:
    """Installed version of an optional distribution, or `None` if absent.

    Distinct from `_dist_version`: `create-forge` always depends on `name`
    there, so "unknown" signals a broken environment. Here `name` is either
    the optional `legacy` extra's `copier` -- not installed is the normal,
    expected default -- or `forge-template`/`uv`, both required since ADR
    0040 (CF-18.01), where a genuine absence signals a broken install.
    docs/engine-resolution.md's diagnostics contract documents
    `integration.copier`/`integration.engine_package` as `null` for either
    case, never the string "unknown".
    """
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _markers(target: Console) -> tuple[str, str]:
    """Return (pass, fail) markers the console's encoding can actually render.

    A Windows console on the cp1252 codepage -- the default outside Windows
    Terminal -- cannot encode the check-mark glyphs, and Rich lets the
    resulting UnicodeEncodeError propagate rather than degrading. `doctor`
    needs markers it knows will survive before it ever tries to print them.
    """
    try:
        "✓✗".encode(target.encoding)
    except (UnicodeEncodeError, LookupError):
        return "OK", "FAIL"
    return "✓", "✗"


@dataclass(frozen=True, slots=True)
class Check:
    """One row of `doctor` output.

    `informational` rows report a fact rather than a pass/fail condition (the
    installed Copier version, say) and never affect `doctor`'s exit status —
    only `passed=False` on a non-informational row does.
    """

    name: str
    passed: bool
    detail: str
    informational: bool = False


@dataclass(frozen=True, slots=True)
class Integration:
    """The active create-forge/forge-template integration line and its
    versions -- see docs/engine-resolution.md for what each field means and
    when it is populated. `engine_range` and every `*_supported` field are
    always populated: the declared range and supported protocols are fixed by
    this create-forge release, independent of the environment.
    `engine_package` is `None` only in a broken install -- `forge-template`
    is a required dependency since ADR 0040 (CF-18.01). `copier` is `None`
    when the optional `legacy` extra is absent. Since ADR 0040 decision 6,
    `doctor` negotiates against the real engine (`engine.get_info()`, which
    performs no compatibility check itself), so every `*_detected` field is
    populated whenever the engine is importable at all -- `None` only when it
    is not.
    """  # noqa: D205

    line: str
    copier: str | None
    engine_package: str | None
    engine_range: str
    projectspec_supported: str
    projectspec_detected: str | None
    component_manifest_supported: str
    component_manifest_detected: str | None
    metadata_version_supported: str
    metadata_version_detected: int | None
    template_source: str | None
    template_ref: str | None


@dataclass(frozen=True, slots=True)
class ConfigSummary:
    """Where config was read from and which keys it set."""

    path: str
    keys: list[str]


@dataclass(frozen=True, slots=True)
class CopierCache:
    """Copier's git-mirror cache location and whether create-forge could use
    it -- see docs/engine-resolution.md's diagnostics contract. `writable` is
    the only field that can fail a `doctor` check; the rest are facts.
    """  # noqa: D205

    path: str
    override: bool
    exists: bool
    writable: bool


@dataclass(frozen=True, slots=True)
class UvStatus:
    """The `uv` create-forge would actually run, and the one the `engine`
    extra declares -- distinct facts that can legitimately differ.
    """  # noqa: D205

    path: str | None
    version: str | None
    package: str | None


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Everything `doctor` reports, gathered once so the table and `--json`
    output can never disagree.
    """  # noqa: D205

    create_forge: str
    python: str
    platform: str
    integration: Integration
    config: ConfigSummary
    copier_cache: CopierCache | None
    uv: UvStatus
    checks: list[Check]

    @property
    def ok(self) -> bool:
        """Whether every non-informational check passed."""
        return all(check.passed for check in self.checks if not check.informational)


def _tooling_diagnostics(checks: list[Check]) -> tuple[CopierCache | None, UvStatus]:
    """Append the tooling rows and return the structured facts.

    The git / uv rows land in `checks` unconditionally; the Copier-cache rows
    only when `copier` -- the optional `legacy` extra since ADR 0040 decision
    2 -- is actually importable, reporting `None`/an informational row
    instead of raising when it is not (decision 6's "`integration.copier`
    becomes `null` when the `legacy` extra is absent", applied to the cache
    facts alongside it). The cache and uv facts `doctor --json` reports
    alongside the checks come back as dataclasses.
    """
    git_found = shutil.which("git")
    checks.append(
        Check(
            "git",
            bool(git_found),
            git_found
            or "not on PATH — required to initialise and update generated "
            "projects (and to clone templates under --legacy)",
        )
    )

    uv_found = shutil.which("uv")
    uv_version = _uv_version(uv_found)
    checks.append(
        Check(
            "uv",
            bool(uv_found),
            f"{uv_version} ({uv_found})"
            if uv_found and uv_version
            else uv_found or "not on PATH — required by generated projects",
        )
    )

    try:
        from create_forge.runner import (  # noqa: PLC0415
            cache_probe,
            copier_cache_location,
        )
    except ImportError:
        checks.append(
            Check(
                "copier cache",
                True,
                r"not applicable — install with pip install 'create-forge\[legacy]'",
                informational=True,
            )
        )
        return None, UvStatus(
            path=uv_found, version=uv_version, package=_optional_dist_version("uv")
        )

    cache = copier_cache_location()
    probe = cache_probe(cache)
    checks.append(
        Check(
            "copier cache",
            True,
            f"{cache.path} "
            + (
                "(COPIER_CACHE_DIR override)"
                if cache.overridden
                else "(default location)"
            ),
            informational=True,
        )
    )
    checks.append(
        Check(
            "copier cache writable",
            probe.writable,
            "writable"
            if probe.writable
            else "not writable — set COPIER_CACHE_DIR to a writable directory",
        )
    )

    return (
        CopierCache(
            path=str(cache.path),
            override=cache.overridden,
            exists=probe.exists,
            writable=probe.writable,
        ),
        UvStatus(
            path=uv_found,
            version=uv_version,
            package=_optional_dist_version("uv"),
        ),
    )


def _engine_check(engine_package: str | None, engine_range: str) -> Check:
    """The `engine` row: installed *and* inside the declared package range.

    Range membership goes through `compat.require_supported_package`, the one
    check `new` applies, so `doctor` cannot report healthy for an engine `new`
    refuses with exit `3` (ADR 0061, closing the gap the FT-28.03 hand-off
    on CF-29.01 recorded).
    """
    if engine_package is None:
        return Check(
            "engine",
            False,
            f"not installed (supports {engine_range}) — reinstall create-forge",
        )
    try:
        require_supported_package(engine_package)
    except EngineCompatibilityError:
        return Check(
            "engine",
            False,
            f"{ENGINE_DISTRIBUTION} {engine_package} is outside the supported "
            f"{engine_range} — `new` will refuse it; reinstall create-forge",
        )
    return Check(
        "engine",
        True,
        f"{ENGINE_DISTRIBUTION} {engine_package} (supports {engine_range})",
    )


def _gather_diagnostics() -> Diagnostics:  # noqa: PLR0915 - one linear pass gathering every doctor fact and check, mirroring `_run_engine`'s own justification for a single unbroken flow rather than an arbitrary split
    """Run every doctor check and collect every reportable fact.

    `doctor` stays offline: it reports the registry's bundled template source
    but never resolves a ref, since that would mean a network call for what
    is meant to be a fast local health check. Since ADR 0040 decision 6,
    engine presence is checked via `importlib.metadata`, and since ADR 0061
    (CF-29.01) that row also fails when the installed version is outside
    `SUPPORTED_ENGINE_RANGE` -- the same `require_supported_package` check
    `new` applies, so `doctor` can no longer report healthy for an engine
    `new` refuses. A real negotiation runs through `engine.get_info()`, which
    performs no compatibility check of its own -- a protocol/`metadata_version`
    mismatch surfaces as one failed check row here rather than raising
    `EngineCompatibilityError` and crashing `doctor` outright. `*_detected`
    fields stay `None` only when the engine cannot be imported at all.
    """
    checks: list[Check] = []

    def check(passed: bool, name: str, detail: str) -> None:
        checks.append(Check(name, passed, detail))

    def info(name: str, detail: str) -> None:
        checks.append(Check(name, True, detail, informational=True))

    py = sys.version_info
    python_version = f"{py.major}.{py.minor}.{py.micro}"
    check(py >= (3, 11), "Python 3.11+", python_version)

    copier_cache, uv_status = _tooling_diagnostics(checks)

    if shutil.which("git"):
        name = _git_config("user.name")
        email = _git_config("user.email")
        check(
            bool(name and email),
            "git identity",
            f"{name} <{email}>"
            if name and email
            else "unset — scaffolding cannot commit",
        )

    registry: Registry | None = None
    try:
        registry = load_registry()
        check(True, "registry", f"{len(registry.templates)} template(s)")
    except RuntimeError as exc:
        check(False, "registry", str(exc).splitlines()[0])

    template_source: str | None = None
    if registry is not None:
        default = registry.get(registry.default_template)
        template_source = str(default.url)
        source_detail = (
            f"{template_source} (default: {registry.default_template}, "
            "ref: latest PEP 440 tag — resolved at scaffold time)"
        )
    else:
        source_detail = "unavailable — registry did not load"

    config_keys: list[str] = []
    try:
        config = load_config()
        config_keys = sorted(config.model_dump(exclude_none=True))
        keys_detail = ", ".join(config_keys) or "no values set"
        check(True, "config", f"{config_path()} — {keys_detail}")
    except ValueError as exc:
        check(False, "config", str(exc).splitlines()[0])

    engine_range = f"{ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}"
    engine_package = _optional_dist_version(ENGINE_DISTRIBUTION)
    copier_package = _optional_dist_version("copier")
    projectspec_supported = ",".join(str(p) for p in SUPPORTED_PROJECTSPEC_PROTOCOLS)
    manifest_supported = ",".join(
        str(p) for p in SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS
    )
    metadata_supported = ",".join(
        str(v) for v in SUPPORTED_GENERATION_METADATA_VERSIONS
    )

    info("create-forge", _dist_version("create-forge"))
    info(
        "copier",
        copier_package
        if copier_package is not None
        else r"not installed — install with pip install 'create-forge\[legacy]'",
    )
    info("template source", source_detail)
    info("integration line", INTEGRATION_LINE)
    checks.append(_engine_check(engine_package, engine_range))

    projectspec_detected: str | None = None
    manifest_detected: str | None = None
    metadata_detected: int | None = None
    if engine_package is not None:
        try:
            from create_forge import engine as _engine  # noqa: PLC0415

            negotiated = _engine.get_info()
            projectspec_detected = ",".join(
                str(p) for p in negotiated.projectspec_protocols
            )
            manifest_detected = ",".join(
                str(p) for p in negotiated.component_manifest_protocols
            )
            metadata_detected = negotiated.metadata_version
            projectspec_ok = bool(
                set(negotiated.projectspec_protocols)
                & set(SUPPORTED_PROJECTSPEC_PROTOCOLS)
            )
            manifest_ok = bool(
                set(negotiated.component_manifest_protocols)
                & set(SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS)
            )
            metadata_ok = metadata_detected in SUPPORTED_GENERATION_METADATA_VERSIONS
        except Exception as exc:
            # doctor must never crash; a too-old engine may not even have
            # these attributes (e.g. `metadata_version` postdates 0.3.2) --
            # report whatever the engine raised or a stale shape produced as
            # one failed check row instead.
            check(False, "engine negotiation", str(exc).splitlines()[0])
        else:
            check(
                projectspec_ok and manifest_ok and metadata_ok,
                "engine negotiation",
                f"ProjectSpec {projectspec_detected}, component manifest "
                f"{manifest_detected}, metadata {metadata_detected}",
            )

    return Diagnostics(
        create_forge=_dist_version("create-forge"),
        python=python_version,
        platform=sys.platform,
        integration=Integration(
            line=INTEGRATION_LINE,
            copier=copier_package,
            engine_package=engine_package,
            engine_range=engine_range,
            projectspec_supported=projectspec_supported,
            projectspec_detected=projectspec_detected,
            component_manifest_supported=manifest_supported,
            component_manifest_detected=manifest_detected,
            metadata_version_supported=metadata_supported,
            metadata_version_detected=metadata_detected,
            template_source=template_source,
            template_ref=None,
        ),
        config=ConfigSummary(path=str(config_path()), keys=config_keys),
        copier_cache=copier_cache,
        uv=uv_status,
        checks=checks,
    )


def _uv_version(uv_path: str | None) -> str | None:
    """The version `uv --version` reports, or None when it can't be trusted.

    `uv --version` prints e.g. `uv 0.12.10`. Only a token that looks like a
    version is returned, so nothing arbitrary from the subprocess can reach
    `doctor`'s output.
    """
    if not uv_path:
        return None
    try:
        result = capture.run_captured([uv_path, "--version"], timeout=5)
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None
    # A diagnostic read (CF-23.01): lenient, and only a validated token escapes.
    match capture.decode_diagnostic(result.stdout).split():
        case [_, token, *_] if re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", token):
            return token
        case _:
            return None


def _render_diagnostics_table(diagnostics: Diagnostics, target: Console) -> None:
    """Render `doctor`'s checks as the human-facing Rich table."""
    passed_marker, failed_marker = _markers(target)

    table = Table(box=None, pad_edge=False)
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", style="dim")

    for entry in diagnostics.checks:
        if entry.informational:
            table.add_row("[dim]-[/]", entry.name, entry.detail)
            continue
        marker = passed_marker if entry.passed else failed_marker
        style = "green" if entry.passed else "red"
        table.add_row(f"[{style}]{marker}[/]", entry.name, entry.detail)

    target.print(table)


def _diagnostics_payload(diagnostics: Diagnostics) -> dict[str, object]:
    """The stable JSON shape `doctor --json` emits.

    Documented field-by-field in docs/engine-resolution.md's diagnostics
    contract -- new fields may be added, but existing ones keep their meaning.
    """
    integration = diagnostics.integration
    return {
        "create_forge": diagnostics.create_forge,
        "python": diagnostics.python,
        "platform": diagnostics.platform,
        "integration": {
            "line": integration.line,
            "copier": integration.copier,
            "engine_package": integration.engine_package,
            "engine_range": integration.engine_range,
            "projectspec_protocol": {
                "supported": integration.projectspec_supported,
                "detected": integration.projectspec_detected,
            },
            "component_manifest_protocol": {
                "supported": integration.component_manifest_supported,
                "detected": integration.component_manifest_detected,
            },
            "metadata_version": {
                "supported": integration.metadata_version_supported,
                "detected": integration.metadata_version_detected,
            },
            "template_source": integration.template_source,
            "template_ref": integration.template_ref,
        },
        "config": {"path": diagnostics.config.path, "keys": diagnostics.config.keys},
        "copier_cache": (
            {
                "path": diagnostics.copier_cache.path,
                "override": diagnostics.copier_cache.override,
                "exists": diagnostics.copier_cache.exists,
                "writable": diagnostics.copier_cache.writable,
            }
            if diagnostics.copier_cache is not None
            else None
        ),
        "uv": {
            "path": diagnostics.uv.path,
            "version": diagnostics.uv.version,
            "package": diagnostics.uv.package,
        },
        "checks": [
            {"name": c.name, "ok": c.passed, "detail": c.detail}
            for c in diagnostics.checks
            if not c.informational
        ],
        "ok": diagnostics.ok,
    }


def doctor(*, as_json: bool) -> None:
    """Check that the environment can scaffold and update projects."""
    diagnostics = _gather_diagnostics()

    if as_json:
        typer.echo(json.dumps(_diagnostics_payload(diagnostics), indent=2))
    else:
        _render_diagnostics_table(diagnostics, _output.console)

    if not diagnostics.ok:
        raise typer.Exit(1)


def _git_config(key: str) -> str | None:
    try:
        result = capture.run_captured(["git", "config", "--get", key], timeout=5)
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None
    # A diagnostic read (CF-23.01): a name may be non-ASCII, and doctor only asks
    # whether one is set, so a lenient decode is enough and cannot raise.
    return capture.decode_diagnostic(result.stdout).strip() or None
