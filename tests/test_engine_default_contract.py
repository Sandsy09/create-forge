"""Guards for the engine-default CLI contract (CF-16.01, ADR 0040).

`docs/engine-default-cli.md` is a *decision*; CF-18.01 has implemented most of
it (the default `new` route, `--legacy`, the five selection flags un-hidden,
`doctor`'s real negotiation), but not all -- `--engine-source`/`--engine-ref`
are CF-18.02's. This module keeps the document honest the same way
`forge-template`'s `tests/test_cutover_gates.py` keeps its FT-15.04 contract
honest:

- **Derived assertions** read the live, post-CF-18.01 CLI and
  `pyproject.toml`, so a claim about *today's* state that silently changes
  fails here.
- **Tripwires** assert the still-pending state deliberately, each with a
  comment naming the CF-EPIC-18 issue whose merge must flip it. When that
  child lands, these fail on purpose, forcing whoever implements it to move
  the affected rule out of `docs/engine-default-cli.md`'s "decided" voice and
  into `docs/cli-conventions.md`'s "in force" voice in the same change.

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

# The five selection flags ADR 0027 added. ADR 0040 decision 8 (CF-18.01)
# removed --engine-preview and un-hid the rest with their names unchanged.
_SELECTION_FLAGS = (
    "--archetype",
    "--capability",
    "--no-capabilities",
    "--platform",
    "--no-platforms",
    "--component-option",
)

# ADR 0040 decision 4 (CF-18.02): a new engine-source override pair, not yet
# implemented.
_PENDING_SOURCE_FLAGS = ("--engine-source", "--engine-ref")


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
# Derived assertions -- today's post-CF-18.01 state, read from the live CLI    #
# --------------------------------------------------------------------------- #


def test_engine_preview_flag_is_gone_and_selection_flags_are_visible() -> None:
    """ADR 0040 decision 8 (CF-18.01): --engine-preview is removed outright
    (no deprecation window -- it was hidden and development-only) and the
    five selection flags are visible with their names unchanged.
    """
    params = _new_params()
    assert "--engine-preview" not in params
    for flag in _SELECTION_FLAGS:
        assert flag in params, f"{flag} is no longer a `new` option"
        assert not getattr(params[flag], "hidden", False), f"{flag} is still hidden"


def test_legacy_flag_exists_and_is_visible() -> None:
    """ADR 0040 decision 2 (CF-18.01): `--legacy` is the visible opt-in that
    reaches the Copier path.
    """
    params = _new_params()
    assert "--legacy" in params
    assert not getattr(params["--legacy"], "hidden", False)


def test_copier_only_flags_are_present_and_visible() -> None:
    """ADR 0040 decisions 3 and 6: --template/--template-url/--ref are
    retained (superseding ADR 0011's removal), scoped to `--legacy` at
    runtime rather than by Click-level visibility.
    """
    params = _new_params()
    for flag in ("--template", "--template-url", "--ref"):
        assert flag in params, f"{flag} disappeared from `new`"
        assert not getattr(params[flag], "hidden", False), f"{flag} became hidden"


def test_engine_is_a_required_dependency_and_copier_is_the_legacy_extra() -> None:
    """ADR 0040 decisions 1/2 (CF-18.01): `forge-template` moved into
    `[project.dependencies]`; `copier` moved into the optional `legacy` extra.
    """
    project = _pyproject()["project"]
    required = " ".join(project["dependencies"])
    assert "forge-template" in required
    assert "copier" not in required
    extras = project["optional-dependencies"]
    assert any(dep.startswith("copier") for dep in extras.get("legacy", []))


def test_integration_line_is_engine_flavoured() -> None:
    """ADR 0040 decision 6/13 (CF-18.01): `integration.line` takes the
    `v<major>.<minor>.x-engine` form once the engine is the default path.
    """
    assert re.fullmatch(r"v\d+\.\d+\.x-engine", INTEGRATION_LINE), INTEGRATION_LINE


def test_doctor_negotiates_the_real_engine() -> None:
    """ADR 0040 decision 6 (CF-18.01): `doctor` calls `get_engine_info()` and
    populates `projectspec_protocol.detected` for real, against the installed
    engine, rather than leaving it hardcoded to `None`.
    """
    result = CliRunner().invoke(app, ["doctor", "--json"])
    assert result.exit_code in (0, 1), result.output
    payload = json.loads(result.output)
    assert payload["integration"]["projectspec_protocol"]["detected"] is not None


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
# Tripwires -- fail deliberately when the still-pending children land          #
# --------------------------------------------------------------------------- #


def test_tripwire_new_has_no_engine_source_override_flags() -> None:
    """Flips when CF-18.02 (#159) adds --engine-source/--engine-ref (ADR 0040
    decision 4).
    """
    params = _new_params()
    for flag in _PENDING_SOURCE_FLAGS:
        assert flag not in params, (
            f"{flag} now exists -- move its rule from docs/engine-default-cli.md "
            "into docs/cli-conventions.md and update this tripwire"
        )
