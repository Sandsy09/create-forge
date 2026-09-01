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

## Repository roles

- **forge-template** owns the Data Science contract, capabilities, archetype,
  composition review, generated content, and engine releases.
- **create-forge** owns discovery-driven user input, ProjectSpec construction,
  diagnostics, staging, lock finalisation, and end-to-end client validation.

See the [architecture](ARCHITECTURE.md),
[ownership model](REPOSITORY-OWNERSHIP.md), and
[stage roadmap](ROADMAP.md) for the complete boundary.

## Live GitHub work

Only six epics are filed. Child issues are intentionally deferred until each
epic is planned in turn:

- [forge-template epic index](https://github.com/Sandsy09/forge-template/blob/main/docs/roadmap-v2/github-issues/forge-template/ISSUE-INDEX.md)
- [create-forge epic index](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v2/github-issues/create-forge/ISSUE-INDEX.md)
- [cross-repository dependency matrix](github-issues/CROSS-REPO-DEPENDENCIES.md)
- [GitHub setup and taxonomy](github-issues/GITHUB-SETUP.md)
