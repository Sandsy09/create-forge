"""CF-18.06 (#163, ADR 0048 decision 4): a drift guard for the recipes
`tests/test_e2e_installed_cutover.py`'s `-k recipe` tests exercise against a
real installed console.

This does not run any command itself -- it only asserts that the exact
strings those e2e tests execute or assert on are still byte-present (after
whitespace normalisation, matching the existing tripwire pattern in
`tests/test_cutover_acceptance_contract.py`) in the corresponding
`docs/user-guide/*.md` file, so a doc edit that silently changes a documented
command the e2e suite still runs against the old string fails here, in the
fast suite, rather than only showing up as an e2e mismatch.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
from pathlib import Path

from create_forge.update import ROLLBACK_HINT
from tests.streamlit_recipes import CHECK_COMMAND, RECIPES

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_GUIDE = REPO_ROOT / "docs" / "user-guide"
UPDATES = USER_GUIDE / "updates.md"
MIGRATION = USER_GUIDE / "migration.md"
STREAMLIT = USER_GUIDE / "streamlit.md"
STREAMLIT_ARCHETYPE_CONTRACT = (
    "https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-archetype.md"
)


def _normalised(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_updates_doc_documents_the_diagnose_recipe() -> None:
    """`test_recipe_diagnose_with_doctor` runs `--version`, `doctor`, and
    `doctor --json` -- all three must still be the documented recipe.
    """
    text = _normalised(UPDATES)
    for command in (
        "uvx create-forge --version",
        "uvx create-forge doctor",
        "uvx create-forge doctor --json",
    ):
        assert command in text, f"updates.md no longer documents {command!r}"


def test_migration_doc_documents_the_pin_back_recipe() -> None:
    """`test_recipe_pin_back_to_0_3_x` runs this exact command."""
    text = _normalised(MIGRATION)
    assert 'uv tool install "create-forge==0.3.2"' in text


def test_migration_doc_documents_the_rollback_recipe_verbatim() -> None:
    """`test_recipe_rollback_restores_a_bad_update` runs
    `update.ROLLBACK_HINT` itself -- imported here rather than duplicated, so
    the two can never silently drift apart.
    """
    assert ROLLBACK_HINT in _normalised(MIGRATION)
    assert ROLLBACK_HINT in _normalised(UPDATES)


def test_migration_doc_documents_the_preview_project_rejection() -> None:
    """`test_preview_era_project_transition_is_rejected`
    (`tests/test_e2e_installed_cutover.py`, CF-18.05) asserts on these two
    fragments of `update.route_for`'s own "neither file" message -- the
    migration recipe quotes that message, so both fragments must survive
    here too.
    """
    text = _normalised(MIGRATION)
    assert "--engine-preview" in text
    assert "create-forge new" in text


def test_streamlit_guide_documents_every_recipe_the_e2e_suite_runs() -> None:
    """CF-21.02 (ADR 0051): `test_documented_recipe_runs_through_the_installed_console`
    (`tests/test_e2e_installed_streamlit.py`) runs each of these commands, and
    the documented check, through the installed console. Both read the strings
    from `tests/streamlit_recipes.py`, so the guide, the e2e evidence, and this
    guard cannot drift apart.
    """
    text = _normalised(STREAMLIT)
    for recipe in RECIPES:
        assert recipe.command in text, (
            f"streamlit.md no longer documents the {recipe.id!r} recipe"
        )
        assert f"cd {recipe.directory}" in text, (
            f"streamlit.md no longer tells the reader to `cd {recipe.directory}`"
        )
    assert CHECK_COMMAND in text


def test_streamlit_guide_links_the_provider_contract_instead_of_restating_it() -> None:
    """CF-ROADMAP-02-AC-07: generated-project details stay linked to
    `forge-template`, so the guide cannot go stale against what is generated.
    """
    assert STREAMLIT_ARCHETYPE_CONTRACT in STREAMLIT.read_text(encoding="utf-8")


def test_streamlit_guide_relative_links_resolve() -> None:
    """The page is excluded from the site until CF-21.03 releases it
    (`mkdocs.yml`'s `exclude_docs`), so the strict build never sees it. Its
    relative links to sibling guide pages are checked here instead.
    """
    text = STREAMLIT.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]+)\)", text)
    relative = [t for t in targets if not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", t)]
    assert relative, "expected at least one link to a sibling guide page"
    for target in relative:
        filename = target.partition("#")[0]
        assert (USER_GUIDE / filename).is_file(), f"streamlit.md links {target!r}"
