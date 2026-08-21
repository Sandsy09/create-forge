"""The bundled templates.toml loads and validates."""

from __future__ import annotations

import pytest

from create_forge.registry import load_registry


@pytest.fixture(autouse=True)
def _clear_registry_cache() -> None:
    # load_registry is process-cached; clear it so every test observes a
    # freshly parsed registry rather than another test's cached object.
    load_registry.cache_clear()


def test_bundled_registry_loads_and_has_templates() -> None:
    registry = load_registry()
    assert registry.templates


def test_template_ids_are_unique() -> None:
    ids = [t.id for t in load_registry().templates]
    assert len(ids) == len(set(ids))


def test_default_template_exists_and_is_not_deprecated() -> None:
    registry = load_registry()
    default = registry.get(registry.default_template)
    assert default.status != "deprecated"
