"""`scripts/candidate_evidence.py` (CF-22.03, ADR 0054): the digest and hash
binding the installed update-safety evidence relies on.

The digest is what turns "refresh the evidence if safety-relevant code changes"
into a red `main`, so its two failure modes matter equally: it must **change**
when the code the installed suite proves changes, and it must **not** change for
an unrelated edit or for a checkout's line endings, or it would train people to
refresh it without re-running anything.

No network, no build (`main` is only run with `--no-build`).
"""

from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import Path

import pytest

from candidate_evidence import (
    SAFETY_CLI_FUNCTIONS,
    SAFETY_FILES,
    LockedPackage,
    content_digest,
    lock_artifacts,
    main,
    render_archive_table,
    render_table,
    safety_digest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")

_CLI = '''\
import typer

app = typer.Typer()


@app.command("update")
def update_project() -> None:
    """Route an update."""


def _run_engine_update() -> None:
    """Orchestrate it."""


def _print_recovery() -> None:
    """Print guidance."""


def _confirm_degraded() -> None:
    """Ask first."""


def unrelated() -> None:
    {body}
'''


def _write_repo(
    root: Path, *, unrelated: str = "return None", crlf: bool = False
) -> Path:
    for relative in SAFETY_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"# {relative}\n".encode())
    cli = _CLI.format(body=unrelated)
    (root / "src/create_forge/cli.py").write_bytes(
        (cli.replace("\n", "\r\n") if crlf else cli).encode()
    )
    return root


def test_the_digest_is_a_sha256(tmp_path: Path) -> None:
    assert _SHA256.fullmatch(safety_digest(_write_repo(tmp_path)))


def test_the_digest_is_deterministic(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)

    assert safety_digest(repo) == safety_digest(repo)


def test_the_digest_ignores_a_checkouts_line_endings(tmp_path: Path) -> None:
    lf = _write_repo(tmp_path / "lf")
    crlf = _write_repo(tmp_path / "crlf", crlf=True)
    for relative in SAFETY_FILES:
        (crlf / relative).write_bytes(f"# {relative}\r\n".encode())

    assert safety_digest(lf) == safety_digest(crlf)


@pytest.mark.parametrize("relative", SAFETY_FILES)
def test_the_digest_changes_when_a_safety_file_changes(
    tmp_path: Path, relative: str
) -> None:
    repo = _write_repo(tmp_path)
    before = safety_digest(repo)

    (repo / relative).write_bytes(b"# an edit\n")

    assert safety_digest(repo) != before


_DOCSTRINGS = {
    "update_project": "Route an update.",
    "_run_engine_update": "Orchestrate it.",
    "_print_recovery": "Print guidance.",
    "_confirm_degraded": "Ask first.",
}


@pytest.mark.parametrize("name", SAFETY_CLI_FUNCTIONS)
def test_the_digest_changes_when_a_safety_cli_function_changes(
    tmp_path: Path, name: str
) -> None:
    repo = _write_repo(tmp_path)
    before = safety_digest(repo)
    cli = repo / "src/create_forge/cli.py"

    cli.write_text(
        cli.read_text(encoding="utf-8").replace(
            f'    """{_DOCSTRINGS[name]}"""', "    return None"
        ),
        encoding="utf-8",
    )

    assert safety_digest(repo) != before


def test_the_digest_ignores_an_unrelated_cli_function(tmp_path: Path) -> None:
    """The point of hashing functions rather than the whole 2000-line file."""
    before = safety_digest(_write_repo(tmp_path / "a"))
    after = safety_digest(
        _write_repo(tmp_path / "b", unrelated="return 12345  # a different body")
    )

    assert before == after


def test_a_decorator_change_on_the_update_command_changes_the_digest(
    tmp_path: Path,
) -> None:
    repo = _write_repo(tmp_path)
    before = safety_digest(repo)
    cli = repo / "src/create_forge/cli.py"

    cli.write_text(
        cli.read_text(encoding="utf-8").replace(
            '@app.command("update")', '@app.command("up")'
        ),
        encoding="utf-8",
    )

    assert safety_digest(repo) != before


