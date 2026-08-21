# Roadmap to v0.1.0

Written from `forge-template` on 2026-08-21, after that repo's issue #5
(pytest port) shipped and CI went green. Reproduced here so create-forge work
happens in this repo's own session, with this repo's own `CLAUDE.md` in
context — the two repos stay separate for the reasons in that file's
"Repository relationship" section.

## Context

`forge-template` is in good shape — four combos green in CI, `copier update`
validated, a real pytest suite, nine ADRs, `v0.1.1` tagged. `create-forge`, the
CLI that is the *only* documented way users are meant to consume it
(`uvx create-forge`), is a single `chore: initial repo setup` commit with no
tests, no CI, no tags, and no LICENSE.

That asymmetry is now actively costing us:

1. **A silent bug is already shipped.** `src/create_forge/templates.toml`
   prompts for `task_runner` (poe/make) — a question `forge-template`'s
   `copier.yml` *deleted* in its ADR-0008. Copier silently drops unknown `data`
   keys, so the answer vanishes; then `src/create_forge/cli.py:185` prints
   `make check` as the next step, a command no generated project has. This is
   precisely the failure `CLAUDE.md` invariant 1 describes, beside the note
   *"There is currently no test guarding this."*
2. **The CLI has never been run end to end.** Backlog item 0 was "tag the
   template repo — nothing here can be tested end to end before that." That
   cleared when `forge-template v0.1.0` landed and nobody cashed it in.
   `poe check` is broken today too: `testpaths = ["tests"]` with no `tests/`,
   and `license-files = ["LICENSE"]` with no LICENSE, so even `uv sync` fails.
3. **forge-template's archetype-two work forces a change here regardless.**
   `Template` in `models.py` is `frozen, extra="forbid"` with only `url` +
   `prompts` — there is no way to express "same repo, second archetype". A
   second archetype needs either a `subdirectory`/`data` field on the model or
   an `archetype` prompt that duplicates the CLI's own template picker.
   Designing that against an untested CLI is designing blind.

Outcome: a `create-forge` that is tested, CI-gated, hygienic, and tagged
`v0.1.0`, with a **drift guard** that makes the class of bug in (1) impossible
to ship again.

### Decisions taken

- **Full pass, to a releasable v0.1.0** — not a minimal contract fix.
- **The drift guard runs in CI *and* on a weekly cron.** The cron is
  load-bearing: `forge-template` moves independently, so a push-only test would
  not have caught `task_runner` for months.
- **The CLI prompts for `license`**, keeping `copier.yml`'s `proprietary`
  default rather than diverging from direct `copier copy` users.

### Finding to carry into archetype two

`_subdirectory` **is** Jinja-rendered — `copier/_main.py:1237`,
`subdir = self._render_string(self.template.subdirectory)`. So
`_subdirectory: "template/{{ archetype }}"` works, and because Copier tracks
paths *relative to the subdirectory root*, moving `template/*` →
`template/library/*` is path-stable for existing projects — that work may need
no `_migrations` at all, provided `archetype` defaults to `library`. Verify
empirically then; recorded here so it is not rediscovered.

---

## Phase 0 — Ground truth before changing anything

`uv sync` will fail on the missing LICENSE, so create that first (MIT, matching
`license = "MIT"` in `pyproject.toml`), then run the CLI for real against the
tagged template and **record what actually happens**:

```bash
uv run create-forge doctor
uv run create-forge new "Smoke Test" --yes --path /tmp/cf-smoke
```

Expected: scaffolds, `task_runner` silently dropped, `make check` printed. Do
not fix anything until the baseline is observed — the point is to learn how many
of the assumed bugs are real and whether there are others.

## Phase 1 — Unblock and fix known drift

Files: `LICENSE` (new), `.gitattributes` (new), `src/create_forge/templates.toml`,
`src/create_forge/cli.py`.

- `LICENSE` — MIT. Unblocks `uv sync`, `uv build`, and `poe check:wheel`.
- `.gitattributes` — `* text=auto eol=lf`. `forge-template` learned this the hard
  way (its invariant 5); the author develops on Windows and this repo has none.
