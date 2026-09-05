"""Installed-client Data Science end-to-end validation (CF-14.02).

Builds the create-forge 0.3.0 candidate wheel, installs that wheel with its
``engine`` extra and the reviewed PyPI ``forge-template 0.4.1`` release into a
clean virtual environment, then drives the real installed ``create-forge``
console script. Both accepted Data Science compositions are generated twice,
byte-compared including their client-finalised locks, restored, checked,
built, installed, and audited without importing either working tree.

The full Scientific Python composition is also checked at the supported
Python window edges. Every workspace is context-managed so candidate builds,
virtual environments, generated projects, and build artefacts are removed
after success, assertion failure, subprocess failure, or timeout. See ADR
0032 and ``docs/installed-data-science-validation.md``.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from tests.installed_client import CLIENT_VERSION as _CLIENT_VERSION
from tests.installed_client import DEFAULT_PYTHON as _DEFAULT_PYTHON
from tests.installed_client import ENGINE_VERSION as _ENGINE_VERSION
from tests.installed_client import FORGE_DISTRIBUTIONS as _FORGE_DISTRIBUTIONS
from tests.installed_client import (
    InstalledClient,
    assert_output_matches_owned_plan,
)
from tests.installed_client import assert_success as _assert_success
from tests.installed_client import file_bytes as _file_bytes
from tests.installed_client import run as _run
from tests.installed_client import venv_python as _venv_python

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parent.parent

_PYTHON_WINDOW_EDGES = ("3.11", "3.14")
_IGNORED_WORKING_TREES = (
    "data/raw",
    "data/interim",
    "data/processed",
    "models",
    "artifacts",
)
_WORKING_TREE_MARKER = b"IGNORED-WORKING-TREE-PAYLOAD-DO-NOT-PACKAGE"


@dataclass(frozen=True, slots=True)
class Composition:
    """One accepted Data Science component selection and its derived names."""

    slug: str
    project_name: str
    package_name: str
    repository_name: str
    capabilities: tuple[str, ...]


_COMPOSITIONS = (
    Composition(
        slug="jupyter",
        project_name="Installed Data Science Jupyter",
        package_name="installed_data_science_jupyter",
        repository_name="installed-data-science-jupyter",
        capabilities=("jupyter",),
    ),
    Composition(
        slug="jupyter-scientific-python",
        project_name="Installed Data Science Scientific Python",
        package_name="installed_data_science_scientific_python",
        repository_name="installed-data-science-scientific-python",
        capabilities=("jupyter", "scientific-python"),
    ),
)
_FULL_COMPOSITION = _COMPOSITIONS[1]


_CLIENT_METADATA_PROBE = """
import json
from importlib.metadata import distribution, version

