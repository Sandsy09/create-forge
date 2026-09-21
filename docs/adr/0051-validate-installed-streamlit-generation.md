# 51. Validate Streamlit through the installed create-forge candidate

## Status

Accepted

## Context

[Issue #166 / CF-21.02](https://github.com/Sandsy09/create-forge/issues/166)
is the second child of
[CF-EPIC-21](https://github.com/Sandsy09/create-forge/issues/154). CF-21.01
([ADR 0050](0050-adopt-the-0-6-streamlit-provider-line.md)) adopted the
reviewed `forge-template 0.6.0` Streamlit provider line and proved selection
in-process: the generic parity suite, a named discovery tripwire, a guard that no
production module names `streamlit`, and real interactive and non-interactive
`new` runs with the lock and Git lifecycle faked. Nothing yet joins the built
create-forge wheel and the published engine through the *installed* console and
runs what they generate.

The provider already proves the archetype at its own boundary: the four accepted
selections across Python 3.11 and 3.14, the wheel and sdist contents, the
`run` task staying outside `check`, the secret safeguards, the listen guard,
and the 10-second per-run and 600-second whole-check bounds
([forge-template's acceptance contract](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-compatibility-and-acceptance.md)).
That contract assigns the client the rows this issue delivers: the installed
console generating all four compositions from published artefacts with committed
lock restoration and the bounded smoke, and incompatible providers, invalid
selections, lock failures and destination conflicts leaving no partial project
or staging state. The roadmap adds two constraints: generated-project details
must be *linked* to the provider, not duplicated (CF-ROADMAP-02-AC-03/AC-07),
and no Streamlit content or validation may live in this repository
(CF-ROADMAP-02-EX-01).

One constraint is a timing one. The user guide describes released behaviour and
deploys from `main` on any push touching `docs/user-guide/**`, but published
`create-forge 0.4.0` declares `forge-template>=0.5,<0.6` and cannot select
Streamlit. A guide page merged and deployed now would give users a command that
fails until CF-21.03 releases.

## Decision

1. **Add one self-contained installed suite.**
   `tests/test_e2e_installed_streamlit.py` reuses the shared harness
   (`tests/installed_client.py`) and the session `installed_client` fixture
   (candidate wheel plus exactly `forge-template 0.6.0`). The Data Science and
   rollout modules are not edited, so the existing archetype and Copier suites
   (CF-ROADMAP-02-AC-06) stay exactly as they were; the few neutral helpers the
   new file needs are duplicated, as the rollout suite already does. The harness
   gains one keyword-only `timeout` on `run`, defaulting to the existing value.

2. **Cover all four accepted compositions at the default interpreter, and the
   heaviest at both window edges.** Streamlit alone, with `jupyter`, with
   `scientific-python`, and with both, each at Python 3.13; the full composition
   again at 3.11 and 3.14. This mirrors the Data Science suite. The provider's
   only real Streamlit defect was interpreter-dependent and invisible to
   resolution alone, so the client's own lock finalisation is exercised at both
   edges.

3. **Prove only what the client owns.** Each composition generates twice with
   byte-identical output including the client-finalised `uv.lock`; the lock passes
   `uv lock --check`; every written byte matches the installed pipeline's own
   ownership plan; neither Forge distribution appears in the project or its lock;
   the project restores with `uv sync --all-groups --locked`, passes
   `uv run --locked poe check`, and passes its generated smoke
   (`tests/test_app.py`) run explicitly. The check and the smoke run under the
   provider's 600-second bound; a timeout is a failure and is never retried, and
   the bound is never raised here. No `streamlit run` is started. Wheel and sdist
   contents, task definitions, secret handling and the listen guard are **not**
   re-audited: they are the provider's, and are linked from the validation record.

4. **Use the previous engine line as the incompatible provider.** A real
   `forge-template 0.5.0` is forced into a second installed environment. It lacks
   `streamlit`, so it is the incompatible engine a Streamlit client most plausibly
   meets, and the range check must reject it at exit `3` before discovery and
   before any write, rather than let the user reach an "unknown archetype".

5. **Mirror the provider's rejection matrix, and add the two filesystem
   failures.** Through the installed console: Streamlit with `documentation`
   (which requires `library`), with `dependabot` and no `github` platform, with a
   component option it does not declare, and `streamlit` given as a capability.
   Also a non-empty destination, and a real, non-monkeypatched lock failure
   (`uv` removed from `PATH` after a successful render). Each asserts the exit
   code, an actionable message, no destination, and no `.create-forge-*` staging
   sibling. The engine's stable error code stays part of the asserted message.

6. **Prove interactive selection in-process, and installed-level by discovery.**
   The interactive archetype prompt is built from the discovered catalogue, and
   CF-21.01 already drives it against the real `0.6.0` engine. The installed
   console adds `create-forge list` showing `streamlit`, which reads the same
   data. No PTY-driven end-to-end test is built: the installed suites are
   non-interactive throughout, and a pseudo-terminal harness would be new
   cross-platform infrastructure with real flake risk (Windows in particular) for
   a path already covered.

7. **Exercise the documented recipes from one source.** The commands the guide
   documents live in `tests/streamlit_recipes.py`. An installed-console e2e test
   runs each verbatim (the launcher `uvx create-forge` becoming the installed
   console, from a clean working directory so the documented default destination
   is exercised) and then the documented check. `tests/test_user_guide_recipes.py`
   asserts the guide still says exactly those strings, links the provider's
   archetype contract rather than restating it, and that its relative links
   resolve.

8. **Ship the guide page excluded from the site until the release.**
   `docs/user-guide/streamlit.md` is written and tested now, and listed under
   `mkdocs.yml`'s `exclude_docs`, with no nav entry and no edit to any other guide
   page. The deployed site stays true for `0.4.0` users. The strict build does not
   see an excluded page, so the drift guard above checks its recipes and links.

9. **Change nothing under `src/`.** This is evidence and documentation.
   `docs/roadmap-v4/**` (hash-pinned against the filed issue bodies) and ADRs
   0001-0050 (immutable) are untouched.

## Consequences

- The e2e tier gains a sixth module. `poe test:e2e` (`pytest -m e2e`) and CI's
  `e2e` job pick it up with no workflow change; its measured runtime is recorded
  in [installed-streamlit-validation.md](../installed-streamlit-validation.md)
  against the job's 60-minute limit rather than assumed.
- The canonical [end-to-end tests contract](../end-to-end-tests.md) and the
  docs index gain the new validation record; a link-audit test keeps it
  discoverable, as for ADRs 0032, 0033 and 0048.
- **CF-21.03 inherits the guide's release work**: remove the `exclude_docs` entry,
  add the nav entry and a `projects.md` archetype row, update `site_description`,
  `installation.md` and `reference.md` (its "What's next" text and its
  `uv add "forge-template>=0.5,<0.6"` example), and choose the release version.
  Until then the guide keeps the `>=0.5,<0.6` range the published client
  actually declares. The provider's contract gates that issue on "documentation
  is deployed", which this shipping order is consistent with: the page is
  complete and tested beforehand, and deployed by the release that makes it true.
- Interactive selection remains proven in-process only. If a future issue needs
  installed-level prompt coverage for every archetype, a PTY harness is its
  decision to make, not a Streamlit-specific one.
- A provider change to the 600-second bound or to the acceptance matrix moves
  this suite deliberately: the constant carries a comment naming the provider
  contract that owns it.