- Remove the `task_runner` prompt block from `templates.toml`; drop the `make`
  branch at `cli.py:185` so the next-step panel always says `uv run poe check`.
- Add a `license` select prompt (Proprietary / MIT / Apache-2.0), default
  `proprietary` to match `copier.yml`.
- **Audit every registry key against `copier.yml` in both directions** and leave
  a comment naming the intentional omissions. Currently unasked and falling
  through to template defaults: `package_name`, `repo_name`, `author_name`,
  `author_email`, `codeowners_team`, `python_version`, `python_min_version`,
  `initial_version`, `coverage_fail_under`, `dependency_updates`,
  `changelog_tool`. All have defaults, so `defaults=True` is safe — but that
  safety is currently accidental, and Phase 2's drift test will assert it.

## Phase 2 — Test suite (backlog item 1)

New `tests/`, following `forge-template`'s established shape (fast suite by
default, slow/networked behind a marker — `network` is already registered in
`pyproject.toml`).

| File | Covers |
| --- | --- |
| `tests/test_models.py` | `PromptSpec._choices_match_kind`, `should_ask`, `Registry._default_exists_and_is_usable`, `_ids_unique`, `_prompt_keys_unique`, duplicate/deprecated cases |
| `tests/test_registry.py` | bundled registry loads and validates; ids unique; default exists and is not deprecated |
| `tests/test_config.py` | `load_config` precedence (file < env), malformed TOML raises *with the path*, `_blank_is_unset`, `write_example` never overwrites |
| `tests/test_prompts.py` | `slugify`, `ask_all` skips preset keys, `depends_on` gating, `choose_template` single-template shortcut |
| `tests/test_cli.py` | Typer `CliRunner` over `list`, `doctor`, `new --dry-run`, `new --yes`, bad `--data`, unknown `--template` |
| `tests/test_drift.py` | **the invariant guard** — `@pytest.mark.network` |

`test_cli.py` **monkeypatches `runner.scaffold` and asserts the resolved
`ScaffoldRequest`** rather than actually scaffolding — that is this repo's own
stated intent, and it makes the fast suite genuinely fast. `ScaffoldRequest` is
already `frozen, slots=True`, so it compares cleanly.

**`tests/test_drift.py`** is the piece that makes all of this worth doing, and
the direct answer to invariant 1's "there is currently no test guarding this":

- Shallow-clone `forge-template` at **the latest PEP440 tag** — what
  `vcs_ref=None` actually resolves to for users — not `main`. Parse its
  `copier.yml` with `yaml.safe_load`.
- Assert every registry prompt `key` exists as a question. *(Fails today on
  `task_runner`; must pass after Phase 1.)*
- Assert every question the CLI does **not** ask has a `default` or
  `when: false`, so `defaults=True` can never leave one unanswered.
- Assert `depends_on` mirrors the template's `when:` — only for the simple
  `{{ x == 'y' }}` form, skipping anything more complex rather than pretending
  to parse arbitrary Jinja.

Clone via `git` in the test, not through `runner.py` — invariant 4 reserves
Copier's API for that module, and a shallow clone is not a Copier operation.

## Phase 3 — Wire `config.py` into `cli.py` (backlog item 2)

`config.py` is fully written and **imported by nothing**, which makes the
`github_org` prompt's help text ("Pre-filled from your forge config if set") a
lie today.

In `new`: `load_config()`, catch `ValueError` as a user error (exit 1), and
surface config path + loaded keys as a `doctor` row.

**One refinement on the backlog's wording.** It says to merge `as_answers()`
into `preset`, but `ask_all` *skips* prompting for anything in `preset` — so a
configured `github_org` would suppress the question entirely, while `README.md`
promises it "pre-fills prompts". These want to be two different channels:

- `--data` → `preset`: suppresses the prompt (explicit, non-interactive intent)
- config → a new `defaults` mapping on `ask_all`: pre-fills, still asks

