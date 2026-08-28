"""The shared create pipeline: discover, build, validate, render -- in memory.

This is the one internal generation path CF-07.01 introduces (ADR 0014).
It depends on `create_forge.engine` -- and therefore, transitively, on the
development-only `forge-template` dependency -- but its own source never
imports `forge_template` directly: type annotations that need engine-owned
types import them only under `TYPE_CHECKING`, so this module's runtime
behaviour never requires the engine to be *type-checkable*, only to be
*installed* when one of its functions is actually called. `engine.py` remains
the only module whose source touches `forge_template` at runtime, per ADR
0013 and invariant 4.

`create_forge.cli` imports this module lazily, inside `--engine-preview`'s
branch only, guarded by `try/except ImportError` -- see ADR 0014 for why:
`forge-template` is not a runtime dependency of the released CLI, so no
module reachable at `cli.py`'s own import time may depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from create_forge import engine
from create_forge.spec import build_spec_payload

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from forge_template import ProjectSpec, RenderedProject


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One in-memory result of the shared create pipeline.

    Ready for CF-07.04 to stage and finalise. No filesystem write happens
    here or in anything this wraps -- `engine.render()` is in-memory only.
    """

    spec: ProjectSpec
    rendered: RenderedProject


def build_generation_request(
    answers: Mapping[str, object],
    *,
    archetype: str,
    capabilities: Sequence[str] = (),
    platforms: Sequence[str] = (),
    component_options: Mapping[str, Mapping[str, object]] | None = None,
) -> GenerationRequest:
    """Run the shared pipeline: discover -> build -> validate -> render.

    Interactive and non-interactive `new` invocations both converge here once
    they've collected the same `answers` mapping `cli._collect_answers`
    already produces today -- nothing about answer collection changes.

    `archetype`/`capabilities`/`platforms`/`component_options` stay
    caller-supplied (ADR 0013): this pipeline mints no component identifiers
    of its own. `discover()` runs for its own compatibility-ladder effect and
    to surface real descriptors to future callers; it does not yet drive
    selection -- Stage 08 gives it something to drive.

    Every downstream call (`build_project_spec`, `validate`, `render`)
    independently re-checks package/protocol compatibility before doing its
    own work, so there is no side effect -- in-memory or otherwise -- before
    every check has passed.
    """
    engine.discover()
    payload = build_spec_payload(
        answers,
        archetype=archetype,
        capabilities=capabilities,
        platforms=platforms,
        component_options=component_options,
    )
    spec = engine.build_project_spec(payload)
    validated = engine.validate(spec)
    rendered = engine.render(validated)
    return GenerationRequest(spec=validated, rendered=rendered)
