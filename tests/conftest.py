"""Shared pytest configuration for contributor-only test options."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the local forge-template checkout used by drift tests."""
    parser.addoption(
        "--forge-template-root",
        metavar="PATH",
        help=(
            "Read copier.yml from a local forge-template checkout instead of "
            "cloning its latest release tag."
        ),
    )
