"""Guards for the engine-default CLI contract (CF-16.01, ADR 0040).

`docs/engine-default-cli.md` is a *decision*, not a shipped interface: it
describes the `create-forge` command surface after the engine-default cutover,
which no release has performed. This module keeps that document honest the same
way `forge-template`'s `tests/test_cutover_gates.py` keeps its FT-15.04
contract honest:

- **Derived assertions** read the live pre-cutover CLI and `pyproject.toml`, so
  a claim about *today's* state that silently changes fails here.
- **Tripwires** assert the pre-cutover state deliberately, each with a comment
  naming the CF-EPIC-18 issue whose merge must flip it. When the cutover lands,
  these fail on purpose, forcing whoever implements it to move the affected
  rule out of `docs/engine-default-cli.md`'s "decided" voice and into
  `docs/cli-conventions.md`'s "in force" voice in the same change.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import typer.main
from typer.testing import CliRunner

from create_forge.cli import app
from create_forge.compat import INTEGRATION_LINE

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
ADR_0040 = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0040-engine-default-selection-and-source-resolution.md"
)
ENGINE_DEFAULT_CLI = REPO_ROOT / "docs" / "engine-default-cli.md"
CLI_CONVENTIONS = REPO_ROOT / "docs" / "cli-conventions.md"

# The five selection flags ADR 0027 added, plus --engine-preview itself. ADR
# 0040 decision 8: --engine-preview is removed at the cutover and the rest
# become visible with their names unchanged.
_PREVIEW_FLAGS = (
    "--engine-preview",
    "--archetype",
    "--capability",
    "--no-capabilities",
    "--platform",
    "--no-platforms",
    "--component-option",
)

# ADR 0040 decisions 2 and 3: these are added at the cutover -- a route flag
# and a new engine-package override. None exists on `new` today.
_CUTOVER_FLAGS = ("--legacy", "--engine-source", "--engine-ref")


def _pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _new_params() -> dict[str, object]:
    """Every click parameter on `create-forge new`, keyed by its long option."""
    command = typer.main.get_command(app)
    new = command.commands["new"]  # type: ignore[attr-defined]
    params: dict[str, object] = {}
    for param in new.params:
        for opt in param.opts:
            params[opt] = param
    return params


# --------------------------------------------------------------------------- #
# Derived assertions -- today's state, read from the live CLI                  #
# --------------------------------------------------------------------------- #


def test_preview_flags_are_hidden_and_named_as_the_contract_expects() -> None:
    """ADR 0040 decision 8 removes --engine-preview and un-hides the other
    five with names unchanged. That is only meaningful if they are hidden and
    present now -- this reads the live command, so a rename or an un-hide that
    lands without updating the contract fails here.
    """
    params = _new_params()
    for flag in _PREVIEW_FLAGS:
        assert flag in params, f"{flag} is no longer a `new` option"
        assert getattr(params[flag], "hidden", False), (
            f"{flag} is no longer hidden -- if the cutover un-hid it, move the "
            "rule from docs/engine-default-cli.md into docs/cli-conventions.md"
        )


def test_copier_only_flags_are_present_and_visible() -> None:
    """ADR 0040 decisions 3 and 6 retain --template-url/--ref and scope them to
    --legacy. They must still be here (superseding ADR 0011's removal) and
    visible today, where there is no --legacy to scope them to.
    """
    params = _new_params()
    for flag in ("--template", "--template-url", "--ref"):
        assert flag in params, f"{flag} disappeared from `new`"
        assert not getattr(params[flag], "hidden", False), f"{flag} became hidden"


def test_engine_is_declared_only_as_the_optional_extra() -> None:
    """Pre-cutover: forge-template is the optional `engine` extra, never a
    required dependency (ADR 0018). ADR 0040 decision 1 moves it into
    [project.dependencies] -- see the tripwire below.
    """
    project = _pyproject()["project"]
    required = " ".join(project["dependencies"])
    assert "forge-template" not in required
    extras = project["optional-dependencies"]
    assert any("forge-template" in dep for dep in extras.get("engine", []))


def test_new_contract_doc_and_adr_exist_and_are_consistent() -> None:
    assert ENGINE_DEFAULT_CLI.is_file()
    assert ADR_0040.is_file()
    doc = ENGINE_DEFAULT_CLI.read_text(encoding="utf-8")
    adr = ADR_0040.read_text(encoding="utf-8")
    # cli-conventions.md keeps the authoritative exit-status table; the new doc
    # must point at it rather than restate it.
    assert "cli-conventions.md" in doc
    assert "docs/engine-default-cli.md" in CLI_CONVENTIONS.read_text(encoding="utf-8")
    # ADR 0040 supersedes ADR 0011 on one clause only.
    assert "0011-engine-source-and-version-resolution.md" in adr


def test_adr_and_contract_name_their_exclusions_literally() -> None:
    """FT-15.04's own gate test asserts the contract names its review
    obligations verbatim; CF-16.01 owns CF-ROADMAP-01-EX-01/-02/-03.
    """
    for path in (ADR_0040, ENGINE_DEFAULT_CLI):
        text = path.read_text(encoding="utf-8")
        for obligation in (
            "CF-ROADMAP-01-EX-01",
            "CF-ROADMAP-01-EX-02",
            "CF-ROADMAP-01-EX-03",
        ):
            assert obligation in text, f"{path.name} does not name {obligation}"


# --------------------------------------------------------------------------- #
# Tripwires -- fail deliberately when the cutover lands                        #
# --------------------------------------------------------------------------- #


def test_tripwire_engine_stays_out_of_required_dependencies() -> None:
    """Flips when CF-18.01 (#158) moves forge-template into
    [project.dependencies]. Update docs/engine-default-cli.md decision 1 and
    docs/cli-conventions.md, then this test, in that change.
    """
    assert "forge-template" not in " ".join(_pyproject()["project"]["dependencies"])


def test_tripwire_copier_is_required_and_there_is_no_legacy_extra() -> None:
    """Flips when CF-18.01 (#158) moves copier into an optional `legacy` extra
    (ADR 0040 decision 2).
    """
    project = _pyproject()["project"]
    assert any(dep.startswith("copier") for dep in project["dependencies"])
    assert "legacy" not in project.get("optional-dependencies", {})


def test_tripwire_integration_line_is_still_copier_flavoured() -> None:
    """Flips when CF-18.01 (#158) switches the default path to the engine and
    `integration.line` becomes `v<major>.<minor>.x-engine` (ADR 0040
    decision 6 / 13).
    """
    assert re.fullmatch(r"v\d+\.\d+\.x-copier", INTEGRATION_LINE), INTEGRATION_LINE


def test_tripwire_new_has_no_cutover_route_or_source_flags() -> None:
    """Flips when CF-18.01 (#158) adds --legacy or CF-18.02 (#159) adds
    --engine-source/--engine-ref (ADR 0040 decisions 2 and 4).
    """
    params = _new_params()
    for flag in _CUTOVER_FLAGS:
        assert flag not in params, (
            f"{flag} now exists -- move its rule from docs/engine-default-cli.md "
            "into docs/cli-conventions.md and update this tripwire"
        )


def test_tripwire_doctor_does_not_negotiate_the_projectspec_protocol() -> None:
    """Flips when CF-18.01 (#158) makes `doctor` call get_engine_info() and
    populate `projectspec_protocol.detected` (ADR 0040 decision 6).
    """
    result = CliRunner().invoke(app, ["doctor", "--json"])
    assert result.exit_code in (0, 1), result.output
    payload = json.loads(result.output)
    assert payload["integration"]["projectspec_protocol"]["detected"] is None
