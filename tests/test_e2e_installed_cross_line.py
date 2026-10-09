"""Released client versus candidate: the existing archetypes are unchanged
across the `0.6` to `0.7` provider line (CF-29.02, ADR 0062).

forge-template's pairing tier compared the candidate engine with the published
`0.6.0` for the `0.6` line. For `0.7.0` it cannot, because the released client
(`create-forge 0.5.0`, which declares `forge-template>=0.6,<0.7`) refuses the
newer engine. The FT-28.03 hand-off therefore left the comparison to the
client: generate the same projects through the **published** `create-forge
0.5.0` on its own `0.6` engine and through the **candidate** on `0.7.0`, and
show that nothing the existing archetypes render has changed.

Compared byte for byte: every generated file *except*

- `uv.lock`, which is the resolver's output at the moment of generation rather
  than anything either client renders; and
- `.forge/generation.json`, which records the provider version by design, so it
  is compared after normalising exactly that one field. Everything else it
  records -- the spec, the component identities and versions, the protocols and
  every output digest -- must agree.

Two positive controls keep the comparison honest: the released client really
does run on a `0.6` engine and really does not know `batch`. That second fact is
also the other half of the compatibility boundary: a client pinned to the
previous line keeps exactly the catalogue it was tested against.

Needs PyPI at test time for `create-forge==0.5.0`, as the rest of the e2e tier
already needs it for the engine.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.installed_client import (
    DEFAULT_PYTHON,
    InstalledClient,
    assert_success,
    file_bytes,
    installed_child_env,
    run,
    venv_python,
    venv_script,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

pytestmark = pytest.mark.e2e

_RELEASED_CLIENT = "create-forge==0.5.0"
_RELEASED_ENGINE_PREFIX = "0.6."
_NOT_COMPARED = {"uv.lock", ".forge/generation.json"}

_ANSWERS = {
    "project_description": "Released-client comparison.",
    "license": "mit",
    "author_name": "create-forge cross-line",
    "author_email": "create-forge-cross-line@example.invalid",
    "python_min_version": "3.11",
    "python_version": DEFAULT_PYTHON,
}


@dataclass(frozen=True, slots=True)
class Existing:
    """One archetype that exists on both sides of the line, and the smallest
    selection that generates it (Data Science requires `jupyter`)."""

    archetype: str
    capabilities: tuple[str, ...] = ()


_EXISTING = (
    Existing("library"),
    Existing("cli"),
    Existing("data-science", ("jupyter",)),
    Existing("streamlit"),
)


@dataclass(frozen=True, slots=True)
class Released:
    """The published client: just what the comparison needs of it."""

    console: Path
    env: Mapping[str, str]
    root: Path


@pytest.fixture(scope="module")
def released_client(e2e_child_env: dict[str, str]) -> Iterator[Released]:
    """`create-forge==0.5.0` from PyPI in a fresh environment, resolving its own
    declared `forge-template` line -- nothing pinned, nothing forced."""
    with tempfile.TemporaryDirectory(prefix="create-forge-released-client-") as tmp:
        root = Path(tmp)
        venv = root / "released-venv"
        created = run(
            ["uv", "venv", "--python", DEFAULT_PYTHON, str(venv)],
            root,
            env=e2e_child_env,
        )
        assert_success(created, "released-client virtual environment")
        installed = run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_python(venv)),
                _RELEASED_CLIENT,
                "uv",
            ],
            root,
            env=e2e_child_env,
        )
        assert_success(installed, f"installing the published {_RELEASED_CLIENT}")
        yield Released(
            console=venv_script(venv, "create-forge"),
            env=installed_child_env(e2e_child_env, venv, root / "config"),
            root=root,
        )


def _new_args(console: Path, case: Existing, dest: Path) -> list[str]:
    args = [
        str(console),
        "new",
        f"Cross Line {case.archetype}",
        "--archetype",
        case.archetype,
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in _ANSWERS.items():
        args += ["--data", f"{key}={value}"]
    for capability in case.capabilities:
        args += ["--capability", capability]
    return args


def _normalised_metadata(files: Mapping[str, bytes]) -> dict[str, Any]:
    """The committed generation metadata with the provider version -- the one
    field that is *supposed* to differ across the line -- replaced."""
    document: dict[str, Any] = json.loads(files[".forge/generation.json"])
    assert document["provider"]["distribution"] == "forge-template"
    document["provider"]["version"] = "<normalised>"
    return document


# --------------------------------------------------------------------------
# positive controls
# --------------------------------------------------------------------------


def test_the_released_client_runs_on_the_previous_provider_line(
    released_client: Released,
) -> None:
    """Without this the comparison could be two runs of the same engine."""
    result = run(
        [str(released_client.console), "doctor", "--json"],
        released_client.root,
        env=released_client.env,
    )
    integration = json.loads(result.stdout)["integration"]

    assert integration["engine_package"].startswith(_RELEASED_ENGINE_PREFIX)
    assert integration["engine_range"] == "forge-template>=0.6,<0.7"


def test_the_released_client_does_not_know_batch(
    released_client: Released, tmp_path: Path
) -> None:
    """A client pinned to the previous line keeps exactly the catalogue it was
    tested against: `batch` is an unknown archetype to it, and nothing is
    written. This is the other half of the compatibility boundary ADR 0061 draws.
    """
    listing = run(
        [str(released_client.console), "list"],
        released_client.root,
        env=released_client.env,
    )
    assert_success(listing, "released client list")
    rows = [line.split() for line in listing.stdout.splitlines()]
    assert not any(row[:2] == ["batch", "archetype"] for row in rows)

    destination = tmp_path / "proj"
    result = run(
        [
            str(released_client.console),
            "new",
            "No Batch Here",
            "--archetype",
            "batch",
            "--yes",
            "--path",
            str(destination),
            "--data",
            "license=mit",
        ],
        tmp_path,
        env=released_client.env,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Unknown archetype" in " ".join((result.stdout + result.stderr).split())
    assert not destination.exists()


# --------------------------------------------------------------------------
# the comparison
# --------------------------------------------------------------------------


@pytest.mark.parametrize("case", _EXISTING, ids=lambda item: item.archetype)
def test_existing_archetype_output_is_unchanged_across_the_provider_line(
    installed_client: InstalledClient, released_client: Released, case: Existing
) -> None:
    """The same answers through the published client (on its `0.6` engine) and
    the candidate (on `0.7.0`) render byte-identical projects, apart from the
    resolver's lock and the provider version the metadata records.
    """
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-cross-line-{case.archetype}-"
    ) as tmp:
        root = Path(tmp)
        released_dest = root / "released" / "project"
        candidate_dest = root / "candidate" / "project"
        released_dest.parent.mkdir()
        candidate_dest.parent.mkdir()

        assert_success(
            run(
                _new_args(released_client.console, case, released_dest),
                released_dest.parent,
                env=released_client.env,
            ),
            f"published create-forge 0.5.0: {case.archetype}",
        )
        assert_success(
            run(
                _new_args(installed_client.console, case, candidate_dest),
                candidate_dest.parent,
                env=installed_client.env,
            ),
            f"candidate create-forge: {case.archetype}",
        )

        released = file_bytes(released_dest)
        candidate = file_bytes(candidate_dest)

        assert set(released) == set(candidate), sorted(set(released) ^ set(candidate))
        differing = sorted(
            path
            for path in released
            if path not in _NOT_COMPARED and released[path] != candidate[path]
        )
        assert differing == [], differing
        assert _normalised_metadata(released) == _normalised_metadata(candidate)

        # The version field really does differ, so the normalisation above is
        # hiding something real rather than nothing.
        released_provider = json.loads(released[".forge/generation.json"])["provider"]
        candidate_provider = json.loads(candidate[".forge/generation.json"])["provider"]
        assert released_provider["version"].startswith(_RELEASED_ENGINE_PREFIX)
        assert candidate_provider["version"] == installed_client.engine