def test_a_missing_safety_function_fails_loudly_instead_of_dropping_out(
    tmp_path: Path,
) -> None:
    repo = _write_repo(tmp_path)
    cli = repo / "src/create_forge/cli.py"
    cli.write_text(
        cli.read_text(encoding="utf-8").replace("_print_recovery", "_renamed"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"_print_recovery.*re-point"):
        safety_digest(repo)


def test_the_real_repository_has_a_digest() -> None:
    assert _SHA256.fullmatch(safety_digest(REPO_ROOT))


_LOCK = """\
[[package]]
name = "forge-template"
version = "9.9.9"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://f.example/ft-9.9.9.tar.gz", hash = "sha256:aa" }
wheels = [
    { url = "https://f.example/ft-9.9.9-py3-none-any.whl", hash = "sha256:bb" },
]

[[package]]
name = "other"
version = "1.0"
"""


def test_lock_artifacts_reads_the_version_and_artefact_hashes() -> None:
    package = lock_artifacts(_LOCK)

    assert package.name == "forge-template"
    assert package.version == "9.9.9"
    assert package.sdist is not None
    assert (package.sdist.filename, package.sdist.hash) == (
        "ft-9.9.9.tar.gz",
        "sha256:aa",
    )
    assert [(w.filename, w.hash) for w in package.wheels] == [
        ("ft-9.9.9-py3-none-any.whl", "sha256:bb")
    ]


def test_lock_artifacts_tolerates_a_package_with_no_sdist_or_wheels() -> None:
    package = lock_artifacts(_LOCK, "other")

    assert package.sdist is None
    assert package.wheels == ()


def test_lock_artifacts_names_a_missing_package() -> None:
    with pytest.raises(KeyError, match="nothing-here"):
        lock_artifacts(_LOCK, "nothing-here")


def test_the_real_lock_pins_the_provider_to_full_hashes() -> None:
    """The provider artefacts the record binds to are immutable PyPI files, and
    `uv.lock` is where the repository pins them.
    """
    package = lock_artifacts((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))

    assert package.name == "forge-template"
    assert package.sdist is not None
    assert _SHA256.fullmatch(package.sdist.hash)
    assert package.wheels
    assert all(_SHA256.fullmatch(wheel.hash) for wheel in package.wheels)


def test_render_table_carries_every_binding_field() -> None:
    provider = LockedPackage("forge-template", "0.6.0", None, ())

    table = render_table(
        commit="abc123",
        tree_state="working tree clean",
        version="0.4.0",
        provider=provider,
        digest="sha256:" + "0" * 64,
        distributions=[
            ("wheel", "cf-0.4.0.whl", "sha256:w", "sha256:wc"),
            ("sdist", "cf.tar.gz", "sha256:s", "sha256:sc"),
        ],
        tools={"uv": "uv 0.12.13"},
    )

    for fragment in (
        "`abc123` (working tree clean)",
        "create-forge wheel (archive) | `cf-0.4.0.whl` `sha256:w`",
        "create-forge wheel content digest | `sha256:wc`",
        "create-forge sdist (archive) | `cf.tar.gz` `sha256:s`",
        "create-forge sdist content digest | `sha256:sc`",
        "forge-template version | `0.6.0` (from `uv.lock`)",
        "uv | `uv 0.12.13`",
        "Safety-relevant source digest | `sha256:" + "0" * 64,
    ):
        assert fragment in table


def test_main_without_a_build_prints_the_digest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--no-build"]) == 0

    out = capsys.readouterr().out
    assert safety_digest(REPO_ROOT) in out
    assert "forge-template version" in out


# --------------------------------------------------------------------------- #
# content_digest: the environment-independent identity of a built archive      #
# --------------------------------------------------------------------------- #

_MEMBERS = {"pkg/__init__.py": b"x = 1\n", "pkg/mod.py": b"y = 2\n"}


def _wheel(path: Path, members: dict[str, bytes], compression: int) -> Path:
    with zipfile.ZipFile(path, "w", compression) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def test_content_digest_ignores_compression_and_archive_bytes(tmp_path: Path) -> None:
    """The observed problem: identical members, different compressed streams."""
    stored = _wheel(tmp_path / "a.whl", _MEMBERS, zipfile.ZIP_STORED)
    deflated = _wheel(tmp_path / "b.whl", _MEMBERS, zipfile.ZIP_DEFLATED)

    assert stored.read_bytes() != deflated.read_bytes()  # different archive bytes
    assert content_digest(stored) == content_digest(deflated)


def test_content_digest_ignores_member_order(tmp_path: Path) -> None:
    forward = _wheel(tmp_path / "a.whl", _MEMBERS, zipfile.ZIP_DEFLATED)
    reverse = _wheel(
        tmp_path / "b.whl", dict(reversed(_MEMBERS.items())), zipfile.ZIP_DEFLATED
    )

    assert content_digest(forward) == content_digest(reverse)


def test_content_digest_changes_with_a_member_body_or_name(tmp_path: Path) -> None:
    base = content_digest(_wheel(tmp_path / "a.whl", _MEMBERS, zipfile.ZIP_DEFLATED))
    edited = {**_MEMBERS, "pkg/mod.py": b"y = 3\n"}
    renamed = {
        "pkg/other.py": _MEMBERS["pkg/mod.py"],
        "pkg/__init__.py": _MEMBERS["pkg/__init__.py"],
    }

    assert (
        content_digest(_wheel(tmp_path / "b.whl", edited, zipfile.ZIP_DEFLATED)) != base
    )
    assert (
        content_digest(_wheel(tmp_path / "c.whl", renamed, zipfile.ZIP_DEFLATED))
        != base
    )


def _sdist(path: Path, members: dict[str, bytes], mtime: int) -> Path:
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = mtime
            archive.addfile(info, io.BytesIO(content))
    return path


def test_archive_table_lists_both_digests_per_file(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path / "a.whl", _MEMBERS, zipfile.ZIP_DEFLATED)
    sdist = _sdist(tmp_path / "a.tar.gz", _MEMBERS, mtime=1)

    table = render_archive_table([wheel, sdist])

    for path in (wheel, sdist):
        row = next(line for line in table.splitlines() if f"`{path.name}`" in line)
        assert f"`{content_digest(path)}`" in row
        assert len(_SHA256.findall(row)) == 2  # archive sha256 and content digest


def test_main_archive_prints_the_table_without_building(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wheel = _wheel(tmp_path / "a.whl", _MEMBERS, zipfile.ZIP_DEFLATED)

    assert main(["--archive", str(wheel)]) == 0

    out = capsys.readouterr().out
    assert content_digest(wheel) in out
    assert "forge-template version" not in out  # not the candidate table


def test_main_archive_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--archive", str(tmp_path / "nope.whl")])

    assert raised.value.code == 2


def test_content_digest_reads_an_sdist_and_ignores_its_metadata(tmp_path: Path) -> None:
    one = _sdist(tmp_path / "a.tar.gz", _MEMBERS, mtime=1)
    two = _sdist(tmp_path / "b.tar.gz", _MEMBERS, mtime=999)
    edited = _sdist(
        tmp_path / "c.tar.gz", {**_MEMBERS, "pkg/mod.py": b"y = 3\n"}, mtime=1
    )

    assert content_digest(one) == content_digest(two)
    assert content_digest(one) != content_digest(edited)
    assert _SHA256.fullmatch(content_digest(one))
