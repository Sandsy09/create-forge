"""The Streamlit user-guide recipes, defined once (CF-21.02, ADR 0051).

`docs/user-guide/streamlit.md` documents these exact commands.
`tests/test_e2e_installed_streamlit.py` runs each through the real installed
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
            'uvx create-forge new "Sales Explorer" --archetype streamlit '
            "--yes --data license=mit"
        ),
        directory="sales-explorer",
    ),
    Recipe(
        id="scientific-python",
        command=(
            'uvx create-forge new "Model Explorer" --archetype streamlit '
            "--capability scientific-python --yes --data license=mit"
        ),
        directory="model-explorer",
    ),
)

# The check the guide tells a user to run in the generated project. `poe run`
# is deliberately not a recipe step here: it starts a server, and the provider's
# non-serving smoke rule forbids the acceptance harness from doing that.
CHECK_COMMAND = "uv run --locked poe check"
