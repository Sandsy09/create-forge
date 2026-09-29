"""Installed-candidate evidence for CF-25.03 (#203): "Built wheel, plain
installation, legacy extra and isolated engine-source commands work with
the new package layout" -- the acceptance criterion CF-25.02's `commands/`
extraction left unproven end to end. Before this module:

- No installed suite imported `create_forge.commands.*` at all, so nothing
  proved the subpackage actually ships and imports under a real, non-editable
  install (`scripts/check_wheel.py` checks membership, not importability).
- No plain (no-`legacy`-extra) install ran `--version`, `list`, or `config
  init`/`show` -- only `new`/`doctor` (`tests/test_e2e_installed_rollout.py`,
  `tests/test_e2e_installed_cutover.py`).
- No `--engine-source` run that CI actually executes had ever *succeeded*:
  `tests/test_engine_source.py`'s one real run needs a sibling checkout, so
  it is always skipped in CI; `tests/test_e2e_installed_encoding.py`'s and
  `tests/test_e2e_installed_cutover.py`'s installed runs are both
  failure-path only.

Reuses `tests/conftest.py`'s session `candidate_wheel`/`e2e_child_env` and
`tests/installed_client.py`'s `build_client`, the same harness every other
installed suite shares.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.installed_client import (
    ENGINE_VERSION,
    InstalledClient,
    assert_success,
    build_client,
    run,
)
from tests.process import run_text

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def plain_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel installed with no extra at all -- `copier` absent.

    Mirrors `tests/test_e2e_installed_cutover.py`'s `no_legacy_client`: the
    reviewed engine is still pinned, so this differs from the shared
    `installed_client` fixture in exactly one respect (no `[legacy]`).
    """
    with build_client(
        candidate_wheel, e2e_child_env, engine=f"forge-template=={ENGINE_VERSION}"
    ) as client:
        yield client


@pytest.fixture(scope="session")
def _forge_template_reachable() -> None:
    """Skip, not fail, a test needing GitHub when it is unreachable -- the
    same contract `tests/test_e2e_installed_cutover.py` keeps.
    """
    try:
        run_text(
            [
                "git",
                "ls-remote",
                "--tags",
                "--refs",
                "https://github.com/Sandsy09/forge-template",
            ],
            check=True,
            timeout=30,
        )
    except Exception as exc:
        pytest.skip(f"github.com is not reachable: {exc}")


_IMPORT_AND_MODULE_SCOPE_PROBE = textwrap.dedent(
    """
    import importlib
    import json
    import pkgutil
    import sys

    import create_forge.cli
    import create_forge.commands

    for info in pkgutil.iter_modules(create_forge.commands.__path__):
        importlib.import_module(f"create_forge.commands.{info.name}")

    try:
        importlib.import_module("copier")
        copier_importable = True
    except ImportError:
        copier_importable = False

    print(json.dumps({
        "copier_importable": copier_importable,
        "copier_in_sys_modules": "copier" in sys.modules,
        "runner_in_sys_modules": "create_forge.runner" in sys.modules,
        "forge_template_in_sys_modules": "forge_template" in sys.modules,
    }))
    """
).strip()


def test_plain_install_imports_cli_and_every_command_with_no_copier(
    plain_client: InstalledClient,
) -> None:
    """`create_forge.cli` and every real `create_forge.commands.*` submodule
    (discovered from the installed package itself, not a list hard-coded
    here -- the same "don't silently stop covering a moved module" reasoning
    `tests/source_tree.py` documents) import cleanly with `copier` absent,
    and none of `copier`/`create_forge.runner`/`forge_template` was pulled
    into `sys.modules` as a side effect -- the ADR 0014/0060 lazy-import rule
    `tests/test_command_layout.py` proves against the source, proven here
    against the real installed wheel.
    """
    result = run(
        [str(plain_client.python), "-c", _IMPORT_AND_MODULE_SCOPE_PROBE],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(result, "plain-install command-module import probe")
    payload = json.loads(result.stdout)
    assert payload == {
        "copier_importable": False,
        "copier_in_sys_modules": False,
        "runner_in_sys_modules": False,
        "forge_template_in_sys_modules": False,
    }


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["new", "--help"],
        ["list", "--help"],
        ["update", "--help"],
        ["doctor", "--help"],
        ["config", "--help"],
        ["config", "init", "--help"],
        ["config", "show", "--help"],
    ],
    ids=" ".join,
)
def test_plain_install_every_command_help_exits_zero(
    plain_client: InstalledClient, args: list[str]
) -> None:
    result = run(
        [str(plain_client.console), *args], plain_client.root, env=plain_client.env
    )
    assert_success(result, f"installed create-forge {' '.join(args)}")


