# 57. Prove the installed console under non-UTF-8 Windows settings

## Status

Accepted

## Context

[Issue #197 / CF-23.02](https://github.com/Sandsy09/create-forge/issues/197) is
the second and last child of
[CF-EPIC-23](https://github.com/Sandsy09/create-forge/issues/189). ADR 0055
(CF-23.01) fixed the mechanism -- every process this client starts is captured
as bytes and decoded by an explicit rule -- and proved it against synthetic
children. It deliberately left three things open: proving the **installed
console** under a *verified* non-UTF-8 Windows setting rather than one merely
assumed from `PYTHONUTF8`'s absence; reproducing five test failures a review
reported, named nowhere in the repository; and the CLI's own stdout/stderr
encoding, which ADR 0055 explicitly declined to touch.

Two things emerged from doing that work, neither anticipated by the issue as
filed:

- **Characterising the installed console found a real correctness bug.**
  `create-forge new` into a destination path containing a character outside
  the console's codepage (a CJK segment, on a `cp1252` host) raised
  `UnicodeEncodeError` from inside the success panel's `console.print` --
  *after* the project had already been written and committed. The mechanism:
  Rich decides whether a stream is a legacy Windows console by asking
  `GetConsoleMode`, which fails identically for a plain pipe (what every test
  harness, CI log, and many IDE run windows give it) and for a genuinely
  unsupported terminal; on that path it writes through the stream's own
  `.write`, i.e. `sys.stdout`'s default `errors="strict"`.
- **Exercising a real `--engine-source` failure found a second one.**
  `EngineSourceError` raised by `engine_source.provision()`'s own body, before
  it ever yields a runtime, reached the user as a raw, unhandled traceback:
  `with engine_source.provision(...) as runtime:` had nothing around it to
  catch an `__enter__`-time failure, unlike every other `EngineSourceError`
  site in the same function.

A third fact shaped how the harness itself is built: this development
environment's own shell layer sets `PYTHONIOENCODING=utf-8:surrogateescape` on
child processes for its own purposes -- present in one of the two tools used to
launch commands here, absent in the other, absent on a plain Windows install
and on a GitHub Actions `windows-latest` runner. Trusting whatever the invoking
shell happened to leave behind would make "ambient" mean something different on
every machine and defeat the point of a verified, not assumed, lane.

## Decision

1. **Three lanes, each checked against a probe, never assumed.** `ambient` (no
   override), `utf8-off` (`PYTHONUTF8=0`), `utf8-on` (`PYTHONUTF8=1`,
   `tests/encoding_lanes.py`). Both variables are cleared before a lane applies
   its own setting -- never left as whatever the invoking environment had. A
   probe runs the client's own interpreter and reports its actual
   `utf8_mode`/preferred encoding; a Windows non-UTF-8 lane whose probe
   resolves to UTF-8 **fails the test**, rather than silently passing under the
   wrong setting. Off Windows, the two non-UTF-8 lanes are not meaningful and
   are skipped; `utf8-on` runs everywhere as the control.

2. **Fix the console-encoding bug found while proving it, narrowly.**
   `cli._harden_console_encoding` reconfigures `sys.stdout`/`sys.stderr` to
   `errors="backslashreplace"`, called at the top of `main()` (Typer's group
   callback) rather than at import time, because `Console.file` resolves
   `sys.stdout`/`sys.stderr` fresh on every print and a test harness (or a
   real invocation) may swap those streams after this module is first
   imported. This is the narrowest fix available: it touches two lines'
   worth of behaviour, does not force `legacy_windows=False` (which would
   also change real-terminal ANSI handling), and degrades only text a stream
   genuinely cannot encode -- ordinary ASCII and `cp1252`-representable
   content (`Café`, unlike `项目`) is unaffected. It also protects a second,
   independent case for free: `decode_diagnostic`'s own substitution
   character (`U+FFFD`) is itself outside `cp1252`.

3. **Fix the provisioning-failure bug found the same way.** The bare `with
   engine_source.provision(requirement) as runtime:` becomes `with
   contextlib.ExitStack() as stack: runtime = stack.enter_context(...)`
   inside its own `try`/`except EngineSourceError`, so a failure before the
   runtime exists is explained exactly like every later failure in the same
   function, and the environment is still cleaned up exactly as the `with`
   form would have on any later failure.

4. **Fault injection favours real processes over monkeypatching, going one
   step further than ADR 0055's own synthetic-child tests.** A `git`/`uv`
   shim (`tests/fake_tools.py`) is a small wheel installed into its own
   venv, so `uv` generates real Windows-native launcher executables --
   `CreateProcess` finds those by a bare name; a `.cmd`/`.bat` file is not
   reliably found the same way. It delegates to the real tool except for one
   diagnostic subcommand or `git commit`, which it corrupts or fails on
   purpose. A `forge_template` look-alike engine (also a hand-built wheel,
   no build backend, no network) lets `--engine-source` provision it and
   corrupt the worker's `info` response four ways, proving
   `capture.parse_protocol_json`'s strict rejection through the real
   out-of-process worker rather than a monkeypatched `subprocess.run`.

5. **CI: the Python window's edges plus the default, not the whole matrix.**
   A new job, `windows-latest`, matrix `3.11`/`3.13`/`3.14`, running only
   `tests/test_e2e_installed_encoding.py` -- the same "edges, not the whole
   window" reasoning `test_e2e_installed_cutover.py`'s and
   `test_e2e_installed_streamlit.py`'s own `_PYTHON_WINDOW_EDGES` already use
   for the identical `build_client(python=...)` mechanism; the window's
   interior is proven by the `test` job's own full matrix and `floor`. No
   `PYTHONUTF8`/`PYTHONIOENCODING` is set in this job or any other --
   `tests/test_installed_encoding_guard.py` fails if either ever is, making
   "no forced UTF-8 workaround is required" an executable claim rather than a
   sentence. The module carries no restriction that would keep it out of the
   existing Linux `e2e` job (`poe test:e2e`), where it runs too, as a UTF-8
   control with the Windows-only lanes skipped.

6. **The five reported failures: sought again, not just cited as
   unreproduced.** ADR 0055 could not reproduce them on `main`. This issue
   sought them at `c9a33cc` -- the commit closest to when the review that
   reported them is dated -- under the same ambient `cp1252` setting, in a
   throwaway worktree, running the fast suite and every e2e module that
   existed at that commit. None reproduced there either.
   `docs/installed-encoding-validation.md` records the disposition, including
   the two suites that did not exist yet at that commit and so could not have
   been among the original five. What reproduces consistently, at every
   commit checked, is the mechanism ADR 0055 already fixed.

## Consequences

- `cli.py` gains `_harden_console_encoding` (called from `main()`) and the
  `ExitStack`-based provisioning fix in `_run_engine_source`. Both are
  outside the update-safety source digest's hashed set
  (`scripts/candidate_evidence.py`), so neither forces a refresh of that
  evidence.
- Two new fast regression tests (`tests/test_cli.py`,
  `tests/test_engine_source.py`) pin each fix independently of the Windows-only
  e2e evidence; both were confirmed to fail against the prior code before the
  fix landed.
- New test-only modules: `tests/encoding_lanes.py`, `tests/fake_tools.py`,
  `tests/test_e2e_installed_encoding.py`,
  `tests/test_installed_encoding_guard.py`. None are shipped; `pyproject.toml`
  is unchanged, no dependency, lock, or protocol changes.
- `docs/subprocess-output.md`'s "Reported failures" section, `docs/README.md`,
  `docs/end-to-end-tests.md`, and `docs/user-guide/updates.md` move from
  "left open for CF-23.02" to the resolved state; the new canonical
  [installed-encoding-validation.md](../installed-encoding-validation.md)
  record is linked from all of them plus this ADR's own contract.
- No release is cut for this issue by itself; the two fixes ship in whatever
  release follows.
- **Out of scope, unchanged:** a console redesign, new Python-version support,
  macOS, Copier's own subprocess use through `plumbum`, `scripts/`, and any
  global forced-UTF-8 workaround. ADRs 0001-0056 are untouched.
