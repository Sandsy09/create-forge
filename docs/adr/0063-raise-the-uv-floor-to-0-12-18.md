# 63. Raise the uv floor past the wheel-extraction advisory

## Status

Accepted

## Context

[ADR 0038](0038-dependency-floor-review.md) reviewed the `uv` floor and held it
at `uv>=0.12,<0.13`. Its decision 2 rests on one fact, stated in its context:
"all five published uv advisories are fixed at ≤ `0.11.15`, so the entire
declared `>=0.12,<0.13` range is already advisory-free." That stopped being true.

[GHSA-2cv4-cqwr-gwf7](https://github.com/advisories/GHSA-2cv4-cqwr-gwf7)
(CVE-2026-104843, "uv: Path traversal on Windows through wheel extraction") is
fixed in `uv 0.12.18`, so the declared range admits `0.12.0` through `0.12.17`.
`uv run poe audit` found it as a `[runtime]` finding while the lock sat at
`0.12.16` ([#247](https://github.com/Sandsy09/create-forge/pull/247) refreshed
the lock to `0.12.23` and cleared it). A lock refresh fixes the audited graph
only: it does not change what the published wheel permits, which is what
[docs/dependency-audit.md](../dependency-audit.md)'s lower-bound review exists to
ask about.

The review has a concrete answer, from reading what `create-forge` runs:

- `new` invokes exactly one `uv` command, `uv lock --directory`
  (`staging.create_uv_lock`, [ADR 0021](0021-client-finalises-engine-lockfiles.md)).
  Locking resolves; it does not extract wheels, so the default path is not exposed.
- The opt-in `--engine-source`/`--engine-ref` route provisions an isolated
  environment with `uv venv` and `uv pip install` (`engine_source.py`), and
  `update` reproduces a recorded provider release the same way
  (`released_requirement`). Those do extract wheels.

Both of those installs fetch an *engine*, which the client then executes. A
hostile engine wheel therefore already has code execution, so the traversal does
not widen what that wheel can do. For `--engine-source` the user has also been
shown a code-execution warning and, unless `--yes` was passed, asked to confirm;
the recorded-release path installs a pinned release from PyPI and has no such
prompt. The marginal risk is small. The advisory is still a published
vulnerability in a range the package declares supported, and the fix costs
nothing: `uv` is `0.12.23` and `uvx` users always resolve the latest. A floor
that admits a known-vulnerable release for no benefit is the thing ADR 0038
decision 5 says to re-verify rather than assume.

[CONTRIBUTING.md](../../CONTRIBUTING.md#dependency-floors) says a new advisory
below a floor is handled "with a new ADR … before other release content", which
is why this lands ahead of the `0.6.0` release preparation rather than inside it.

## Decision

1. **Raise the floor to `uv>=0.12.18,<0.13`.** The upper bound is unchanged:
   this is not a compatibility-line crossing, and a `0.13` proposal remains a
   human decision ([ADR 0038](0038-dependency-floor-review.md) decision 3).
   `pyproject.toml`'s `[project.dependencies]` entry, the lock's recorded
   specifier, and `tests/test_engine_contract.py`'s `UV_REQUIREMENT` change
   together. The lock itself already resolves `0.12.23`.

2. **Supersede the premise of ADR 0038 decision 2, not the record.** ADR 0038 is
   immutable and stays as written; its decision to hold the floor was correct for
   the advisory record it reviewed. This record revises the number it cites, as
   ADR 0039 did for the Copier floor.

3. **Prove the floor in CI rather than assert it.** The existing `floor` job
   resolves every direct dependency at the bottom of its range
   (`--resolution lowest-direct`), so after this change it runs the fast suite
   under `uv==0.12.18`. That job is the evidence that the new floor resolves and
   that the supported commands work at it.

4. **Leave the install hints that quote `uv>=0.12,<0.13` unchanged.** Three
   messages tell a user without `uv` on `PATH` to "install uv>=0.12,<0.13"
   (`staging.py`, `lifecycle.py`, `engine_source.py`, asserted by
   `tests/test_lifecycle.py`). They are advice to obtain a supported major
   range, not the requirement, which the installer enforces when it resolves
   `create-forge`. One of them is in `staging.py`, which is part of the
   update-safety digest ([ADR 0054](0054-verify-installed-update-safety-on-the-release-candidate.md)):
   editing a hint string would force refreshing the installed update-safety
   evidence for no behavioural change. The imprecision is recorded here and
   corrected by the next change that touches those files for another reason.

5. **Do not move the CI `UV_VERSION` pin.** `ci.yml`, `linux-checks.yml` and
   `release.yml` pin `UV_VERSION: "0.12.0"` for the CI tooling and the audit
   scanner. That is a separate, deliberate move with its own checks
   ([docs/dependency-audit.md](../dependency-audit.md), "Maintaining the pin"),
   and the advisory concerns what a consumer's `uv` extracts, not the scanner.

## Consequences

- `create-forge 0.5.x` keeps declaring `uv>=0.12,<0.13`; the next release
  declares `uv>=0.12.18,<0.13`. A consumer installing into an environment with an
  older `uv` has it upgraded by the resolver.
- No shipped module changes, so the update-safety digest is untouched and no
  installed evidence needs refreshing.
- The audit stays clean: it already was, at the locked `0.12.23`. What changes is
  that the declared range no longer permits the finding the lower-bound review
  raised, so the question does not recur at the next release.
- The three install hints say `0.12` while the requirement says `0.12.18`. A user
  who follows a hint and installs `uv 0.12.0` will still be told by the installer
  that `create-forge` needs a newer one. This is accepted until those files are
  next touched.