def test_plain_install_version_matches_the_wheel(
    plain_client: InstalledClient,
) -> None:
    result = run(
        [str(plain_client.console), "--version"],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(result, "installed create-forge --version")
    assert plain_client.wheel.name.startswith(f"create_forge-{result.stdout.strip()}-")


def test_plain_install_list_shows_the_discovered_catalogue(
    plain_client: InstalledClient,
) -> None:
    result = run(
        [str(plain_client.console), "list"], plain_client.root, env=plain_client.env
    )
    assert_success(result, "installed create-forge list")
    assert "library" in result.stdout
    assert "archetype" in result.stdout


def test_plain_install_list_legacy_works_without_copier(
    plain_client: InstalledClient,
) -> None:
    """`list --legacy` reads only the bundled registry (`templates.toml`),
    never `copier` -- unlike `new --legacy`/`update`'s file-routed Copier
    path, it does not gate on `_ensure_legacy_available`. Worth proving
    explicitly: the obvious guess is that every `--legacy` surface needs the
    extra, and that guess is wrong for this one command.
    """
    result = run(
        [str(plain_client.console), "list", "--legacy"],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(result, "installed create-forge list --legacy")
    assert "library" in result.stdout


def test_plain_install_new_legacy_exits_3_naming_the_remedy(
    plain_client: InstalledClient, tmp_path: Path
) -> None:
    dest = tmp_path / "rejected"
    result = run(
        [
            str(plain_client.console),
            "new",
            "--legacy",
            "Example",
            "--yes",
            "--path",
            str(dest),
        ],
        plain_client.root,
        env=plain_client.env,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "create-forge[legacy]" in result.stdout + result.stderr
    assert not dest.exists()


def test_plain_install_doctor_json_succeeds(plain_client: InstalledClient) -> None:
    result = run(
        [str(plain_client.console), "doctor", "--json"],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(result, "installed create-forge doctor --json")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_plain_install_config_init_then_show(
    plain_client: InstalledClient, tmp_path: Path
) -> None:
    """`InstalledClient.env`'s own `XDG_CONFIG_HOME` isolation (`tests/
    installed_client.py::installed_child_env`) is what makes this safe to
    run against the shared session-scoped client: each test gets a config
    root under that client's own throwaway directory, not a real user's.
    """
    init_result = run(
        [str(plain_client.console), "config", "init"],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(init_result, "installed create-forge config init")

    show_result = run(
        [str(plain_client.console), "config", "show"],
        plain_client.root,
        env=plain_client.env,
    )
    assert_success(show_result, "installed create-forge config show")


def test_engine_source_success_reaches_a_real_installed_console(
    plain_client: InstalledClient, _forge_template_reachable: None, tmp_path: Path
) -> None:
    """The first `--engine-source` run CI actually executes to a *successful*
    finish: existing installed coverage
    (`tests/test_e2e_installed_encoding.py`,
    `tests/test_e2e_installed_cutover.py::
    test_boundary_incompatible_engine_via_engine_source_writes_nothing`) is
    failure-path only, and `tests/test_engine_source.py`'s own real
    provisioning run needs a sibling `../forge-template` checkout, so it is
    always skipped in CI. This pins a real, reviewed release
    (`v{ENGINE_VERSION}`) instead, so it succeeds wherever GitHub is
    reachable.
    """
    dest = tmp_path / "engine-source-success"
    result = run(
        [
            str(plain_client.console),
            "new",
            "Engine Source Trial",
            "--engine-source",
            "https://github.com/Sandsy09/forge-template",
            "--engine-ref",
            f"v{ENGINE_VERSION}",
            "--archetype",
            "library",
            "--no-capabilities",
            "--no-platforms",
            "--yes",
            "--path",
            str(dest),
            "--data",
            "license=mit",
            "--data",
            "author_name=Test User",
            "--data",
            "author_email=test@example.invalid",
            "--data",
            "python_min_version=3.11",
            "--data",
            "python_version=3.13",
        ],
        plain_client.root,
        env=plain_client.env,
        timeout=600,
    )
    assert_success(result, "installed create-forge new --engine-source")
    assert (dest / "pyproject.toml").is_file()
    assert (dest / "uv.lock").is_file()
    # --engine-source never records generation metadata (ADR 0044) -- proven
    # at the fast-suite level by tests/test_engine_source.py's own
    # `-k metadata` group; proven here against a real provisioned run too.
    assert not (dest / ".forge").exists()
