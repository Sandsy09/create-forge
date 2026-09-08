# GitHub Actions Workflow Security

This is the living contributor contract for how `create-forge`'s
`.github/workflows/` pins external actions and scopes the `GITHUB_TOKEN`.
[ADR 0037](adr/0037-immutable-workflow-actions.md) records the decision; the
rules below are what [`scripts/check_workflows.py`](../scripts/check_workflows.py)
enforces and what a reviewer applies to a Dependabot Action pull request.

## Why it matters

`create-forge` publishes to PyPI through Trusted Publishing (OIDC) and deploys
GitHub Pages. Its `release` and `deploy` jobs therefore hold `contents: write`,
`id-token: write` and `pages: write`. A mutable action reference — a branch, or
a `v7` / `v1.14.2` tag — can be repointed by the upstream repository after the
workflow was reviewed, so one of those jobs could run code that was never
assessed. Pinning to an immutable commit closes that gap; keeping write scopes
off the workflow level keeps a compromised or buggy action in an unrelated job
from reaching them.

## The pinning rule

Every **external** `uses:` reference is a full 40-character lowercase commit
SHA, with the human-readable version in an adjacent comment:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

The check rejects, with a distinct message for each:

- a branch or floating tag (`@main`, `@v7`)
- an exact version tag (`@v7.0.1`, `@v1.14.2`) — still mutable
- an abbreviated or upper-case SHA
- a full SHA with no `# <version>` comment

Two reference kinds sit **outside** the rule:

- repository-local actions (`./.github/actions/…`) — already immutable, they
  live in this repo
- `docker://` image references — accepted explicitly; pin by digest if one is
  ever added

Reusable-workflow references (`owner/repo/.github/workflows/x.yml@<sha>`) follow
the same SHA rule; there are none today.

## The permissions rule

Each workflow declares `permissions:` at the top level with `contents: read`
and nothing more — a read-only floor. A job re-grants a wider scope only when
it needs one:

| Workflow / job | Scope | Why |
| --- | --- | --- |
| `ci.yml` — all jobs | `contents: read` (inherited) | clone the repo; nothing here writes |
| `release.yml` — `release` | `contents: write` | push the release tag, create the GitHub release |
| `release.yml` — `publish` | `contents: read`, `id-token: write` | check out, then PyPI Trusted Publishing |
| `docs.yml` — `build` | `contents: read` (inherited) | check out, build the site |
| `docs.yml` — `deploy` | `pages: write`, `id-token: write` | deploy to GitHub Pages |

The check rejects any `write` scope — or `permissions: write-all` — at the
workflow level, and requires every workflow to declare a top-level
`permissions:` key so it never falls back to the repository's default token
scopes. Job-level scopes are not otherwise constrained: a new job that needs
`packages: write`, say, places it on the job.

## Reviewing a Dependabot Action upgrade

Dependabot's `github-actions` ecomony proposes a new SHA and version comment
for an action. Before approving:

1. Confirm the new SHA is the commit the proposed tag resolves to —
   `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (dereference an annotated
   tag with `gh api repos/<owner>/<repo>/git/tags/<sha>`).
2. Skim the upstream diff between the old and new commit for anything the
   workflow's permissions would let it abuse.
3. Let CI run. `check:workflows` keeps the PR red until the reference is a full
   SHA with a comment, so a malformed Dependabot proposal cannot merge.

Pin at the SHA the tag resolves to; a version jump the maintainer does not
want is declined, not merged and reverted. ADR 0012's
[engine update policy](engine-updates.md) is separate — it governs the
`copier` and `forge-template` compatibility-line dependencies, not actions.

## Running the check

```bash
uv run poe check:workflows
```

It also runs inside `uv run poe check` via
[`tests/test_workflows.py`](../tests/test_workflows.py), which the `test` job
runs and the protected `all-green` aggregate check requires. When a rule above
changes, update this document, `scripts/check_workflows.py`, and
`tests/test_workflows.py` in the same pull request.
