"""Loads the bundled template registry.

The registry is package data, not user configuration. It is read once, validated
by Pydantic, and cached for the process lifetime. A malformed registry is a
packaging bug, not a user error, so the failure is loud and unhandled.
"""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources

from pydantic import ValidationError

from create_forge.models import Registry

_REGISTRY_FILE = "templates.toml"


@cache
def load_registry() -> Registry:
    """Read and validate the bundled registry."""
    raw = resources.files("create_forge").joinpath(_REGISTRY_FILE).read_text("utf-8")

    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - packaging bug
        msg = f"Bundled {_REGISTRY_FILE} is not valid TOML: {exc}"
        raise RuntimeError(msg) from exc

    try:
        return Registry.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - packaging bug
        msg = f"Bundled {_REGISTRY_FILE} failed validation:\n{exc}"
        raise RuntimeError(msg) from exc