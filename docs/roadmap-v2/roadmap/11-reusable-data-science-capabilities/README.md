# Stage 11 — Reusable Data Science Capabilities

## Epic

[FT-EPIC-11 / forge-template#97](https://github.com/Sandsy09/forge-template/issues/97)
delivers the first production capability layer selected by Stage 10.

## Dependencies

FT-EPIC-11 is natively blocked by FT-EPIC-10.

## Child sequence

1. [FT-11.01 / #105](https://github.com/Sandsy09/forge-template/issues/105)
   adds additive Foundation extension points for capability tooling.
2. [FT-11.02 / #106](https://github.com/Sandsy09/forge-template/issues/106)
   implements the optionless `jupyter` capability.
3. [FT-11.03 / #107](https://github.com/Sandsy09/forge-template/issues/107)
   implements the independently applicable `scientific-python` capability.
4. [FT-11.04 / #108](https://github.com/Sandsy09/forge-template/issues/108)
   validates omission, independent and combined selection, compatibility,
   deterministic rendering, and packaged resources.

FT-11.01 is blocked by FT-10.04. The two capability implementations may then
proceed independently; both block FT-11.04.

## Entry criteria

- Stage 10's contract is accepted.
- Capability ownership, applicability, options, and compatibility are fixed.

## Outcomes

- Add reviewed package-bound capability manifests and content.
- Define options, requirements, conflicts, contributions, and compatibility.
- Use only published extension points and deterministic composition order.
- Expose path-free descriptors through the public discovery facade.
- Prove valid, omitted, conflicting, and inapplicable selections.
- Preserve a provider-, framework-, and domain-neutral Foundation.

## Exit criteria

The selected capability layer is production-ready, documented, deterministic,
and suitable for the Data Science archetype. Stage 12 may then implement that
archetype against real components.

## Non-goals

This stage does not implement the archetype, client UX, plugins, or a remote
component registry.
