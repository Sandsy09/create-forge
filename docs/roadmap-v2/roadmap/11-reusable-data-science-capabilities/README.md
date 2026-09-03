# Stage 11 — Reusable Data Science Capabilities

## Epic

[FT-EPIC-11 / forge-template#97](https://github.com/Sandsy09/forge-template/issues/97)
delivers the first production capability layer selected by Stage 10.

## Dependencies

FT-EPIC-11's native predecessor FT-EPIC-10 is complete.

## Child sequence

1. [FT-11.01 / #105](https://github.com/Sandsy09/forge-template/issues/105)
   is complete: additive Foundation extension points for capability tooling.
2. [FT-11.02 / #106](https://github.com/Sandsy09/forge-template/issues/106)
   is complete: the optionless `jupyter` capability, generated safe notebook
   validator, Foundation contributions, tests, and [ADR
   0050](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0050-production-jupyter-capability.md).
3. [FT-11.03 / #107](https://github.com/Sandsy09/forge-template/issues/107)
   is complete: the independently applicable `scientific-python` capability,
   exact runtime dependency contributions, generated import test, endpoint
   resolution, and [ADR
   0051](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0051-production-scientific-python-capability.md).
4. [FT-11.04 / #108](https://github.com/Sandsy09/forge-template/issues/108)
   is complete: production composition validation covers omission, independent
   and combined selection, compatibility, deterministic rendering, and
   packaged resources under [ADR
   0052](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0052-validate-production-capability-composition.md).

FT-11.01 through FT-11.04 are complete. Epic #97 and its milestone are closed;
the capability layer is published in `forge-template 0.4.0`.

## Entry criteria

- Stage 10's contract is accepted (complete).
- Capability ownership, applicability, options, and compatibility are fixed.
- Foundation's three capability-tooling extension points are published
  (FT-11.01, complete).

## Outcomes

- Add reviewed package-bound capability manifests and content.
- Define options, requirements, conflicts, contributions, and compatibility.
- Use only published extension points and deterministic composition order.
- Expose path-free descriptors through the public discovery facade.
- Prove valid, omitted, conflicting, and inapplicable selections.
- Preserve a provider-, framework-, and domain-neutral Foundation.

## Exit criteria

The selected capability layer is production-ready, documented, deterministic,
and suitable for the Data Science archetype. **Met.** Stage 12 implemented the
archetype against these production components and published the provider line.

## Non-goals

This stage does not implement the archetype, client UX, plugins, or a remote
component registry.
