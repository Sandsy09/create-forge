# Forge Data Science Roadmap — Two-Repository Edition

This roadmap continues the completed
[Forge Foundation roadmap](../roadmap-v1/README.md) through Stages 10–14.
It plans the next production archetype without reopening the Foundation,
composition, reference-client, or Blueprint decisions completed in Stages
00–09.

The target is a package-backed, notebook-oriented Data Science project with
reusable optional capabilities. Exact scientific libraries, notebook front
ends, data-versioning systems, model tooling, and deployment integrations are
not selected here; Stage 10 owns those decisions.

Delivery remains behind `create-forge new --engine-preview`. Retiring the
default direct-Copier path is a separate future initiative.

Stages 10–12 are complete. The package-bound five-component catalogue is
published as
[`forge-template 0.4.0`](https://github.com/Sandsy09/forge-template/releases/tag/v0.4.0)
on [PyPI](https://pypi.org/project/forge-template/0.4.0/). Stage 13 is
complete: CF-13.01 (ADR 0026) adopted the `forge-template>=0.4,<0.5`
compatibility line, so `--engine-preview` discovery now returns all five
descriptors, and CF-13.02 (ADR 0027) fixed the generic component-selection
CLI conventions, which CF-13.03 (ADR 0028) implemented for capabilities and
platforms and CF-13.04 (ADR 0029) for per-component options, and CF-13.05
(ADR 0030) validated the Data Science composition through the shared pipeline
against the released engine, closing CF-EPIC-13. Stage 14 takes the released
client and engine pair through installed-console validation and rollout.
Provider Stage 14 is complete and published the reviewed
`forge-template 0.4.1` release. CF-14.01 (ADR 0031) adopts it as create-forge's
`>=0.4.1,<0.5` lower bound and prepares create-forge `0.3.0`; CF-14.02
(ADR 0032) completes installed-console Data Science validation, and CF-14.03
(ADR 0033) completes the installed regression and failure matrix. CF-14.04
(ADR 0034) published create-forge `0.3.0` to PyPI, verified the released pair,
and closed CF-EPIC-14 and both Stage 13 and Stage 14 milestones. **The Data
Science roadmap is complete in both repositories.**

## Repository roles

- **forge-template** owns the Data Science contract, capabilities, archetype,
  composition review, generated content, and engine releases.
- **create-forge** owns discovery-driven user input, ProjectSpec construction,
  diagnostics, staging, lock finalisation, and end-to-end client validation.

See the [architecture](ARCHITECTURE.md),
[ownership model](REPOSITORY-OWNERSHIP.md), and
[stage roadmap](ROADMAP.md) for the complete boundary.

## Live GitHub work

Six epics and 24 child issues are filed across the two repositories. GitHub
issue bodies and native parent/dependency relationships are authoritative:

- [forge-template epic index](https://github.com/Sandsy09/forge-template/blob/main/docs/roadmap-v2/github-issues/forge-template/ISSUE-INDEX.md)
- [create-forge epic index](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v2/github-issues/create-forge/ISSUE-INDEX.md)
- [cross-repository dependency matrix](github-issues/CROSS-REPO-DEPENDENCIES.md)
- [GitHub setup and taxonomy](github-issues/GITHUB-SETUP.md)
