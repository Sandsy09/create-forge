"""Guards for the engine project lifecycle contract (CF-16.02, ADR 0041).

`docs/engine-project-lifecycle.md` is a *decision*, not a shipped interface:
CF-18.03 (#160) implemented the `new` half -- the engine `new` finalisation
lifecycle (git init, initial commit, conditional hooks) and the committed
`.forge/generation.json` metadata file -- but the engine-native
`create-forge update` route stays CF-18.04's (#161), not yet built.

Same discipline as `tests/test_engine_default_contract.py` and
`forge-template`'s `tests/test_cutover_gates.py`:

- **Derived assertions** read the live CLI, so a claim about *today's* state
  that silently changes fails here.
- **Tripwires** assert a not-yet-built state deliberately, each naming the
  CF-EPIC-18 issue whose merge must flip it. When it lands, the tripwire is
  replaced by a derived assertion proving the real behaviour, and the
  affected rule moves out of `docs/engine-project-lifecycle.md`'s "decided"
  voice into `docs/filesystem-generation.md` / `docs/cli-conventions.md`'s
  "in force" voice in the same change -- CF-18.03 did exactly this for its
  own two rows below; only the CF-18.04 update-dispatch tripwire remains.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.main

from create_forge import engine, runner
from create_forge.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_0041 = (
    REPO_ROOT / "docs" / "adr" / "0041-engine-project-lifecycle-and-update-dispatch.md"
)
ENGINE_PROJECT_LIFECYCLE = REPO_ROOT / "docs" / "engine-project-lifecycle.md"
SRC = REPO_ROOT / "src" / "create_forge"

METADATA_FILE = ".forge/generation.json"

# ADR 0041 decisions 1 and 10: `--legacy` routes an update to Copier;
# `--degraded` opts into the two-way update. Neither exists on `update` today.
_UPDATE_CUTOVER_FLAGS = ("--legacy", "--degraded")


def _update_params() -> dict[str, object]:
    """Every click parameter on `create-forge update`, keyed by long option."""
    command = typer.main.get_command(app)
    update = command.commands["update"]  # type: ignore[attr-defined]
    params: dict[str, object] = {}
    for param in update.params:
        for opt in param.opts:
            params[opt] = param
    return params


# --------------------------------------------------------------------------- #
# Derived assertions -- today's state, read from the live CLI                  #
# --------------------------------------------------------------------------- #


def test_update_has_only_its_pre_cutover_parameters() -> None:
    """ADR 0041 adds engine-native update routing to `update`. Today it takes
    only the project, `--ref` and `--dry-run` -- this reads the live command,
    so a new flag that lands without updating the contract fails here.
    """
    params = _update_params()
    assert set(params) >= {"--ref", "--dry-run"}
    for flag in _UPDATE_CUTOVER_FLAGS:
        assert flag not in params, (
            f"{flag} now exists on `update` -- move its rule from "
            "docs/engine-project-lifecycle.md into docs/cli-conventions.md"
        )


def test_runner_update_still_requires_the_copier_answers_file(tmp_path: Path) -> None:
    """The one update route today is Copier's, keyed on `.copier-answers.yml`.
    ADR 0041 decision 1 adds a second route keyed on `.forge/generation.json`;
    until then a project without the answers file is rejected as here.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "file.txt").write_text("x", encoding="utf-8")

    with pytest.raises(runner.ScaffoldError, match="copier-answers"):
        runner.update(project)


def test_new_contract_doc_and_adr_exist_and_name_the_metadata_file() -> None:
    assert ENGINE_PROJECT_LIFECYCLE.is_file()
    assert ADR_0041.is_file()
    doc = ENGINE_PROJECT_LIFECYCLE.read_text(encoding="utf-8")
    adr = ADR_0041.read_text(encoding="utf-8")
    for text, name in ((doc, "contract"), (adr, "ADR")):
        assert METADATA_FILE in text, f"the {name} does not name {METADATA_FILE}"
    # cli-conventions.md keeps the authoritative exit-status table; the new doc
    # must point at it rather than restate it.
    assert "cli-conventions.md" in doc


def test_adr_names_its_review_obligations_literally() -> None:
    """FT-15.04's own gate test asserts the contract names its review
    obligations verbatim; CF-16.02 owns CF-ROADMAP-01-AC-03 and -AC-05.
    """
    adr = ADR_0041.read_text(encoding="utf-8")
    for obligation in ("CF-ROADMAP-01-AC-03", "CF-ROADMAP-01-AC-05"):
        assert obligation in adr, f"ADR 0041 does not name {obligation}"


# --------------------------------------------------------------------------- #
# Derived assertions -- CF-18.03's rows, now that they are shipped             #
# --------------------------------------------------------------------------- #


def test_the_engine_new_path_persists_generation_metadata() -> None:
    """CF-18.03 (#160): `pipeline.finalise_files` writes the provider's
    generation-metadata document into the staged tree, before the rename, at
    the engine's own documented default path -- re-exported through
    `engine.generation_metadata_target()` (ADR 0041 rule 5) rather than
    duplicated as a second `.forge/generation.json` literal, so the two names
    can never drift apart. Accessed lazily (ADR 0045), not at `engine.py`
    module scope, so an out-of-range engine that predates this constant still
    fails through `EngineCompatibilityError` rather than a misleading
    `ImportError`.
    """
    assert engine.generation_metadata_target() == METADATA_FILE
    pipeline_source = (SRC / "pipeline.py").read_text(encoding="utf-8")
    assert "generation_metadata_target" in pipeline_source


def test_the_engine_new_path_runs_the_git_and_hook_lifecycle() -> None:
    """CF-18.03 (#160): `lifecycle.finalise_project` runs `git init` + one
    initial commit + conditional `pre-commit install --install-hooks` at the
    final destination, after the atomic rename (ADR 0041 decisions 5-7). It
    lives in its own engine-free module, called from `pipeline.finalise_files`
    -- neither `pipeline.py` nor `staging.py` spawns `git` directly.
    """
    pipeline_source = (SRC / "pipeline.py").read_text(encoding="utf-8")
    assert "lifecycle.finalise_project" in pipeline_source

    lifecycle_source = (SRC / "lifecycle.py").read_text(encoding="utf-8")
    assert re.search(
        r"""["'`]init["'`],\s*["'`]--initial-branch=main["'`]""", lifecycle_source
    ), "lifecycle.py does not run `git init --initial-branch=main`"
    assert "pre-commit" in lifecycle_source
    assert "--install-hooks" in lifecycle_source


# --------------------------------------------------------------------------- #
# Tripwires -- fail deliberately when the cutover lands                        #
# --------------------------------------------------------------------------- #


def test_tripwire_update_dispatches_only_to_runner_update() -> None:
    """Flips when CF-18.04 (#161) adds engine-native update dispatch to
    `cli.update_project` (ADR 0041 decision 1). Today it calls only
    `runner.update`.
    """
    source = (SRC / "cli.py").read_text(encoding="utf-8")
    # The engine-native route would import from create_forge.pipeline or a new
    # update module; the Copier route is the sole `update(` call today.
    assert "engine_native_update" not in source
    assert source.count("update(project") <= 1
