# Data Science Roadmap Architecture

The accepted public-engine architecture remains unchanged. The roadmap adds a
third archetype and the first production capabilities through existing
package-bound component contracts.

```text
User
  ↓
create-forge --engine-preview
  │ discovery-driven selections and options
  │ strict ProjectSpec protocol
  ↓
forge-template public engine
  │ implicit Foundation
  │ exactly one archetype
  │ zero or more capabilities and platforms
  ↓
validated in-memory project
  ↓
create-forge staging, uv lock, atomic finalisation
```

## Accepted direction

- The canonical
  [Data Science contract](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-archetype.md)
  defines an optionless, package-backed, notebook-oriented archetype with
  independently owned package, test, notebook, and ignored working-tree paths.
- Reusable optional concerns become capabilities rather than Foundation
  defaults or duplicated archetype content.
- FT-10.01 fixes the minimal shape: the archetype owns the starter notebook
  and working-tree conventions. FT-10.02's canonical
  [initial capability contracts](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md)
  define reusable Jupyter development tooling and the independently optional
  Scientific Python runtime stack. Stage 10 subsequently fixed safeguards and
  compatibility. FT-11.01 published the additive Foundation points, and
  FT-11.02 now implements Jupyter on unreleased `forge-template/main`; the
  released create-forge range remains on the two-archetype `0.3.x` line.
- Capabilities remain bundled, reviewed forge-template components. This
  roadmap does not introduce plugins or remote component registries.
- create-forge consumes public descriptors and never recreates component
  semantics or catalogue metadata.

## Compatibility boundary

ProjectSpec, component-manifest, option-schema, Foundation-source, component,
and engine-package versions remain independently governed by the canonical
compatibility policy. Stage 10 must classify every required version change
before implementation, and Stage 14 reviews the resulting line before final
client rollout.

The default Copier path, `template/`, `copier.yml`, and stored Copier answers
are outside this roadmap unless a later, separately accepted cutover changes
that boundary.
