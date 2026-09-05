# 34. Publish create-forge 0.3.0 and close the Data Science roadmap

## Status

Accepted

## Context

[Issue #114 / CF-14.04](https://github.com/Sandsy09/create-forge/issues/114)
is the fourth and last child of
[CF-EPIC-14](https://github.com/Sandsy09/create-forge/issues/104), and the
last open issue in the Data Science roadmap
([`docs/roadmap-v2`](../roadmap-v2/README.md)). Everything it depends on has
landed. CF-14.01 raised the engine range to `forge-template>=0.4.1,<0.5` and
set `pyproject.toml` to `0.3.0`
([ADR 0031](0031-adopt-the-reviewed-forge-template-0-4-1-release.md)). CF-14.02
built that candidate wheel and validated both accepted Data Science
compositions through its installed console script
([ADR 0032](0032-validate-installed-data-science-generation.md)). CF-14.03
proved everything CF-14.02 left out — Library, CLI Application, the engine-less
Copier path, a real out-of-range engine, and the full failure matrix
([ADR 0033](0033-complete-rollout-regression-validation.md)). Each of those
records ends by naming CF-14.04 as the owner of the changelog, tag,
publication, and verification.

Nothing was published. PyPI's latest `create-forge` was `0.2.1` and the newest
tag was `v0.2.1`, so `0.3.0` — the first line with generic discovery-driven
component selection and the Data Science archetype reachable behind
`--engine-preview` — existed only as a prepared version number. Epic acceptance
criterion 7 makes an unpublished, unverified release a blocker on closing the
shared roadmap.

The compatibility change that defines this line landed as
`chore: adopt reviewed forge-template 0.4.1 (#126)`. `[tool.git-cliff]` skips
`chore`, so `git-cliff --tag v0.3.0` produces a correct changelog section that
does not mention the engine range. Changing the parser config would rewrite
every earlier section on the next regeneration and pull unrelated maintenance
commits into all future changelogs.

## Decision

1. **Ship `0.3.0` as the generic-component-selection line, with the default
   path unchanged.** `--engine-preview` stays hidden and opt-in; `new` stays
   direct-Copier. The release notes and evidence record say so explicitly.
   This is the release's headline constraint, matching CF-EPIC-14's own
   exclusion, not an unfinished cutover.

2. **Split the work across the release.** A pre-release PR regenerates
   `CHANGELOG.md` and nothing else, because that is all the Release workflow's
   changelog gate needs and the only claim true before the tag exists. A
   post-release PR carries this ADR, the evidence record, and every "released
   and verified" statement in the roadmap records.

3. **Keep `CHANGELOG.md` purely `git-cliff` output.** The `forge-template
   0.4.1` engine-range statement goes on the GitHub release page as a
   prepended *Compatibility* paragraph and into the evidence record — not a
   hand edit to the generated file, and not a `commit_parsers` change.

4. **Verify against the published artefacts, recorded verbatim.** A clean
   environment installs `create-forge==0.3.0` and `create-forge[engine]==0.3.0`
   from PyPI and reproduces the CF-14.02/14.03 generations — both Data Science
   compositions, Library, CLI Application, and the engine-less default Copier
   path — with each generated project's own `uv run --locked poe check`. The
   real command output lands in `docs/release-0-3-0-validation.md`. No new test
   module: a PyPI-resolving suite would make CI depend on PyPI availability and
   duplicate the candidate-wheel suites byte for byte.

5. **Reconcile both repositories' roadmap bookkeeping.** Every closed child's
   acceptance checklist is checked against its landed evidence and ticked;
   anything unevidenceable stays unticked and is reported. Both
   `CROSS-REPO-DEPENDENCIES.md` matrices are reconciled — the create-forge one
   in the post-release PR, the forge-template one in a single-file sibling PR
   touching no template content. Both Stage 13 and Stage 14 create-forge
   milestones close.

6. **Record this as its own ADR and canonical doc.** CF-14.01/02/03 each did.
   `docs/release-0-3-0-validation.md` maps the release identity, the published
   verification, and the six-epic / 24-child reconciliation to their evidence;
   it is linked from `CLAUDE.md` and `CONTRIBUTING.md` with a link-audit case
   in `tests/test_engine_contract.py`.

## Consequences

- No shipped module, dependency range, CLI flag, protocol, or default path
  changes. `pyproject.toml` stays at the `0.3.0` CF-14.01 committed. No new or
  changed test.
- `create-forge 0.3.0` and `create-forge[engine] 0.3.0` are on PyPI, tag
  `v0.3.0` is on `main`, and the GitHub release is published. A published PyPI
  version is immutable: any defect found after publication is a `0.3.1`, not a
  re-upload.
- `docs/release-0-3-0-validation.md` is new. `CLAUDE.md`, `CONTRIBUTING.md`,
  `README.md`, `docs/rollout-regression-validation.md`,
  `docs/installed-data-science-validation.md`, and
  `docs/data-science-preview-validation.md` retire their "CF-14.04 owns…"
  forward references; the Stage 14 roadmap records, both issue indexes, and
  both dependency matrices describe the shipped graph.
- CF-14.04 closes, CF-EPIC-14 closes, and the create-forge Stage 13 and
  Stage 14 milestones close. The Data Science roadmap is complete in both
  repositories.
- This is still not the CLI cutover. The engine replacing direct Copier as the
  default `new` path remains a separate, unfiled decision.