Precedence stays config < `--data` < prompt, as intended. This is a small
signature change to `ask_all` / `_resolve_default` in `prompts.py`.
Config's `default_template` should also be honoured when neither `-t` nor an
interactive pick applies.

## Phase 4 — Repo hygiene (backlog item 3)

Mirror `forge-template`'s root, which is the known-good reference:

- `.pre-commit-config.yaml` — same hooks as forge-template's, minus `shellcheck`
  (no `scripts/` here): whitespace/EOF/`check-toml`/`check-yaml`,
  `ruff-check --fix`, `ruff-format`, `uv-lock`, `conventional-pre-commit` on
  `commit-msg`.
- `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` (git-cliff is already
  configured in `pyproject.toml`).
- `.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`.
- **`README.md` fixes**: lines 41-42 list "task runner" among remembered
  choices — now untrue; the `SECURITY.md` / `CONTRIBUTING.md` / `LICENSE` links
  are broken until this phase creates them.
- The two gotchas `CLAUDE.md` already records: the `--version` lambda with a
  tuple side-effect (`cli.py:60`) becomes a named function, and `match spec.kind`
  compares `PromptKind` members rather than string literals (`prompts.py:100`).

## Phase 5 — CI (backlog item 4)

New `.github/workflows/ci.yml`, mirroring `forge-template`'s
`test-template.yml` shape (pinned `UV_VERSION`, `setup-uv@v5`, `concurrency`,
`permissions: contents: read`, an `all-green` aggregate job for branch
protection):

| Job | Runs |
| --- | --- |
| `lint` | `uv run pre-commit run --all-files`, `uv run poe typecheck` |
| `test` | matrix 3.11 / 3.12 / 3.13, `uv run poe test` (`-m 'not network'`) |
| `wheel` | `uv run poe check:wheel` — invariant 5, the failure that passes locally and breaks on first `uvx` |
| `drift` | `uv run pytest -m network` — **also on `schedule: cron "0 6 * * 1"`** |
| `all-green` | aggregate required check |

Fix `check:wheel` while wiring it: it is
`shell = "uv build && python -m zipfile -l dist/*.whl | grep templates.toml"` —
the pipe masks `uv build`'s exit code, and `dist/*.whl` glob expansion is
unreliable under Windows `sh`. Replace with a small Python check.

## Phase 6 — ADRs (backlog item 5, partial)

`docs/adr/` with the decisions `CLAUDE.md` already names as unrecorded: two-repo
split, Copier over Cookiecutter, bundled registry over remote, Copier's Python
API over subprocess, scaffold-only scope (no repo creation), and the fork model
for organisations. Same Nygard format and `README.md` index as
`forge-template`'s `docs/adr/`.

Add a slim `tests/test_adr.py` for filename/numbering/index consistency —
`forge-template`'s `src/forge_template/adr.py` is the reference, but port a
trimmed version rather than depending across repos.

**MkDocs site deferred** — file an issue. ADRs as plain Markdown are enough, and
a docs site is a standing maintenance commitment given the MkDocs 2.0
uncertainty in `forge-template`'s ADR-0007.

## Phase 7 — Release v0.1.0 (backlog item 6)

- `.github/workflows/release.yml` — port `forge-template`'s
  (`workflow_dispatch`, bump choice, `dry_run`, annotated tag + GitHub release).
  Drop its `_migrations` warning step, which is template-specific.
- Tag `v0.1.0`, then verify from a clean environment:
  `uvx --from git+https://github.com/Sandsy09/create-forge@v0.1.0 create-forge new`.
- **PyPI deferred** — file an issue. Tag + `uvx --from git+…` proves the
  packaging; PyPI adds trusted-publishing setup and a name claim, and is a
  separate decision.

---

## Verification

```bash
uv run poe check                 # format, lint, typecheck, fast tests
uv run poe check:wheel           # templates.toml ships in the wheel
uv run pytest -m network -v      # the drift guard, against the real tag
uv run pre-commit run --all-files
```

Beyond green exit codes:

