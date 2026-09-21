"""Bind the installed update-safety evidence to one release candidate.

CF-22.03 (ADR 0054). A validation record is only worth what it is bound to: the
exact source, the exact artefacts, and the exact provider it was produced
against. This prints that binding as one Markdown table, reproducibly, so the
record is filled the same way every time -- and so CF-21.03 can re-run it on the
final release commit to *refresh* it rather than write it again by hand.

It also owns `safety_digest`: a sha256 over the source whose behaviour the
installed update-safety suite proves. `tests/test_update_safety_evidence.py`
recomputes it and fails when it no longer matches the recorded value, which is
how "if safety-relevant candidate code changes, refresh affected evidence
before publication" is enforced by a red `main` rather than remembered. Both
this script and that test import the one definition below.

**Archive hashes are not a stable identity; content digests are.** The same
source built in two different build environments produced wheels whose members
are byte-identical, in the same order, with the same timestamps and attributes --
and different archive sha256, because the compressed streams differ. Repeated
builds in one environment are identical, which is why that is easy to miss. So
the table records both: the archive sha256 (what a particular build produced, and
what PyPI will serve for the published file) and a *content digest* over each
member's name and bytes, which is independent of compression and is what two
builds of the same candidate can be expected to share.

Run `uv run poe evidence:candidate` (builds the wheel and sdist into a fresh
temporary directory), or `--no-build` for just the digest and provider hashes.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Whole files whose only job is update safety or the filesystem boundary.
SAFETY_FILES = (
    "src/create_forge/paths.py",
    "src/create_forge/update.py",
    "src/create_forge/staging.py",
)

# `cli.py` is a large file with much unrelated to update safety, so only the
# functions that route an update, orchestrate it, gate the degraded fallback and
# print recovery guidance are hashed. An unrelated edit elsewhere in `cli.py`
# must not force an evidence refresh.
CLI_FILE = "src/create_forge/cli.py"
SAFETY_CLI_FUNCTIONS = (
    "update_project",
    "_run_engine_update",
    "_print_recovery",
    "_confirm_degraded",
)

_PROVIDER = "forge-template"


def _normalise(data: bytes) -> bytes:
    """Line endings are a checkout setting, not source: CRLF becomes LF."""
    return data.replace(b"\r\n", b"\n")


def _function_sources(text: str, names: tuple[str, ...]) -> dict[str, str]:
    """The source of each named module-level function, decorators included.

    Raises:
        ValueError: a named function no longer exists at module level -- the
            guard would otherwise silently stop covering it.
    """
    lines = text.split("\n")
    found: dict[str, str] = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name in names
        ):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno]) - 1
            found[node.name] = "\n".join(lines[start : node.end_lineno])
    missing = [name for name in names if name not in found]
    if missing:
        msg = (
            f"{CLI_FILE} no longer defines {', '.join(missing)} at module level; "
            "re-point SAFETY_CLI_FUNCTIONS in scripts/candidate_evidence.py at "
            "wherever the update path lives now (and refresh the evidence)"
        )
        raise ValueError(msg)
    return found


def _feed(digest: hashlib._Hash, label: str, content: bytes) -> None:
    """Length-prefix each part so two parts can never blur into one another."""
    digest.update(f"{label}\n{len(content)}\n".encode())
    digest.update(content)
    digest.update(b"\n")


def safety_digest(repo_root: Path = REPO_ROOT) -> str:
    """The sha256 of the safety-relevant source, as `sha256:<hex>`."""
    digest = hashlib.sha256()
    for relative in SAFETY_FILES:
        _feed(digest, relative, _normalise((repo_root / relative).read_bytes()))
    cli_text = _normalise((repo_root / CLI_FILE).read_bytes()).decode("utf-8")
    sources = _function_sources(cli_text, SAFETY_CLI_FUNCTIONS)
    for name in SAFETY_CLI_FUNCTIONS:
        _feed(digest, f"{CLI_FILE}::{name}", sources[name].encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class Artefact:
    """One published file and the hash the lockfile pins it to."""

    filename: str
    hash: str


@dataclass(frozen=True, slots=True)
class LockedPackage:
    """A package as `uv.lock` records it."""

    name: str
    version: str
    sdist: Artefact | None
    wheels: tuple[Artefact, ...]


def _artefact(entry: dict[str, str]) -> Artefact:
    return Artefact(filename=entry["url"].rsplit("/", 1)[-1], hash=entry["hash"])


def lock_artifacts(lock_text: str, name: str = _PROVIDER) -> LockedPackage:
    """The named package's version and artefact hashes, from `uv.lock` text.

    Raises:
        KeyError: the lock has no such package.
    """
    for package in tomllib.loads(lock_text).get("package", []):
        if package.get("name") == name:
            sdist = package.get("sdist")
            return LockedPackage(
                name=name,
                version=package["version"],
                sdist=_artefact(sdist) if sdist else None,
                wheels=tuple(_artefact(w) for w in package.get("wheels", [])),
            )
    msg = f"uv.lock has no package named {name!r}"
    raise KeyError(msg)


def _sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def content_digest(archive: Path) -> str:
    """A sha256 over an archive's members' names and bytes, as `sha256:<hex>`.

    Independent of compression, member order and archive metadata, so two builds
    of the same source share it even when their archive sha256 differ. Supports
    a wheel (zip) and an sdist (`.tar.gz`).
    """
    digest = hashlib.sha256()
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zipped:
            for name in sorted(zipped.namelist()):
                if not name.endswith("/"):
                    _feed(digest, name, zipped.read(name))
    else:
        with tarfile.open(archive, "r:gz") as tarred:
            for member in sorted(tarred.getmembers(), key=lambda m: m.name):
                extracted = tarred.extractfile(member) if member.isfile() else None
                if extracted is not None:
                    _feed(digest, member.name, extracted.read())
    return f"sha256:{digest.hexdigest()}"


def _run(argv: list[str], cwd: Path) -> str:
    """Run a command, decoding leniently; `""` if it cannot be run."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed executables, reviewed args
            argv, cwd=cwd, capture_output=True, check=False, timeout=600
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def build_distributions(out_dir: Path, repo_root: Path = REPO_ROOT) -> list[Path]:
    """Build the sdist and wheel `release.yml` would, into `out_dir`."""
    subprocess.run(  # noqa: S603 - fixed executable, reviewed args
        ["uv", "build", "--out-dir", str(out_dir)],  # noqa: S607
        cwd=repo_root,
        check=True,
    )
    # `uv build` also writes a `.gitignore` into the output directory; only the
    # distributions are evidence.
    wheels = sorted(out_dir.glob("*.whl"))
    sdists = sorted(out_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        msg = f"expected one wheel and one sdist in {out_dir}, found {wheels + sdists}"
        raise RuntimeError(msg)
    return [*wheels, *sdists]


def render_table(  # noqa: PLR0913 - one keyword per row group of the table
    *,
    commit: str,
    tree_state: str,
    version: str,
    provider: LockedPackage,
    digest: str,
    distributions: list[tuple[str, str, str, str]],
    tools: dict[str, str],
) -> str:
    """The Markdown table pasted into `docs/update-safety-validation.md`."""
    rows = [
        ("Commit", f"`{commit}` ({tree_state})"),
        ("create-forge version", f"`{version}`"),
    ]
    for kind, filename, archive_sha, content in distributions:
        rows.append((f"create-forge {kind} (archive)", f"`{filename}` `{archive_sha}`"))
        rows.append((f"create-forge {kind} content digest", f"`{content}`"))
    rows.append((f"{provider.name} version", f"`{provider.version}` (from `uv.lock`)"))
    artefacts = [("sdist", provider.sdist)] if provider.sdist else []
    artefacts += [("wheel", wheel) for wheel in provider.wheels]
    rows += [
        (f"{provider.name} {kind}", f"`{item.filename}` `{item.hash}`")
        for kind, item in artefacts
    ]
    rows += [(tool, f"`{value}`") for tool, value in tools.items()]
    rows.append(("Safety-relevant source digest", f"`{digest}`"))
    lines = ["| Field | Value |", "| --- | --- |"]
    lines += [f"| {field} | {value} |" for field, value in rows]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the candidate binding table."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="skip building the wheel and sdist (digest and provider hashes only)",
    )
    args = parser.parse_args(argv)

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    version = pyproject["project"]["version"]
    provider = lock_artifacts((REPO_ROOT / "uv.lock").read_text("utf-8"))

    dirty = _run(["git", "status", "--porcelain"], REPO_ROOT)
    tree_state = "working tree clean" if not dirty else "working tree DIRTY"

    distributions: list[tuple[str, str, str, str]] = []
    if not args.no_build:
        with tempfile.TemporaryDirectory(prefix="candidate-evidence-") as scratch:
            for path in build_distributions(Path(scratch)):
                kind = "wheel" if path.suffix == ".whl" else "sdist"
                distributions.append(
                    (kind, path.name, _sha256_file(path), content_digest(path))
                )
    tools = {
        "uv": _run(["uv", "--version"], REPO_ROOT),
        "git": _run(["git", "--version"], REPO_ROOT),
        "Python": sys.version.split()[0],
    }
    print(
        render_table(
            commit=_run(["git", "rev-parse", "HEAD"], REPO_ROOT),
            tree_state=tree_state,
            version=version,
            provider=provider,
            digest=safety_digest(),
            distributions=distributions,
            tools=tools,
        )
    )
    if dirty:
        print(
            "\nWARNING: the working tree is dirty; commit before recording this "
            "as candidate evidence.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
