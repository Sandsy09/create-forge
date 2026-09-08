# 39. Diagnose the Copier template cache

## Status

Accepted

## Context

On a managed Windows laptop, `create-forge new` failed with Copier reporting a
cached path as "not a git repository", though the same mirror and worktree
worked when run by hand. Copier had already removed its temporary worktree by
the time the error was inspected. Pointing `COPIER_CACHE_DIR` at a usable
location fixed it.

That failure was unactionable in two places:

- `runner._explain` collapses every `plumbum.ProcessExecutionError` to one
  message naming the template URL, `--ref`, network, repository access and Git
  credentials. This is deliberate — argv and stderr may carry credentials
  ([ADR 0036](0036-template-source-credentials.md)) — but it sends a user with
  a broken cache to check their VPN.
- `doctor` reports whether `git` and `uv` are on `PATH`, but never names the
  cache directory, never says whether `COPIER_CACHE_DIR` is overriding it,
  never checks it is writable, and reports no `uv` version.

Two findings shaped the change.

**Copier's git-mirror cache and `COPIER_CACHE_DIR` were introduced in `9.16.0`.**
The floor [ADR 0038](0038-dependency-floor-review.md) set a day earlier is
`copier>=9.15.2`. At `9.15.2` Copier clones every template into a fresh
temporary directory, ignores `COPIER_CACHE_DIR`, and cannot produce this
failure — so every cache row `doctor` grows would be a lie at the bottom of the
supported range, and the CI `floor` job, which resolves exactly the floor,
could exercise none of it. ADR 0038's own rule permits the move: *a floor
moves on advisory or required-behaviour evidence*. The advisory record is
unchanged — re-queried at implementation time, `9.15.2` still clears it and the
whole `>=9.16` range is advisory-free.

**`plumbum.ProcessExecutionError` is a subclass of `OSError`.** An unwritable
or misdirected cache fails inside Copier at `mirror.parent.mkdir(...)` as a
plain `PermissionError` / `FileExistsError`, which `runner.scaffold` does not
catch — so it reaches the user as a raw traceback, breaking the "expected
failures are shown without a traceback" rule in
[`docs/cli-conventions.md`](../cli-conventions.md). Catching it needs an
`except OSError` clause *after* the existing
`except (CopierError, ProcessExecutionError)`, scoped so that only a failure at
the resolved cache path is translated and every other `OSError` re-raises
untouched.

Copier's cache-location resolver (`copier._vcs._get_cache_dir`) is private and
has moved between supported releases — `copier.vcs` is a deprecation shim in
`9.18.x`. `create-forge` cannot import it in shipped code (CLAUDE.md invariant
4; vendoring Copier internals is out of scope for this change). It instead
replicates the two-line documented rule in `runner.py` — the module invariant 4
already designates as the one place that models Copier behaviour — and a test
pins that replication to Copier's own resolver so a drift fails CI rather than
silently misreporting in `doctor`.

[ADR 0038](0038-dependency-floor-review.md) is immutable and unchanged. This
record revises the `copier` figure it set; it supersedes no decision — the
advisory review still stands, and `9.16` remains within it.

## Decision

1. **Raise the Copier floor to `copier>=9.16,<10`.** `9.16.0` is the first
   release with the git-mirror cache and `COPIER_CACHE_DIR`. The move is on
   required-behaviour evidence, not advisory evidence; the whole `>=9.16`
   range is advisory-free, and the upper bound is unchanged — this is not a
   compatibility-line crossing. `platformdirs` becomes a direct dependency,
   pinned at `>=4.3.6`, the bound Copier itself declares.

2. **Model Copier's cache-location rule in `runner.py`, and pin the model to
   Copier.** `copier_cache_location()` applies `COPIER_CACHE_DIR` verbatim
   when set and non-empty, else `<platformdirs user cache "copier">/git`.
   `tests/test_copier_cache.py` asserts it equals `copier._vcs._get_cache_dir`
   under both branches; that private import lives only in the test.

3. **Report the cache in `doctor`, and fail the check when it is not
   writable.** Human and `--json` output gain the resolved cache path, whether
   `COPIER_CACHE_DIR` overrides it, and a writability probe; `--json` also
   gains the `uv` binary path, its parsed `uv --version`, and the `engine`
   extra's declared `uv` version. An unwritable cache means the environment
   genuinely cannot scaffold, so that check reports `ok: false` and `doctor`
   exits `1`. The probe never creates the cache directory and never touches a
   `<sha>.git` mirror — it writes and deletes one uniquely named file in the
   cache directory or its deepest existing ancestor. `os.access` is not used:
   on Windows it ignores ACLs and reports a locked-down corporate directory as
   writable.

4. **Classify the cache condition from sanitised signals only, and never emit
   the process detail that produced them.** `runner._explain` treats a
   `ProcessExecutionError` as the cache condition only when its stderr
   contains the literal phrase `not a git repository` *and* names the resolved
   cache path (in stderr or argv, compared through `os.path.normcase`). A new
   `except OSError` clause in `scaffold` and `update` translates an error
   whose `filename` is under the cache path and re-raises every other
   `OSError`. Both surfaces emit only `create-forge`'s own resolved cache
   path — a local filesystem path `doctor` already prints — and the fixed
   `COPIER_CACHE_DIR` recovery guidance, never any part of argv, stdout or
   stderr. Authentication, network and missing-source failures never produce
   the phrase, so they keep the existing generic guidance.

5. **Recommend a fresh alternate cache, never deletion or permission
   changes.** The guidance points `COPIER_CACHE_DIR` at a new writable
   directory, in PowerShell and POSIX form, and explicitly says not to delete
   the existing one. `create-forge` performs no cache deletion, repair or
   permission change.

## Consequences

- A fresh `pip install create-forge` resolves `copier>=9.16`. Anyone on
  `9.15.x` upgrades on their next `create-forge` update; `platformdirs`, already
  a transitive dependency via Copier, becomes a direct one at the same bound.
- `create-forge` moves to `0.3.2`, a patch release whose user-visible changes
  are the raised `copier` floor and the new `doctor` output. Wheel metadata,
  the changelog and the installed console-script path are verified in that
  release.
- `doctor`'s `--json` schema is additive — `copier_cache` and `uv` objects are
  new; every existing field keeps its name and meaning. The only behavioural
  change is that a genuinely unwritable cache now flips `ok` to `false`.
- The CI `floor` job now resolves `copier==9.16.0` and so exercises the cache
  model, the writability probe and the classification at the advertised
  floor — where, before this change, none of that code path existed.
- `runner.py` now models one piece of Copier behaviour beyond the API call
  itself. The drift guard in `tests/test_copier_cache.py` is what keeps that
  model honest across Copier upgrades; a Copier change to the cache rule fails
  CI rather than silently making `doctor` wrong.
- This changes the advertised Copier floor, `doctor`'s output and one error
  classification. It does not cross the Copier compatibility line, change the
  engine range or protocol, vendor Copier internals, perform the engine
  cutover, or require a `forge-template` release.
