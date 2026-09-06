# 35. Shared Forge user documentation

## Status

Accepted

## Context

[Issue #8](https://github.com/Sandsy09/create-forge/issues/8) deferred a
documentation site when plain Markdown ADRs covered the available material.
The released CLI now exposes three preview archetypes and two capabilities.
Root READMEs have accumulated implementation history while practical usage,
installation, and version-selection instructions are hard to find.

## Decision

Maintain one Forge user guide in `create-forge/docs/user-guide`, serving both
repositories at `https://sandsy09.github.io/create-forge/`. Keep the root
READMEs focused on orientation and essential commands. Existing contracts,
ADRs, and validation evidence stay in their owning repositories and are
linked through a short reference index rather than copied into the site.

Publish one current-release guide, initially covering create-forge 0.3.0
with forge-template 0.4.1. Label preview features and update limitations
explicitly. Accepted future contracts do not establish released behaviour.
Update affected user guides and their release pair when behaviour changes.

Use MkDocs >=1.6,<2 and Material >=9.5,<10 as locked development dependencies,
matching the existing template documentation stack. Keep dependency tooling
within those major versions. Enable search, code copying, source editing,
and per-page documentation feedback through GitHub Issues. Use existing
bug and feature forms and a dedicated documentation form in both repos.

Build strictly on every PR and require that job in the existing CI
aggregate. Upload the site as a review artifact. Deploy an artifact from
main with GitHub Pages Actions; only the deployment job receives Pages and
OIDC write permissions. PRs never deploy. The first publication follows
review of both repository PRs and the built site; enable Pages with the
Actions source, deploy, and verify the site before merging sibling links.

## Consequences

Users have one searchable starting point, while engine reference ownership
remains in forge-template. The site adds a release-maintenance obligation:
examples must be exercised and current behaviour kept separate from plans.
Strict builds check local navigation, links, and anchors; external links and
browser behaviour are checked before publication.

Documentation does not change CLI behaviour, generated files, or package
versions. PyPI descriptions receive the rewritten READMEs on the next
package releases. Historical ADRs and completed roadmaps remain intact.