1. **The drift guard actually fires.** Re-add the `task_runner` prompt to
   `templates.toml`, confirm `test_drift.py` fails, revert. A guard that has
   never been seen to fail is not a guard.
2. **End-to-end, for real.** `create-forge new` against the tagged template
   produces a project whose own `uv run poe check` passes, and whose
   `.copier-answers.yml` records `_commit` as the tag. This has never once been
   done.
3. **`create-forge update` works.** Scaffold from `forge-template v0.1.0`, tag
   it `v0.1.2`, run `create-forge update`, confirm the merge lands. Exercises
   `runner.update`, which no test path currently reaches.
4. **CI green on the real run** — `gh run view`, not a local exit code.

Natural commit boundaries are one per phase. Phases 0–2 are the ones that
de-risk archetype two; if the work is cut short, cut it after Phase 2 rather
than mid-phase.

## Issues to file first (this repo has none)

- MkDocs documentation site (Phase 6 deferral)
- PyPI publishing (Phase 7 deferral)
- Registry support for multiple archetypes in one template repo — blocks, and is
  blocked by, `forge-template#4`
- Add Python 3.14 to the CI matrix and classifiers (`forge-template`'s
  `python_all` already includes it; this repo stops at 3.13)

---

## Not in scope

- **Any change under `forge-template/`.** Its `CLAUDE.md` backlog still shows
  #4 as next; a note there that this precedes it would be a separate one-line
  edit in that repo, on the author's say-so.
- **forge-template #1, #6, #7, #8** — untouched.

**Pushes use explicit HTTPS URLs** (`git push https://github.com/... main`)
until the SSH key passphrase is sorted, leaving `origin` on SSH.

---

## Phase 0 — observed baseline (2026-08-21)

Run before any fix, on Windows, against `forge-template@v0.1.1`.

1. `LICENSE` added (MIT) — this alone was enough to unblock `uv sync`, which
   then resolved and checked 49 packages with no other errors.
2. `create-forge --version` → `0.1.0`. `create-forge list` → renders the single
   `library` template correctly.
3. **New finding, not anticipated by this plan:** `create-forge doctor` crashes
   with `UnicodeEncodeError: 'charmap' codec can't encode character '✓'`.
   Rich renders the ✓/✗ check marks in the doctor table; the Windows console is
   on the `cp1252` codepage, which cannot encode them, and Rich's legacy-Windows
   render path lets the exception propagate instead of falling back to ASCII.
   Unrelated to the registry drift this plan targets — filed as its own issue
   rather than fixed here, to keep this change scoped to Phase 1's stated diff.
4. `create-forge new "Smoke Test" --yes --data project_description=smoke --path …`
   → **succeeded**, exit 0, full scaffold + `uv sync` + pre-commit install
   inside the generated project. `.copier-answers.yml` confirms:
   - `_commit: v0.1.1` — resolves to the latest tag, as expected.
   - **`task_runner` is absent from the answers file** — confirms the drift:
     the CLI's prompt answer for this key is silently dropped by Copier because
     `forge-template`'s `copier.yml` has no such question.
   - `license: proprietary` — confirms the second defect: never prompted, so
     it silently takes the template default every time. The generated `LICENSE`
     file is the Proprietary boilerplate, not MIT, confirming this is a real
     content difference and not just an unused answer.
   - The next-step panel already read `uv run poe check`, not `make check` —
     because `--yes` mode sets `answers = preset` directly (never calls
     `ask_all`), and `task_runner` was never in `preset` to begin with. So the
     `cli.py:185` bug is latent, not visibly triggered by this non-interactive
     path — it would only surface for a user who runs `new` interactively,
     picks "Makefile" at the `task_runner` prompt, then has that answer
     silently discarded while the panel still keys off the (dropped) value.
     Confirms fixing `cli.py:185` is still correct and necessary even though
     this particular run didn't visibly hit it.

No other discrepancies observed. Proceeding to Phase 1 as planned, plus filing
the `doctor` Unicode crash as an additional issue (not in the original ten).
