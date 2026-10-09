"""The batch user-guide recipes, defined once (CF-29.02, ADR 0062).

`docs/user-guide/batch.md` documents these exact commands.
`tests/test_e2e_installed_batch.py` runs each through the real installed
console, and `tests/test_user_guide_recipes.py` asserts the guide still says
them -- so the guide, the e2e evidence, and the drift guard share one source
and cannot silently diverge.

Nothing here imports `create_forge` or `forge_template`. The archetype and
capability ids are fixture data typed exactly as a user would type them, never
selection logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Recipe:
    """One documented `new` command and the directory it creates."""

    id: str
    command: str
    directory: str


RECIPES = (
    Recipe(
        id="plain",
        command=(
            'uvx create-forge new "Nightly Report" --archetype batch '
            "--yes --data license=mit"
        ),
        directory="nightly-report",
    ),
    Recipe(
        id="scientific-python",
        command=(
            'uvx create-forge new "Daily Metrics" --archetype batch '
            "--capability scientific-python --yes --data license=mit"
        ),
        directory="daily-metrics",
    ),
)

# The check the guide tells a user to run in the generated project.
CHECK_COMMAND = "uv run --locked poe check"

# Unlike a server archetype's `run` task, the batch job terminates, so the
# acceptance harness can execute it: it reads the tracked sample input and
# writes `data/output.json`, with no scheduler or service involved.
RUN_COMMAND = "uv run poe run"
