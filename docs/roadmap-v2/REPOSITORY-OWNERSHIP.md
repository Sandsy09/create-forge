# Data Science Repository Ownership

The existing one-way dependency remains authoritative:

```text
create-forge → forge-template → generated project
```

Generated projects require neither Forge package during normal development or
runtime operation.

## forge-template owns

- the canonical
  [Data Science archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-archetype.md),
  including its independently owned package, test, notebook, metadata, README,
  and ignored working-tree concerns;
- the canonical
  [initial capability contracts](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md),
  including Jupyter's development tooling and Scientific Python's optional
  runtime dependency stack;
- the production Jupyter manifest, generated validator, development
  dependencies, tasks, and Foundation contributions implemented by FT-11.02
  and published in `forge-template 0.4.0`;
- the production Scientific Python manifest, runtime dependencies, generated
  import test, and guidance implemented by FT-11.03 and published in `0.4.0`;
- the production Data Science manifest, package, tests, starter notebook,
  working-tree guidance, and Foundation contributions published in `0.4.0`;
- Foundation/archetype/capability/platform classification;
- package-bound capability and archetype manifests and content;
- component compatibility, dependencies, conflicts, options, and extension
  contributions;
- deterministic selection validation, planning, rendering, and generated
  output validation;
- generated notebook, package, test, metadata, and documentation behavior;
- the three-archetype composition review; and
- engine versioning, packaging, and releases.

## create-forge owns

- archetype and capability selection UX behind `--engine-preview`;
- interactive and non-interactive input precedence;
- public-descriptor-driven component option prompting;
- effective ProjectSpec construction and client-side compatibility messages;
- destination safety, staging, lock finalisation, and atomic placement;
- real console-script and generated-project end-to-end validation; and
- adoption and release of a compatible engine range.

## Explicit exclusions

- Foundation does not gain notebook, scientific, data, model, or deployment
  dependencies.
- create-forge does not gain copied templates, a component catalogue, or
  archetype-specific rendering logic, paths, or hard-coded component IDs.
- No client or policy may load private catalogue roots or replace arbitrary
  files.
- Engine preview remains opt-in; the default Copier cutover is unscheduled.
