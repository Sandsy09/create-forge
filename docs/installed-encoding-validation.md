# Installed Console Encoding Validation

This is the living evidence record for
[CF-23.02 / #197](https://github.com/Sandsy09/create-forge/issues/197), the
last child of [CF-EPIC-23 / #189](https://github.com/Sandsy09/create-forge/issues/189).
The decision is accepted under
[ADR 0057](adr/0057-prove-the-installed-console-under-non-utf8-windows-settings.md).

[CF-23.01](https://github.com/Sandsy09/create-forge/issues/196) fixed the
*mechanism* every process `create_forge` starts follows -- captured as bytes,
decoded by an explicit rule -- and proved it against synthetic children
([subprocess-output.md](subprocess-output.md), ADR 0055). It deliberately left
three things open: proving the **installed console** under a *verified*
non-UTF-8 Windows setting, reproducing five failures a review reported, and the
CLI's own stdout/stderr encoding. This record is all three.

## The lanes

`tests/encoding_lanes.py` defines three settings and checks each one measures
as what it claims, rather than trusting `PYTHONUTF8`'s presence or absence:

| Lane | Setting | On Windows | Off Windows |
| --- | --- | --- | --- |
| `ambient` | neither variable set | must measure non-UTF-8, or the test fails | skipped (not meaningful) |
| `utf8-off` | `PYTHONUTF8=0` | must measure non-UTF-8, or the test fails | skipped |
| `utf8-on` | `PYTHONUTF8=1` | must measure UTF-8 | runs everywhere, as the control |

A discovered quirk shapes the harness: the shell layer that launches commands
in this development environment sets `PYTHONIOENCODING=utf-8:surrogateescape`
for its own purposes, which is not present in a plain Windows install, a
GitHub Actions `windows-latest` runner, or a user's own terminal. `lane_env`
clears both variables before applying a lane's own setting, rather than
trusting whatever the invoking shell happened to leave behind -- this was
found by measuring the same probe through two different tools in the same
session and getting two different, unexplained answers before tracing it.

`tests/conftest.py`'s `pytest_report_header` prints the running interpreter's
own mode on every job, so a CI log states what it ran under without needing to
open a test.

## The finding: a path outside the console's codepage crashed after the
project was already written

Characterising the installed console (`create-forge new` into a destination
containing `项目`, a CJK segment with no `cp1252` reading) reproduced a real
`UnicodeEncodeError`, on the real console script, whenever output was not a
real interactive console -- piped, redirected, or captured, which is also what
every test harness, CI log, and many IDE run windows do. The mechanism: Rich
resolves whether a stream is a "legacy Windows" console by asking
`GetConsoleMode`, which fails identically for a plain pipe and an unsupported
terminal; on that path Rich writes through the stream's own `.write`, i.e.
`sys.stdout`'s default `errors="strict"`. The crash happened inside
`_report_created`'s success panel -- **after** `pipeline.finalise_files` and
`lifecycle.finalise_project` had already written and committed the project.
`Café`, a `cp1252`-representable name, did not reproduce it; only a character
genuinely outside the console's codepage does.

The fix, `cli._harden_console_encoding` (called at the top of `main()`, Typer's
group callback, so it applies to whatever `sys.stdout`/`sys.stderr` are current
at invocation time -- including a test harness's own swapped streams):
reconfigures both to `errors="backslashreplace"`. Confirmed fixed under all
three lanes, through the real console script, in
`tests/test_e2e_installed_encoding.py::test_generation_into_a_non_ascii_path_survives_every_lane`;
the cross-platform half of the same mechanism (any codepage mismatch, not only
Rich's Windows-specific writer) is proven fast, in-process, in
`tests/test_cli.py`.

`decode_diagnostic`'s own substitution character (`U+FFFD`) is *also* outside
`cp1252`, so the same fix independently protects genuinely undecodable
diagnostic bytes reaching `doctor` -- proven with a real `git`/`uv` shim
(`tests/fake_tools.py`) that emits them from `git config --get`/`uv --version`.

## A second finding: a provisioning failure escaped as a raw traceback

While exercising a real `--engine-source` failure, `EngineSourceError` raised
by `engine_source.provision()`'s own body (before it ever yields a runtime)
reached the user as an unhandled traceback: `with engine_source.provision(...)
as runtime:` had nothing around it to catch an `__enter__`-time failure, unlike
every other `EngineSourceError` site in the same function. Fixed by replacing
that `with` with `contextlib.ExitStack`, so provisioning can be wrapped in its
own `try`/`except` while every later step keeps its existing one. Proven fast
in `tests/test_engine_source.py::test_a_provisioning_failure_is_explained_not_traced`
(confirmed to fail on the prior code by reverting the fix locally) and, through
the real console with a real connection failure, in
`test_engine_source_connection_failure_is_explained_not_echoed`.

Neither finding is Windows- or encoding-specific in its cause; both were found
*while* characterising encoding behaviour and are recorded here rather than
split into a separate issue, since fixing them is what let the rest of this
issue's scenarios pass at all.

## What the executable evidence proves

`tests/test_e2e_installed_encoding.py` builds the candidate wheel and installs
it, with `forge-template==0.6.0` pinned alongside it, into a virtual
environment at the interpreter `CREATE_FORGE_E2E_PYTHON` names (default 3.13;
CI's matrix feeds 3.11/3.13/3.14 -- the supported window's edges plus the
default, the same "edges, not the whole window" reasoning
`test_e2e_installed_cutover.py`'s and `test_e2e_installed_streamlit.py`'s own
`_PYTHON_WINDOW_EDGES` already use for the identical mechanism).

| Criterion | Evidence |
| --- | --- |
| Record interpreter mode and preferred encoding; exercise `PYTHONUTF8=0`; never silently UTF-8-only | `test_the_lane_is_verified_not_assumed`, all three lanes; a lane that cannot be verified fails, not skips, on Windows |
| Non-ASCII paths and human diagnostics | `test_generation_into_a_non_ascii_path_survives_every_lane`, `test_update_through_a_non_ascii_path_survives_every_lane`, `test_doctor_reports_a_non_ascii_git_identity` (a real, not-injected, `.gitconfig` identity) |
| Invalid diagnostic bytes | `test_doctor_survives_undecodable_git_config_bytes` (all three lanes), `test_doctor_survives_undecodable_uv_version_bytes`, via a real `git`/`uv` shim (`tests/fake_tools.py`) |
| Strict worker JSON rejection | `test_worker_rejects_a_corrupted_response`, all four ways `capture.parse_protocol_json` can refuse a body, through a real out-of-process worker talking to a hand-built `forge_template` look-alike engine, not a monkeypatched `subprocess.run` |
| Git/uv errors | `test_a_failing_git_commit_shows_the_fixed_warning_never_the_secret` (a real failing `git commit`, `new` still exits `0` and keeps the sound render); `test_engine_source_connection_failure_is_explained_not_echoed` (a real connection failure) |
| Secret redaction | The two tests above assert the fixed message only, never the child's own output |
| Linux and UTF-8 controls remain green | The module carries no `windows_only` restriction on its own collection -- it runs in the Linux `e2e` job (`poe test:e2e`) too, where the two Windows-only lanes skip and the rest run as a UTF-8 control |
| Supported settings documented; no forced UTF-8 workaround required | [docs/user-guide/updates.md](user-guide/updates.md#windows-text-encoding); `tests/test_installed_encoding_guard.py` fails if either variable is ever set in `ci.yml` |

## The five reported failures

The Stage 21 review recorded five local test failures under a non-UTF-8
Windows console, resolved by `PYTHONUTF8=1`, named nowhere in the repository.
CF-23.01 could not reproduce them on `main` at `a9c48c7` and left them to this
issue. Sought here at `c9a33cc` -- the CF-21.01 merge, the commit closest to
when the review is dated -- under ambient `cp1252`, with neither `PYTHONUTF8`
nor `PYTHONIOENCODING` set:

| Suite | Result at `c9a33cc` |
| --- | --- |
| fast (`-m "not network and not e2e"`) | 910 passed, 1 skipped, **0 failed** |
| `tests/test_e2e_generation.py` | 5 passed |
| `tests/test_e2e_engine_generation.py` | 24 passed |
| `tests/test_e2e_installed_data_science.py` | 5 passed |
| `tests/test_e2e_installed_cutover.py` | 18 passed |
| `tests/test_e2e_installed_rollout.py` | 39 passed |
| `tests/test_update_engine.py`, `tests/test_engine_source.py` (e2e) | 1 passed, 2 skipped (no sibling `../forge-template` checkout -- an unrelated, pre-existing skip) |

**None reproduced.** `test_e2e_installed_update_safety.py` and
`test_e2e_installed_streamlit.py` did not exist yet at `c9a33cc` (CF-22.03 and
CF-21.02 added them afterward), so they could not have been among the original
five there either. This is the same outcome CF-23.01 recorded at a later
commit; between the two measurements, nothing that would explain the five is
established. What *did* reproduce, both times, is the underlying mechanism
CF-23.01 fixed (`docs/subprocess-output.md`'s "Reported failures" section) --
which is why AC-03 is satisfied by this disposition rather than by naming five
tests that do not exist.

## Boundaries retained

This changes `cli.py` (the two fixes above) and adds tests, a CI job, and
documentation. It does not change any generation, update, or protocol
behaviour beyond the two fixes; no dependency, lock, or template registry
change. `runner.py`'s Copier subprocesses and `scripts/` are unaffected, as
`docs/subprocess-output.md` already scopes them out. No release is cut for
this issue by itself; the fixes ride whatever release follows.

When this boundary or its evidence changes, update this record,
[docs/subprocess-output.md](subprocess-output.md), and the executable suite in
the same pull request.
