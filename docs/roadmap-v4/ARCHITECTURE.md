# Streamlit Archetype architecture boundaries

## Existing baseline, not a new API

Provider manifests, composition, generated content and in-memory validation
stay in forge-template. Client UX, ProjectSpec construction, staging,
filesystem application, Git/hooks and error presentation stay in create-forge.

```text
Client selection → ProjectSpec → public provider validation/render
                                ↓
                    validated in-memory output
                                ↓
             client staging, lock and filesystem application
```

The current release keeps Copier as default and the engine preview optional.
This preparation changes no runtime API, schema, dependency or version.

## Accepted planning gates

- Engine-native updates and legacy Copier updates must work before cutover.
- Provider contract acceptance precedes client contract approval; provider
  publication precedes client implementation/adoption.
- Streamlit waits for CF-16.03, not CF-18.07. FT-19.02 must select its target
  compatibility line and record any genuinely necessary implementation edges.
- Provider releases are immutable reviewed hand-offs. If integrated testing
  finds a defect, publish a corrected provider and repeat affected adoption
  and validation; never substitute a moving branch as a completed hand-off.
- No silent compatibility fallback, copied catalogue rules, private resource
  inspection, arbitrary component registry or plugin mechanism is permitted.
- Retain credential-free diagnostics and existing source-validation safety.

## Decisions still required

Contract children must decide metadata format, reproducible update inputs,
merge/conflict and recovery policy, platform/tooling ownership, package and
protocol compatibility, and support/deprecation sequencing. Streamlit contracts
must decide layout, entry point, dependency ownership, Python support and the
bounded non-serving validation strategy. None is preselected by this pack.

CF-16.01 must reconcile the current client engine-resolution guidance and
ADR 0011's atomic replacement of `--template-url` with the proposed explicit
legacy route. New accepted ADRs supersede decisions where necessary; historical
records are never rewritten. Engine-source overrides are executable package
resolution, not permission to load arbitrary component catalogues.

## Review interpretation

The source review's provider and client cutover drafts describe decision
issues. Their no-implementation/no-release exclusions apply to those contract
children, not to the complete cutover delivery roadmap. Their implementation,
validation and publication follow-ups are deliberately separate here.
