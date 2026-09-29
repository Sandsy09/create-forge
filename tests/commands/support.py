"""Non-fixture helpers shared by more than one `tests/commands/*` module.

Fixtures shared across files live in `conftest.py` instead, where pytest can
resolve them by name; these are plain functions/constants, imported
explicitly by whichever module needs them.
"""

from __future__ import annotations

from pathlib import Path

from forge_template import (
    GenerationMetadata,
    MetadataProtocols,
    ProviderIdentity,
    SelectedComponent,
)


def write_config(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


# A default archetype (CF-08.02): individual tests override this by
# appending a later --archetype, which wins under Click's last-flag-wins
# rule for a scalar option.
ENGINE_ANSWERS = [
    "--data",
    "github_org=test-org",
    "--data",
    "license=mit",
    "--data",
    "author_name=Test User",
    "--data",
    "author_email=test@example.invalid",
    "--data",
    "python_min_version=3.11",
    "--data",
    "python_version=3.13",
    "--archetype",
    "library",
]


def synthetic_metadata() -> GenerationMetadata:
    """A minimal but real `GenerationMetadata`, for a faked `RenderedProject`
    that must reach `finalise_generation_request` -- CF-18.03's fail-closed
    check rejects `metadata=None` before staging.
    """
    return GenerationMetadata(
        metadata_version=1,
        provider=ProviderIdentity(distribution="forge-template", version="0.5.0"),
        protocols=MetadataProtocols(projectspec=1, component_manifest=(1,)),
        spec={},
        components=(SelectedComponent(id="library", version="1.0.0"),),
        output=(),
    )
