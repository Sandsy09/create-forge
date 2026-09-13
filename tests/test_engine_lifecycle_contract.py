"""Guards for the engine project lifecycle contract (CF-16.02, ADR 0041).

`docs/engine-project-lifecycle.md` is a *decision*, not a shipped interface --
but every rule it decided is now built: CF-18.03 (#160) implemented the `new`
half (git init, initial commit, conditional hooks, the committed
`.forge/generation.json` metadata file); CF-18.04 (#161, ADR 0046) implements
the `update` half (file-based routing, the Git-backed three-way merge, the
per-target `--dry-run` list, and the client-owned `--degraded` fallback);
CF-18.05 (#162, ADR 0047) implements rule 8's exact wording (the pre-cutover
`--engine-preview` rejection) and the retention specifics ADR 0041 rule 7
otherwise left to it.

Same discipline as `tests/test_engine_default_contract.py` and
`forge-template`'s `tests/test_cutover_gates.py`:

- **Derived assertions** read the live CLI, so a claim about *today's* state
  that silently changes fails here.
- **Tripwires** assert a not-yet-built state deliberately, each naming the
  CF-EPIC-18 issue whose merge must flip it. When it lands, the tripwire is
  replaced by a derived assertion proving the real behaviour, and the
  affected rule moves out of `docs/engine-project-lifecycle.md`'s "decided"
  voice into `docs/filesystem-generation.md` / `docs/cli-conventions.md`'s
  "in force" voice in the same change -- CF-18.03, CF-18.04 and CF-18.05 have
  now all done exactly this; no CF-EPIC-18 tripwire remains in this file.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer.main

from create_forge import engine, update
from create_forge.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_0041 = (
    REPO_ROOT / "docs" / "adr" / "0041-engine-project-lifecycle-and-update-dispatch.md"
)
ADR_0046 = REPO_ROOT / "docs" / "adr" / "0046-engine-native-update-application.md"
ADR_0047 = (
    REPO_ROOT
    / "docs"
    / "adr"
    / "0047-legacy-copier-retention-and-preview-transition.md"
)
ENGINE_PROJECT_LIFECYCLE = REPO_ROOT / "docs" / "engine-project-lifecycle.md"
SRC = REPO_ROOT / "src" / "create_forge"

METADATA_FILE = ".forge/generation.json"


def _update_params() -> dict[str, object]:
    """Every click parameter on `create-forge update`, keyed by long option."""
    command = typer.main.get_command(app)
    update_command = command.commands["update"]  # type: ignore[attr-defined]
    params: dict[str, object] = {}
    for param in update_command.params:
        for opt in param.opts:
            params[opt] = param
    return params


# --------------------------------------------------------------------------- #
# Derived assertions -- today's state, read from the live CLI                  #
# --------------------------------------------------------------------------- #


def test_update_has_the_full_cutover_parameter_set() -> None:
    """CF-18.04 (#161): `update` now takes `--legacy` and `--degraded`
    alongside the pre-cutover `project`/`--ref`/`--dry-run` (ADR 0041
    decisions 1 and 10) -- this reads the live command, so a flag that is
    removed without updating the contract fails here.
    """
    params = _update_params()
    assert set(params) >= {"--ref", "--dry-run", "--legacy", "--degraded"}


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
# Derived assertions -- CF-18.03's rows                                       #
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
# Derived assertions -- CF-18.04's rows, now that they are shipped            #
# --------------------------------------------------------------------------- #


def test_update_routes_by_file_not_by_flag() -> None:
    """ADR 0041 rule 7: routing reads the project's own files, never a flag
    (other than the explicit `--legacy` override) -- `update.route_for` is
    the one place this decision lives.
    """
    assert update.route_for.__module__ == "create_forge.update"
    cli_source = (SRC / "cli.py").read_text(encoding="utf-8")
    assert "update.route_for" in cli_source


def test_the_update_route_dispatches_to_the_engine_native_module() -> None:
    """CF-18.04 (#161, ADR 0046): `cli.update_project` now reaches
    `create_forge.update`'s Git-backed application in addition to
    `runner.update`'s Copier path -- the tripwire this test replaces asserted
    the opposite.
    """
    cli_source = (SRC / "cli.py").read_text(encoding="utf-8")
    assert "pipeline.prepare_update" in cli_source
    assert "update.apply_plan" in cli_source
    assert "runner.update" not in cli_source  # still imported by name, unqualified
    assert "import update as copier_update" in cli_source


def test_the_engine_native_route_merges_with_git_merge_file() -> None:
    """ADR 0046: the per-target three-way merge (rule 12) is `git merge-file
    -p`, not a bespoke merge algorithm -- `create-forge` never re-implements
    what Git already does correctly and everyone already knows. `update.py`
    staying engine-free at all (no `forge_template` *import*) is
    `test_engine_contract.py`'s AST-based `_SHIPPED_MODULES` guard's job, not
    a substring check here -- this module's own docstring names
    `forge_template.plan_update` in plain English.
    """
    update_source = (SRC / "update.py").read_text(encoding="utf-8")
    assert "merge-file" in update_source


def test_the_degraded_route_never_invents_a_merge_base() -> None:
    """ADR 0041 rule 22 / decision 4: `--degraded` is entirely client-owned
    code, since `forge_template.plan_update` explicitly declines to perform
    this comparison itself. `update.degraded_plan` never calls the provider.
    """
    update_source = (SRC / "update.py").read_text(encoding="utf-8")
    assert "def degraded_plan" in update_source


def test_adr_0046_exists_and_is_indexed() -> None:
    assert ADR_0046.is_file()
    index = (REPO_ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    assert "0046" in index


# --------------------------------------------------------------------------- #
# Derived assertions -- CF-18.05's rows, now that they are shipped            #
# --------------------------------------------------------------------------- #


def test_the_neither_file_message_names_the_removed_preview_flag() -> None:
    """ADR 0047 rule 1: rule 8's rejection is one diagnostic covering all
    three "neither file" causes, including the removed `--engine-preview`
    flag, rather than a detected case of its own."""
    update_source = (SRC / "update.py").read_text(encoding="utf-8")
    assert "--engine-preview" in update_source


def test_the_copier_route_stays_reachable_without_a_usable_engine() -> None:
    """ADR 0047 rule 3: `update_project` must not resolve the engine-owned
    metadata filename unconditionally before routing -- a project that only
    records `.copier-answers.yml` does not depend on the engine at all."""
    cli_source = (SRC / "cli.py").read_text(encoding="utf-8")
    assert "EngineCompatibilityError" in cli_source
    assert "COPIER_ANSWERS_FILE" in cli_source


def test_adr_0047_exists_is_indexed_and_names_its_review_obligation() -> None:
    assert ADR_0047.is_file()
    index = (REPO_ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    assert "0047" in index
    adr = ADR_0047.read_text(encoding="utf-8")
    assert "CF-ROADMAP-01-AC-05" in adr


# --------------------------------------------------------------------------- #
# Executable examples -- link audit                                          #
# --------------------------------------------------------------------------- #


def test_engine_project_lifecycle_doc_reflects_the_shipped_state() -> None:
    """Every rule this contract decided is now shipped -- the doc's own
    Status section must say so rather than still describing `update` as
    Copier-only.
    """
    doc = ENGINE_PROJECT_LIFECYCLE.read_text(encoding="utf-8")
    assert "CF-18.04" in doc
    assert "ADR 0046" in doc
    assert "CF-18.05" in doc
    assert "ADR 0047" in doc
