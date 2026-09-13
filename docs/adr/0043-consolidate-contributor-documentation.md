# 43. Consolidate CLAUDE.md and CONTRIBUTING.md behind a docs index

## Status

Accepted

## Context

`CLAUDE.md` had grown to 729 lines and `CONTRIBUTING.md` to 549. Both grew by
accretion: every ADR since 0010 appended a paragraph of narrative recording
who moved which engine pin, in which issue, superseded by what. Roughly 400
lines of `CLAUDE.md` ("Accepted target", "Data Science roadmap", "Completed
bootstrap plan") and 300 lines of `CONTRIBUTING.md` ("Architecture decisions",
the roadmap history inside "Cross-repository changes") were pure history — all
of it already recoverable from `docs/adr/` (43 records at the time of writing),
`docs/roadmap-v{1..4}/`, and git history.

`CLAUDE.md` is loaded into every agent session working in this repository;
burying its six invariants and module boundaries under superseded narrative
has a real, recurring cost. `CONTRIBUTING.md` is worse for its actual
audience: a first-time contributor met 250 lines of engine-boundary
archaeology before reaching "how do I run the tests".

`docs/` held 21 canonical contract documents and no index at all —
`mkdocs.yml` publishes only `docs/user-guide/`, so a contributor entering the
repository directly had no map of them. ADRs 0027, 0030, 0033, 0040, and 0042
each state, as part of their Consequences, that the contract they introduce
"is linked from `CLAUDE.md`, `CONTRIBUTING.md`" (and a third file for
CLI-surface contracts) — a discoverability guarantee enforced by 17 tests
across `tests/test_engine_contract.py`, `tests/test_workflows.py`, and
`tests/test_reference_client_boundary.py`.

## Decision

1. **Add `docs/README.md` as the canonical contract index.** One line per
   contract document, grouped by CLI surface / engine boundary / filesystem
   and tests / validation records / process and security, plus pointers to
   `docs/adr/README.md`, the roadmap directories, and `docs/user-guide/`.

2. **Strip `CLAUDE.md` to what guides a decision.** Keep what this is, the
   repository relationship, the architecture and module-boundary rules, the
   six invariants, the coding conventions, the out-of-scope list, current
   state, and gotchas — target roughly 150 lines. Delete the historical
   narrative sections entirely; they are recoverable from `docs/adr/` and
   `docs/roadmap-v*/`.

3. **Add a "Change process" section to `CLAUDE.md`.** State the loop this
   repository actually runs: plan and surface every open question first,
   decide whether the change needs an ADR, move any canonical contract with
   the behaviour it describes, implement, verify (`poe check`, plus
   `network`/`e2e`/`check:wheel` where they apply), then branch, commit,
   PR, wait for green, squash-merge. This did not exist as written guidance
   anywhere in the repository before this record.

4. **Rewrite `CONTRIBUTING.md` for a first-time contributor.** Reorder around
   the actual task sequence — getting set up, making a change, running the
   three test tiers, opening a PR, what CI runs — before the maintainer-only
   sections (releasing, dependency floors, workflow security). Delete the
   architecture-decision narrative and the roadmap history; point at
   `docs/README.md` and `docs/adr/` instead of restating their contents.

5. **Retarget the 17 link-audit guards at `docs/README.md`.** Each guard in
   `tests/test_engine_contract.py` and the ADR-0024 guard in
   `tests/test_reference_client_boundary.py` that checked `CLAUDE.md` and
   `CONTRIBUTING.md` for a contract's link now checks `docs/README.md`
   instead (CLI-surface contracts keep their second entry point,
   `docs/cli-conventions.md`; `docs/integration-contract.md` and
   `docs/end-to-end-tests.md` keep theirs). This partially supersedes the
   "linked from `CLAUDE.md`, `CONTRIBUTING.md`" clause in ADRs 0027, 0030,
   0033, 0040, and 0042's Consequences — those records stay `Accepted`; only
   that one clause is overturned. `tests/test_workflows.py`'s two guards over
   `workflow-security.md` and ADR 0037 are unchanged: the slim `CLAUDE.md`
   and `CONTRIBUTING.md` still cite both inline in invariant 6.

6. **Tighten `README.md`'s prose without changing its facts.** It still
   describes published `0.3.2` behaviour, which is what a user can actually
   install; the engine-default cutover on `main` remains unreleased and out
   of scope for this record.

## Consequences

- `docs/README.md` is added; every canonical contract in `docs/` is now
  reachable from one maintained index rather than duplicated prose in two
  files.
- `CLAUDE.md` and `CONTRIBUTING.md` are both rewritten in place — same
  filenames, same purpose, roughly a quarter of their previous length.
- `tests/test_engine_contract.py` gains a `DOCS_INDEX` constant; its 14
  link-audit guards and `tests/test_reference_client_boundary.py`'s ADR-0024
  guard are retargeted accordingly. No new test is added — the existing
  guards keep doing their job against the new entry point.
- Future contract-introducing ADRs should say "linked from `docs/README.md`"
  (plus any CLI-surface third entry point), not "`CLAUDE.md`,
  `CONTRIBUTING.md`".
- This changes no runtime behaviour, no dependency, and no version — it is a
  documentation-and-test-fixture change only.