client = distribution("create-forge")
engine = distribution("forge-template")
print(json.dumps({
    "client_version": version("create-forge"),
    "engine_version": version("forge-template"),
    "uv_version": version("uv"),
    "client_direct_url": json.loads(client.read_text("direct_url.json")),
    "engine_direct_url": engine.read_text("direct_url.json"),
    "client_requirements": client.requires,
}))
"""


def _engine_extra_requirement(
    raw_requirements: Sequence[str], name: str
) -> Requirement:
    matches = []
    for raw in raw_requirements:
        requirement = Requirement(raw)
        if canonicalize_name(requirement.name) != canonicalize_name(name):
            continue
        if requirement.marker is None or not requirement.marker.evaluate(
            {"extra": "engine"}
        ):
            continue
        matches.append(requirement)
    assert len(matches) == 1, matches
    return matches[0]


def test_candidate_wheel_installs_the_reviewed_pair(
    installed_client: InstalledClient,
) -> None:
    """The real candidate wheel, its extra metadata, and PyPI engine agree."""
    version = _run(
        [str(installed_client.console), "--version"],
        installed_client.root,
        env=installed_client.env,
    )
    _assert_success(version, "installed create-forge --version")
    assert version.stdout.strip() == _CLIENT_VERSION

    probed = _run(
        [str(installed_client.python), "-c", _CLIENT_METADATA_PROBE],
        installed_client.root,
        env=installed_client.env,
    )
    _assert_success(probed, "installed client metadata probe")
    payload: dict[str, Any] = json.loads(probed.stdout)

    assert payload["client_version"] == _CLIENT_VERSION
    assert payload["engine_version"] == _ENGINE_VERSION
    assert installed_client.wheel.name in payload["client_direct_url"]["url"]
    # PEP 610 metadata exists only for direct/path/VCS installs. Its absence
    # proves the reviewed engine was resolved from the package index.
    assert payload["engine_direct_url"] is None

    requirements: list[str] = payload["client_requirements"]
    engine = _engine_extra_requirement(requirements, "forge-template")
    uv = _engine_extra_requirement(requirements, "uv")
    assert {str(specifier) for specifier in engine.specifier} == {">=0.4.1", "<0.5"}
    assert {str(specifier) for specifier in uv.specifier} == {">=0.12", "<0.13"}
    assert str(engine.marker) == 'extra == "engine"'
    assert str(uv.marker) == 'extra == "engine"'
    assert Version(payload["uv_version"]) in uv.specifier

    path_probe = _run(
        [
            str(installed_client.python),
            "-c",
            "import shutil; print(shutil.which('uv'))",
        ],
        installed_client.root,
        env=installed_client.env,
    )
    _assert_success(path_probe, "candidate uv PATH probe")
    assert Path(path_probe.stdout.strip()).resolve() == installed_client.uv.resolve()


def _answers(composition: Composition, endpoint: str) -> dict[str, str]:
    return {
        "project_name": composition.project_name,
        "project_description": "Installed Data Science end-to-end validation.",
        "license": "mit",
        "author_name": "create-forge installed e2e",
        "author_email": "create-forge-installed-e2e@example.invalid",
        "python_min_version": "3.11",
        "python_version": endpoint,
    }


def _generate(
    client: InstalledClient,
    composition: Composition,
    destination: Path,
    *,
    endpoint: str = _DEFAULT_PYTHON,
) -> subprocess.CompletedProcess[str]:
    answers = _answers(composition, endpoint)
    args = [
        str(client.console),
        "new",
        composition.project_name,
        "--engine-preview",
        "--archetype",
        "data-science",
        "--yes",
        "--path",
        str(destination),
    ]
    for key, value in answers.items():
        if key != "project_name":
            args += ["--data", f"{key}={value}"]
    for capability in composition.capabilities:
        args += ["--capability", capability]
    return _run(args, destination.parent, env=client.env)


def _assert_initial_project_shape(project: Path, composition: Composition) -> None:
    assert project.is_dir()
    assert (project / "pyproject.toml").is_file()
    assert (project / "uv.lock").is_file()
    assert (project / f"src/{composition.package_name}/__init__.py").is_file()
    assert (project / f"src/{composition.package_name}/py.typed").is_file()
    assert (project / "notebooks/getting-started.ipynb").is_file()
    assert (project / "tests").is_dir()
    assert not (project / ".git").exists()
    assert not (project / ".venv").exists()
    assert list(project.parent.glob(".create-forge-*")) == []


def _assert_output_matches_owned_plan(
    client: InstalledClient,
    project: Path,
    composition: Composition,
    endpoint: str,
) -> None:
    assert_output_matches_owned_plan(
        client,
        project,
        archetype="data-science",
        capabilities=composition.capabilities,
        answers=_answers(composition, endpoint),
    )


def _assert_lock_is_current(client: InstalledClient, project: Path) -> None:
    result = _run([str(client.uv), "lock", "--check"], project, env=client.env)
    _assert_success(result, f"{project.name} uv lock --check")


def _assert_no_forge_dependencies(project: Path) -> None:
    pyproject: dict[str, Any] = tomllib.loads(
        (project / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements: list[str] = []
    requirements.extend(pyproject.get("build-system", {}).get("requires", []))
    requirements.extend(pyproject.get("project", {}).get("dependencies", []))
    for extra in pyproject.get("project", {}).get("optional-dependencies", {}).values():
        requirements.extend(item for item in extra if isinstance(item, str))
    for group in pyproject.get("dependency-groups", {}).values():
        requirements.extend(item for item in group if isinstance(item, str))

    declared = {
        canonicalize_name(Requirement(requirement).name) for requirement in requirements
    }
    locked = {
        canonicalize_name(package["name"])
        for package in tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))[
            "package"
        ]
    }
    assert declared.isdisjoint(_FORGE_DISTRIBUTIONS)
    assert locked.isdisjoint(_FORGE_DISTRIBUTIONS)


def _restore_and_check(
    client: InstalledClient, project: Path, *, scientific: bool
) -> None:
    commands = [
        ("locked restoration", [str(client.uv), "sync", "--all-groups", "--locked"]),
        (
            "canonical project check",
            [str(client.uv), "run", "--locked", "poe", "check"],
        ),
        (
            "notebook execution",
            [str(client.uv), "run", "--locked", "poe", "notebook:check"],
        ),
    ]
    if scientific:
        commands.append(
            (
                "Scientific Python smoke test",
                [
                    str(client.uv),
                    "run",
                    "--locked",
                    "pytest",
                    "tests/test_scientific_python.py",
                ],
            )
        )
    for description, command in commands:
        _assert_success(
            _run(command, project, env=client.env),
            f"{project.name} {description}",
        )


def _plant_ignored_working_trees(project: Path) -> None:
    for tree in _IGNORED_WORKING_TREES:
        planted = project / tree / "planted.bin"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_bytes(_WORKING_TREE_MARKER)


def _build_generated_distributions(
    client: InstalledClient, project: Path, composition: Composition
) -> tuple[Path, Path]:
    _plant_ignored_working_trees(project)
    build = _run([str(client.uv), "build"], project, env=client.env)
    _assert_success(build, f"{project.name} wheel and sdist build")

    wheels = sorted((project / "dist").glob("*.whl"))
    sdists = sorted((project / "dist").glob("*.tar.gz"))
    assert len(wheels) == 1, wheels
    assert len(sdists) == 1, sdists
    assert wheels[0].name.startswith(f"{composition.package_name}-0.1.0-")
    assert sdists[0].name.startswith(f"{composition.package_name}-0.1.0")
    return wheels[0], sdists[0]


def _assert_ignored_trees_absent_from_archives(wheel: Path, sdist: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        wheel_blob = b"".join(archive.read(name) for name in wheel_names)

    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
        sdist_parts: list[bytes] = []
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            assert extracted is not None
            sdist_parts.append(extracted.read())
        sdist_blob = b"".join(sdist_parts)

    for name in (*wheel_names, *sdist_names):
        stripped = name.split("/", 1)[-1] if "/" in name else name
        for tree in _IGNORED_WORKING_TREES:
            assert stripped != tree
            assert not stripped.startswith(f"{tree}/"), name
        assert "planted.bin" not in name, name
    assert _WORKING_TREE_MARKER not in wheel_blob
    assert _WORKING_TREE_MARKER not in sdist_blob


def _assert_generated_wheel_installs_without_forge(
    client: InstalledClient,
    wheel: Path,
    composition: Composition,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-generated-install-{composition.slug}-"
    ) as tmp:
        root = Path(tmp)
        venv = root / "venv"
        created = _run(
            [str(client.uv), "venv", "--python", _DEFAULT_PYTHON, str(venv)],
            root,
            env=client.env,
        )
        _assert_success(created, f"{composition.slug} install venv creation")

        python = _venv_python(venv)
        installed = _run(
            [str(client.uv), "pip", "install", "--python", str(python), str(wheel)],
            root,
            env=client.env,
        )
        _assert_success(installed, f"{composition.slug} generated wheel installation")

        probe = f"""
