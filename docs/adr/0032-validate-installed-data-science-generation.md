# 32. Validate Data Science through the installed create-forge candidate

## Status

Accepted

## Context

[Issue #112 / CF-14.02](https://github.com/Sandsy09/create-forge/issues/112)
is the second child of
[CF-EPIC-14](https://github.com/Sandsy09/create-forge/issues/104). CF-13.05
proved the full Data Science composition through the real console script, but
that script came from create-forge's editable development environment.
CF-14.01 then prepared create-forge `0.3.0` and adopted the reviewed,
PyPI-published `forge-template 0.4.1` release. No test yet joined those two
release candidates through the console script installed from the built
create-forge wheel.

The provider already proves both accepted Data Science compositions at the
public-engine boundary and across the Python support window. Its Stage 14
handoff deliberately leaves the final client-owned boundary here: CLI answer
collection, ProjectSpec construction, installed engine negotiation, staged
filesystem generation, client-owned lock finalisation, generated-project
restoration, and the resulting distribution must all work together without
either Forge package leaking into the generated project.

## Decision

1. **Install the client candidate from its wheel.** The E2E suite builds a
   fresh create-forge `0.3.0` wheel into a temporary directory and installs
   `wheel[engine]` into an isolated Python 3.13 virtual environment. The
   reviewed engine is constrained to exactly the published `0.4.1` package.
   PEP 610 metadata proves create-forge came from the wheel and forge-template
   came from the package index, not either working tree.

2. **Drive both accepted compositions through that environment's console
   script.** `data-science` + `jupyter`, and `data-science` + `jupyter` +
   `scientific-python`, each generate twice into empty destinations with every
   answer supplied explicitly. The candidate environment's `uv` is first on
   `PATH`; parent virtual-environment state, user configuration, and
   `FORGE_*` variables cannot influence the result.

3. **Treat the lock as part of client determinism.** Each pair must contain
   the same relative files and identical bytes, including `uv.lock`, and both
   locks must pass `uv lock --check`. This is stricter than the provider's
   render-only determinism proof because create-forge owns lock finalisation.

4. **Derive output expectations from the installed plan.** A subprocess in
   the candidate environment runs the installed shared pipeline for the same
   answers and selection. Every console-written rendered byte must match that
   plan, every planned file must be owned by Foundation or a selected
   component, and every selected component must contribute. No provider file
   manifest is copied into create-forge.

5. **Run the generated projects as users do.** Both compositions restore with
   `uv sync --all-groups --locked`, pass `uv run --locked poe check`, execute
   `poe notebook:check`, build a wheel and sdist, and install their wheel into
   a second environment outside the project. The full Scientific Python
   composition also runs its generated scientific smoke test explicitly.

6. **Carry the provider handoff matrix through the client.** Both
   compositions run at the client default Python 3.13; the full composition
   repeats its locked check, scientific smoke, and live-kernel notebook
   execution at Python 3.11 and 3.14. Provider-owned wider composition and
   endpoint matrices are not duplicated.

7. **Audit independence and ignored working trees.** Generated metadata,
   locks, built archives, and isolated installations must contain neither
   Forge distribution. Markers planted under `data/raw`, `data/interim`,
   `data/processed`, `models`, and `artifacts` must enter neither wheel nor
   sdist. Installed packages must report version `0.1.0`,
   `Requires-Python >=3.11`, and a `py.typed` marker.

8. **Make temporary ownership explicit.** Candidate builds, client and
   generated-package environments, generated destinations, and build outputs
   live under context-managed temporary roots. Cleanup therefore runs when a
   test succeeds, an assertion fails, a child command fails, or a subprocess
   times out.

## Consequences

- `tests/test_e2e_installed_data_science.py` is a third `e2e`-marked module.
  It is CI-enforced by the existing E2E job; no new marker or required job is
  introduced.
- The existing editable-environment engine suite remains unchanged. Library,
  CLI Application, default Copier, compatibility, and atomic-failure matrices
  remain CF-14.03's responsibility.
- The canonical
  [installed Data Science validation](../installed-data-science-validation.md)
  record maps #112's acceptance criteria to the executable tests.
- No shipped module, public API, CLI flag, schema, dependency range, protocol,
  component identifier, runtime behavior, or default path changes. The engine
  remains optional and `--engine-preview` remains preview-only.
- create-forge remains prepared at `0.3.0`. CF-14.04 still owns the changelog,
  tag, publication, and installed release verification.
