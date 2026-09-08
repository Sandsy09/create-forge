# 37. Pin external Actions to reviewed commits and scope permissions per job

## Status

Accepted

## Context

The workflows in `.github/workflows/` mixed SHA-pinned and mutable references.
`actions/checkout@v7`, `astral-sh/setup-uv@v7` and
`pypa/gh-action-pypi-publish@v1.14.2` resolved through tags a maintainer of
the upstream repository can repoint after review, so the code a
release-capable job runs need not be the code that was assessed. `create-forge`
publishes to PyPI through Trusted Publishing and deploys GitHub Pages, so its
release and documentation jobs hold `contents: write`, `id-token: write` and
`pages: write` — the references with the largest supply-chain blast radius were
the least immutable.

Permissions were also granted too broadly. `release.yml` set `contents: write`
at the workflow level, so its `publish` job held repository write access on top
of the `id-token: write` it actually needs.

`forge-template` already pins every external action to a full commit SHA.
Dependabot reintroduces a mutable tag on each upgrade unless a check rejects
it. PRs #132–#135 SHA-pinned `actions/setup-python`, `actions/upload-artifact`,
`actions/upload-pages-artifact` and `actions/deploy-pages`; this decision
finishes the set and makes the policy self-enforcing.

This repo's Actions policy is **Allow select actions** with an explicit
third-party allowlist, which previously named the exact mutable tags
(`astral-sh/setup-uv@v7`). A SHA reference does not match a `@v7` allowlist
entry, and a non-matching `uses:` fails the whole run at startup with no log.

## Decision

1. **Pin every external `uses:` reference to a full 40-character commit SHA.**
   Keep the human-readable version in an adjacent `# vX.Y.Z` comment, in the
   form Dependabot writes. Repository-local (`./…`) and explicitly accepted
   `docker://` references stay outside the rule.

2. **Keep the workflow-level token scope read-only.** Each workflow sets
   `permissions: { contents: read }` at the top — the floor a checkout needs;
   a job re-grants a wider scope only where it uses one: `contents: write`
   only on the `release` job that pushes the tag, `id-token: write` only on
   the `publish` and Pages `deploy` jobs, `pages: write` only on the Pages
   `deploy` job.

3. **Enforce both properties in the protected test path.**
   `scripts/check_workflows.py` rejects an external reference that is a branch,
   a floating or exact tag, or an abbreviated or upper-case SHA; requires the
   version comment; requires a top-level `permissions:` key; and rejects any
   workflow-level write scope. `poe check:workflows` runs it standalone and
   `tests/test_workflows.py` runs it inside the fast suite that the `all-green`
   aggregate check requires.

4. **Widen the Actions allowlist entries to `owner/repo@*`.** The allowlist
   stays as the gate on *which* third-party actions may run; the SHA pin and
   check 3 are the gate on *which version*. A new third-party action is
   allowlisted in the change that introduces it.

5. **Resolve a Dependabot Action upgrade to its reviewed commit before
   merging.** Dependabot proposes a new SHA and version comment; the reviewer
   confirms the SHA is the commit the claimed tag resolves to. The check keeps
   the PR red until the reference is a full SHA with a comment.

## Consequences

- Actions are pinned to the commit their mutable tag resolved to at review
  time, not upgraded. `astral-sh/setup-uv` stays at v7.6.0 though v10 exists;
  moving it is now a separate, reviewable Dependabot PR.
- The `publish` job loses the repository write access it inherited from the old
  workflow-level grant and keeps only `contents: read` and `id-token: write`.
- `publish`'s `id-token: write` step is guarded by `if: ${{ !inputs.dry_run }}`,
  so a release dry run does not exercise the OIDC path; the first real exercise
  is the next actual release.
- A new workflow or job that needs a write scope must place it on the job. The
  check blocks a workflow-level `write` grant, including `permissions:
  write-all`; a read-only workflow-level `contents: read` is allowed as the
  floor.
- The Actions allowlist now admits any ref of the two named third-party
  actions, not one tag. Narrowing *which version* runs moves entirely to the
  workflow SHA and check 3; the allowlist keeps its narrower job of bounding
  *which actions* run at all.
- This changes CI and release plumbing only. It does not alter the package
  version, the engine compatibility range, the template trust boundary, or
  `forge-template`.