import importlib.util
import json
from importlib.metadata import distributions, metadata
from pathlib import Path
import {composition.package_name} as package

module_spec = importlib.util.find_spec({composition.package_name!r})
assert module_spec is not None
root = module_spec.submodule_search_locations[0]
names = [dist.metadata["Name"] for dist in distributions()]
print(json.dumps({{
    "version": package.__version__,
    "requires_python": metadata({composition.repository_name!r})["Requires-Python"],
    "typed": (Path(root) / "py.typed").is_file(),
    "distributions": names,
    "forge_template_importable": importlib.util.find_spec("forge_template") is not None,
    "create_forge_importable": importlib.util.find_spec("create_forge") is not None,
}}))
"""
        inspected = _run([str(python), "-c", probe], root, env=client.env)
        _assert_success(inspected, f"{composition.slug} installed package probe")
        payload: dict[str, Any] = json.loads(inspected.stdout)

        assert payload["version"] == "0.1.0"
        assert payload["requires_python"] == ">=3.11"
        assert payload["typed"] is True
        installed_names = {
            canonicalize_name(name) for name in payload["distributions"] if name
        }
        assert installed_names.isdisjoint(_FORGE_DISTRIBUTIONS)
        assert payload["forge_template_importable"] is False
        assert payload["create_forge_importable"] is False


@pytest.mark.parametrize("composition", _COMPOSITIONS, ids=lambda item: item.slug)
def test_installed_console_validates_data_science_composition(
    installed_client: InstalledClient, composition: Composition
) -> None:
    """Both accepted compositions pass every installed-client audit."""
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-data-science-{composition.slug}-"
    ) as tmp:
        root = Path(tmp)
        first = root / "first"
        repeated = root / "repeated"

        first_result = _generate(installed_client, composition, first)
        _assert_success(first_result, f"first {composition.slug} generation")
        repeated_result = _generate(installed_client, composition, repeated)
        _assert_success(repeated_result, f"repeated {composition.slug} generation")

        _assert_initial_project_shape(first, composition)
        _assert_initial_project_shape(repeated, composition)
        _assert_lock_is_current(installed_client, first)
        _assert_lock_is_current(installed_client, repeated)
        assert _file_bytes(first) == _file_bytes(repeated)
        _assert_output_matches_owned_plan(
            installed_client, first, composition, _DEFAULT_PYTHON
        )
        _assert_no_forge_dependencies(first)

        scientific = "scientific-python" in composition.capabilities
        _restore_and_check(installed_client, first, scientific=scientific)
        wheel, sdist = _build_generated_distributions(
            installed_client, first, composition
        )
        _assert_ignored_trees_absent_from_archives(wheel, sdist)
        _assert_generated_wheel_installs_without_forge(
            installed_client, wheel, composition
        )


@pytest.mark.parametrize("endpoint", _PYTHON_WINDOW_EDGES)
def test_full_data_science_composition_passes_python_window_edge(
    installed_client: InstalledClient, endpoint: str
) -> None:
    """The full composition passes its own checks at Python 3.11 and 3.14."""
    with tempfile.TemporaryDirectory(
        prefix=f"create-forge-data-science-full-py{endpoint.replace('.', '')}-"
    ) as tmp:
        project = Path(tmp) / "project"
        result = _generate(
            installed_client,
            _FULL_COMPOSITION,
            project,
            endpoint=endpoint,
        )
        _assert_success(result, f"full Data Science generation at Python {endpoint}")
        _assert_initial_project_shape(project, _FULL_COMPOSITION)
        _assert_lock_is_current(installed_client, project)
        _assert_output_matches_owned_plan(
            installed_client, project, _FULL_COMPOSITION, endpoint
        )
        _assert_no_forge_dependencies(project)
        _restore_and_check(installed_client, project, scientific=True)
