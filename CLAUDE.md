# CLAUDE.md — create-forge

Guidance for Claude Code working in this repository.

## What this is

`create-forge` is a CLI that scaffolds Python projects from Copier templates,
analogous to `pnpm create-payload-app`. It is a **thin wrapper**: Copier does the
rendering and merging, this tool owns the prompt experience and a bundled
registry of known templates.

Distributed via `uvx create-forge`. Public, MIT, intended for open-source use.

## Repository relationship

Two repositories, deliberately separate:

| Repo | Role |
| --- | --- |
| `https://github.com/Sandsy09/create-forge` | This repo. The CLI. |
| `https://github.com/Sandsy09/forge-template` | The templates it scaffolds from. |

They are split because Copier resolves template versions from PEP440 git tags in
the template repo. A shared repo would make `v1.3.0` ambiguous between the two
codebases. **Do not merge them.**

## Architecture

```
src/create_forge/
├── models.py       Pydantic v2 models for the registry. No I/O.
├── templates.toml  Bundled registry data. Package data, ships in the wheel.
├── registry.py     Loads + validates templates.toml. Cached.
├── config.py       User config (~/.config/create-forge/config.toml). NOT WIRED.
├── prompts.py      questionary flow. Driven entirely by registry data.
├── runner.py       The ONLY module that touches Copier's Python API.
└── cli.py          Typer app: new, list, update, doctor.
```

Dependency direction is one-way: `cli` → `prompts`/`runner`/`registry` →
`models`. Nothing lower imports anything higher.

## Invariants — do not break these

### 1. Registry prompt keys must exist in the template's copier.yml

Every `key` in a `[[templates.prompts]]` block must match a question in the
target template's `copier.yml`.

**This fails silently.** Copier ignores unknown keys passed via `data` — no
error, the answer vanishes, the template default applies. A typo produces a
scaffold that looks fine and is subtly wrong.

There is currently **no test guarding this**. Adding one is a priority task
(see backlog). It requires cloning the template repo, so mark it
`@pytest.mark.network`.

### 2. copier.yml is the source of truth for defaults

The CLI decides which questions get *asked*. It never redefines a question's
type, default, or validation. `runner.py` passes `defaults=True` so anything
unprompted falls back to the template. Adding a question to `copier.yml` must
never require a CLI change.

### 3. unsafe=True is load-bearing and dangerous

`runner.scaffold()` passes `unsafe=True` (the API form of `--trust`) because
templates declare `_tasks`. This executes code from whatever is cloned.

This is acceptable **only because template URLs are bundled** — they ship with
the reviewed release and cannot be altered at runtime. Do not add remote
registry fetching or config-based URL overrides without revisiting this. The
`--template-url` flag is the sanctioned escape hatch and prompts for
confirmation.

### 4. Copier's Python API is touched in exactly one place

`runner.py`. It is public but evolves faster than the CLI, hence the
`copier>=9.4,<10` pin. On a major bump, only that file should need attention.

### 5. templates.toml must ship in the wheel

Editable installs read from source; wheels do not. A missing registry passes
every local test and breaks on a user's first `uvx` run. Verify with:

```bash
uv run poe check:wheel
```

Run this before any release.

## Conventions

- Python 3.11+ (`tomllib`, `StrEnum`)
- mypy strict; ruff with `ANN` and `D` enabled
- Conventional Commits (enforced by pre-commit once set up)
- `from __future__ import annotations` everywhere
- Pydantic models are `frozen=True, extra="forbid"`
- Errors shown to users go through `runner._explain()` or are phrased for a
  reader who has never used Copier

## Current state

Working: all six modules written, registry validates, CLI structure complete.

Not yet done:
- `config.py` is written but **not imported by `cli.py`**
- No `tests/` directory at all
- No CI
- No pre-commit config
- No `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `LICENSE`
- No `docs/`
- No tags or releases

## Backlog, in order

See [docs/plan-v0.1.0.md](docs/plan-v0.1.0.md) for the phased roadmap covering
items 0-6 below (drift guard against `forge-template`'s `copier.yml`, test
suite, `config.py` wiring, repo hygiene, CI, ADRs, release) — written after a
`forge-template` session found a live bug here (`task_runner` still prompted
for after `forge-template` removed the question) and confirmed this CLI has
never been run end to end.

**0. Tag the template repo.** `create-forge new` cannot work until
`forge-template` has a PEP440 tag. Push `v0.1.0` there first — nothing in this
repo can be tested end to end before that.

**1. Test suite.** Nothing is tested. Start with:
- `tests/test_registry.py` — bundled registry validates; ids unique; default
  exists and is not deprecated
- `tests/test_models.py` — validator behaviour (select without choices,
  deprecated without successor, duplicate keys)
- `tests/test_cli.py` — Typer's `CliRunner` against `list`, `doctor`,
  `new --dry-run`, `new --yes`, bad `--data` format
- `tests/test_drift.py` — invariant 1, marked `network`

Assert the *resolved Copier invocation* by monkeypatching `runner.scaffold`,
rather than actually scaffolding. Keep the real scaffold in one network test.

**2. Wire `config.py` into `cli.py`.** In `new`, load config and merge
`as_answers()` into `preset` **beneath** any `--data` values, so precedence runs
config < `--data` < prompt. Handle `ValueError` from `load_config` as a user
error. Also surface config state in `doctor`.

**3. Repo hygiene.** pre-commit config, `CONTRIBUTING.md`, `SECURITY.md`,
`LICENSE`, `CHANGELOG.md`, `.gitattributes` (`* text=auto eol=lf` — the author
develops on Windows), issue and PR templates, CODEOWNERS.

**4. CI.** Lint, typecheck, test matrix over 3.11–3.13, plus a `check:wheel`
job. Mirror the workflow in the template repo.

**5. `docs/`.** MkDocs site. Include ADRs for the decisions already made:
two-repo split, Copier over Cookiecutter, bundled registry over remote,
Copier Python API over subprocess, scaffold-only scope, fork model for
organisations.

**6. First release.** Tag `v0.1.0`, verify `uvx --from git+... create-forge`
works from a clean machine, then consider PyPI.

## Deferred, with reasons

- **Remote registry override** — breaks the security property behind
  `unsafe=True`. Would need a signing or allowlist mechanism first.
- **GitHub repo creation and push** — deliberately out of scope. Would pull `gh`
  into the dependency tree and require the `workflow` OAuth scope, which is a
  confusing failure for users.
- **Interactive template browsing / search** — not useful with one template.

## Gotchas already hit

- `gh` pushes fail on `.github/workflows/**` without the `workflow` OAuth scope
  (`gh auth refresh -h github.com -s workflow`). Relevant if repo creation is
  ever added.
- `match spec.kind` in `prompts.py` compares against string literals while
  `PromptKind` is a `StrEnum`. Works at runtime; mypy strict may object. Prefer
  the enum members.
- The `--version` callback in `cli.py` uses a lambda with a tuple side-effect.
  Works, but should be a named function.