# 1. Record architecture decisions

## Status

Accepted

## Context

`CLAUDE.md` had accumulated a "do not break these" invariants section and a
handful of one-line justifications — the two-repo split, why `unsafe=True` is
load-bearing, why the Copier Python API is touched in exactly one place. Each
justification kept shrinking to fit alongside the growing invariants list, and
a rule stated without its reasoning cannot be argued with: a contributor who
disagrees, or a future maintainer who wonders if a decision still holds, has
nothing to check it against.

## Decision

Use Architecture Decision Records, as described by Michael Nygard in
[Documenting Architecture
Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

Each ADR is a numbered Markdown file in `docs/adr/`, with `## Status`,
`## Context`, `## Decision`, and `## Consequences` sections. Records are
immutable: once accepted, a decision is changed by writing a new ADR that
supersedes it, not by editing this one. `scripts/adr.py` (invoked by
`uv run poe check:adr`, and run as part of the fast test suite) checks that the
set stays internally consistent — filenames match `NNNN-slug.md`, numbers are
contiguous with no gaps or duplicates, every record is linked from
`docs/adr/README.md`, and every record has all four headings.

This is the same format `forge-template` uses for its own `docs/adr/` — see
its [ADR 0001](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0001-record-architecture-decisions.md)
— and the same format the `library` archetype gives scaffolded projects as
their own ADR 0001. Both repos in this project's ecosystem, and everything
either of them produces, record decisions the same way.

## Consequences

Anyone wanting to understand a past design decision reads the ADR instead of
reverse-engineering it from code, git history, or asking around. `CLAUDE.md`
keeps the operational rules and links out here for rationale, rather than
carrying both. Decisions that turn out to be wrong are recorded as history,
not silently erased.
