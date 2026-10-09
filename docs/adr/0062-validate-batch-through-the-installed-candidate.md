# 62. Validate batch through the installed create-forge candidate

## Status

Accepted

## Context

[Issue #205 / CF-29.02](https://github.com/Sandsy09/create-forge/issues/205)
is the second child of
[CF-EPIC-29](https://github.com/Sandsy09/create-forge/issues/192).
CF-29.01 ([ADR 0061](0061-adopt-the-0-7-batch-provider-line.md)) adopted the
reviewed `forge-template 0.7.0` batch provider line and proved selection
in-process: the generic parity suite, a named discovery tripwire, a guard that
no production module names `batch`, and real interactive and non-interactive
`new` runs with the lock and Git lifecycle faked. Nothing yet joins the built
create-forge wheel and the published engine through the *installed* console and
runs what they generate.

The provider already proves the archetype at its own boundary: the four accepted
selections across Python 3.11 and 3.14 (eight cells), each restoring from a
committed lock, passing the generated project's `poe check` inside a 600-second
bound, running the job through both entry points, and building and installing a
wheel and sdist
([forge-template's acceptance contract](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-compatibility-and-acceptance.md)).
That contract assigns the client the rows this issue delivers: the installed
console generating the accepted compositions from published artefacts with
committed-lock restoration and the bounded smoke, and incompatible providers,
invalid selections, lock failures and destination conflicts leaving no partial
project or staging state — plus "existing archetype, default and legacy paths
unchanged". The issue adds installation modes, engine-native update with
local-data preservation, and Windows/non-UTF-8 and Linux coverage, and requires
generated-project detail to be *linked* to the provider, not duplicated.

Four facts shape the design, each measured rather than assumed:

- The catalogue accepts **640** batch compositions, not four. The provider's own
  endpoint sweep uses four selections (none, `jupyter`, `scientific-python`,
  both). Running all 640 through an installed console would be hours of locks and
  syncs for no client-owned property the four do not already exercise.
- The generated job pins `encoding="utf-8"` and writes ASCII-safe JSON, so the
  Windows codepage safety of the *job* is the provider's. The client-owned
  hazard is non-ASCII names and paths through staging
  ([ADR 0057](0057-prove-the-installed-console-under-non-utf8-windows-settings.md)).
- Batch declares **no runtime dependency**, so the job runs with plain
  `python -m <package>` and no environment sync.
- `0.7.0` is the first release containing `batch`, so there is no older batch
  render to differ from: a real cross-version three-way merge cannot be
  exercised until a batch change ships in an `0.7.x` patch.

One constraint is a timing one, as for
[ADR 0051](0051-validate-installed-streamlit-generation.md). The user guide
describes released behaviour and deploys from `main` on any guide change, but
published `create-forge 0.5.0` declares `forge-template>=0.6,<0.7` and cannot
select `batch`. A guide page deployed now would give users a command that fails
until CF-29.03 releases.

The provider's FT-28.03 hand-off also left a comparison open: the
released-client byte comparison its pairing tier made for `0.6.0` cannot be made
across the two lines, because the released client refuses the newer engine. It
names CF-29.01; ADR 0061 placed it here, where it belongs under "retain existing
archetype coverage".

## Decision

CF-29.02 ships as two pull requests under the one issue. This record covers
both so that its decisions are made once; each decision names the pull request
that delivers it.

1. **Add one self-contained installed suite** (PR A).
   `tests/test_e2e_installed_batch.py` reuses the shared harness
   (`tests/installed_client.py`) and the session `installed_client` fixture
   (candidate wheel plus exactly `forge-template 0.7.0`). Existing modules are
   not edited for this, so the existing archetype and Copier suites stay exactly
   as they were; the few neutral helpers the new file needs are duplicated, as
   the rollout and Streamlit suites already do.

2. **Cover the provider's four accepted compositions at the default interpreter,
   and the heaviest at both window edges** (PR A). Batch alone, with `jupyter`,
   with `scientific-python`, and with both, each at Python 3.13; the full
   composition again at 3.11 and 3.14. The remaining axes of the 640 are
   provider-owned.

3. **Prove only what the client owns** (PR A). Each composition generates twice
   with byte-identical output including the client-finalised `uv.lock`; the lock
   passes `uv lock --check`; every written byte matches the installed pipeline's
   own ownership plan; neither Forge distribution appears in the project or its
   lock; the project restores with `uv sync --all-groups --locked`, passes
   `uv run --locked poe check`, and passes its generated smoke
   (`tests/test_job.py`) run explicitly, under the provider's 600-second bound
   (a timeout is a failure, never retried, and the bound is never raised here).
   The example job then runs from the project root through **both** its console
   script and `python -m`, and the client asserts only that each exits `0`,
   produces the output file with the sample input's record count, and that the
   two entry points agree byte for byte. The transformation, the idempotency and
   fail-fast contract, the sample input, and the wheel and sdist contents are
   **not** re-audited: they are the provider's, and are linked from the
   validation record.

4. **Use the previous engine line as the incompatible provider** (PR A). A real
   `forge-template 0.6.0` is forced into a second installed environment. It lacks
   `batch`, so it is the incompatible engine a batch client most plausibly meets.
   `new` must reject it at exit `3` before discovery and before any write, and —
   proving [ADR 0061](0061-adopt-the-0-7-batch-provider-line.md) decision 4 on the
   installed console — `doctor` must exit `1` naming the range while protocol
   negotiation still passes, so the failure is attributable to the package range
   alone.

5. **Mirror the provider's rejection matrix, and add the two filesystem failures**
   (PR A). Through the installed console: `batch` with `documentation` (which
   requires `library`), with `dependabot` and no `github` platform, with a
   component option it does not declare, and `batch` given as a capability. Also
   a non-empty destination, a real non-monkeypatched lock failure (`uv` removed
   from `PATH` after a successful render), and `--legacy --archetype batch`,
   which the Library-only Copier registry makes a contradiction the CLI refuses
   before touching the disk. Each asserts the exit code, an actionable message,
   no destination, and no `.create-forge-*` staging sibling.

6. **Prove interactive selection in-process, and installed-level by discovery**
   (PR A). The interactive archetype prompt is built from the discovered
   catalogue and CF-29.01 already drives it against the real `0.7.0` engine; the
   installed console adds `create-forge list` showing `batch`. No PTY-driven test
   is built, for the reasons ADR 0051 decision 6 gave.

7. **Exercise the documented recipes from one source** (PR A). The commands the
   guide documents live in `tests/batch_recipes.py`. An installed-console e2e
   test runs each verbatim (the launcher `uvx create-forge` becoming the
   installed console, from a clean working directory), then the documented check
   **and the documented run** — unlike a server archetype, batch's `run` task
   terminates, so it is a legitimate recipe step. `tests/test_user_guide_recipes.py`
   asserts the guide still says exactly those strings, links the provider's
   contract rather than restating it, and that its relative links resolve.

8. **Ship the guide page excluded from the site until the release** (PR A).
   `docs/user-guide/batch.md` is written and tested now, and listed under
   `mkdocs.yml`'s `exclude_docs`, with no nav entry and no edit to any other guide
   page. The deployed site stays true for `0.5.0` users. The strict build does
   not see an excluded page, so the drift guard above checks its recipes and
   links.

9. **Cover the supported installation modes** (PR B). The `uvx`, `uv tool
   install`, `pip install` and `[legacy]`-extra modes each resolve the required
   engine and generate `batch`, by giving the install-mode helpers an `archetype`
   argument that defaults to `library` so the existing cases are untouched. The
   isolated `--engine-source` route is exercised against the immutable public
   `forge-template` tags: `--engine-ref v0.7.0` generates, and `--engine-ref
   v0.6.0` exits `3` with nothing created.

10. **Cover Windows, non-UTF-8 and Linux under the accepted policy** (PR B). Batch
    cases join the encoding suite — a non-ASCII project name and description and
    a CJK destination path, under every lane (`ambient`, `utf8-off`, `utf8-on`),
    followed by running the job with plain `python -m` and no sync — so they ride
    the existing Windows Python 3.11, 3.13 and 3.14 jobs unchanged. The new
    module's non-composition subset is added to the hand-picked `e2e-windows`
    list, and a guard fails the fast suite if that entry is dropped. Linux runs the
    full module through the existing `-m e2e` job.

11. **Cover engine-native update, and record the one gap** (PR B). Using
    [ADR 0054](0054-verify-installed-update-safety-on-the-release-candidate.md)'s
    technique, batch cases prove a no-op update, a genuinely changed update that
    preserves a locally edited `job.py` and an untracked, ignored
    `data/output.json`, and `--dry-run` leaving the tree untouched. The existing
    containment and recovery suite is re-run, not duplicated. The real three-way
    merge across provider versions is **not** covered for `batch` and is recorded
    as such: it needs an older batch render, and `0.7.0` is the first.

12. **Make the released-client comparison** (PR B).
    `tests/test_e2e_installed_cross_line.py` installs published `create-forge
    0.5.0` (which resolves a `0.6` engine) and the candidate (with `0.7.0`) into
    separate environments, generates `library`, `cli`, `data-science` and
    `streamlit` from identical answers, and compares every file's bytes
    **excluding** `uv.lock` (the resolver's clock) and `.forge/generation.json`,
    which is compared after normalising the provider and client versions it
    records. Two positive controls: `0.5.0` still generates with its own line,
    and `0.5.0` refuses `batch` as an unknown archetype. This is also the proof
    that existing archetype output is unchanged by the line crossing.

13. **Change nothing under `src/`.** This is evidence and documentation.
    `docs/roadmap-v*/**` (hash-pinned against the filed issue bodies) and ADRs
    0001–0061 (immutable) are untouched.

## Consequences

- The e2e tier gains a module. `poe test:e2e` (`pytest -m e2e`) and CI's Linux
  `e2e` job pick it up with no workflow change; the Windows list, which is
  hand-picked, changes in PR B. Measured runtimes are recorded in
  [installed-batch-validation.md](../installed-batch-validation.md) against the
  jobs' limits rather than assumed.
- The canonical [end-to-end tests contract](../end-to-end-tests.md) and the docs
  index gain the new validation record; a link-audit test keeps it discoverable,
  as for ADRs 0032, 0033, 0048 and 0051.
- **CF-29.03 inherits the guide's release work**: remove the `exclude_docs`
  entry, add the nav entry and a `projects.md` archetype row, update
  `site_description`, `installation.md` and `reference.md` (its example
  `uv add "forge-template>=0.6,<0.7"` and "What's next" text), and choose the
  release version. Until then the guide keeps the `>=0.6,<0.7` range the
  published client actually declares.
- Interactive selection remains proven in-process only. If a future issue needs
  installed-level prompt coverage for every archetype, a PTY harness is its
  decision to make, not a batch-specific one.
- A provider change to the 600-second or 5-second bounds, or to the acceptance
  matrix, moves this suite deliberately: the constant carries a comment naming
  the provider contract that owns it.
- Covering four of 640 compositions is a deliberate bound, not an oversight. The
  client composes selections generically and holds no per-composition logic; if
  that ever changes, widening the sweep is the right response.
- The released-client comparison depends on `create-forge 0.5.0` remaining on
  PyPI at test time, as the rest of the e2e tier already depends on PyPI for the
  engine.
