# 55. Capture subprocess output as bytes, and decode it by an explicit rule

## Status

Accepted

## Context

[Issue #196 / CF-23.01](https://github.com/Sandsy09/create-forge/issues/196) is
the first child of
[CF-EPIC-23](https://github.com/Sandsy09/create-forge/issues/189). The Stage 21
review recorded five existing test cases failing locally under a non-UTF-8
Windows console, all passing with `PYTHONUTF8=1`.

Every production capture site used `subprocess.run(..., text=True)`, which decodes
with the *host locale*. That is a bet that the child writes what this process
reads, and the two are never guaranteed to agree: `git` and `uv` write UTF-8, a
Python child writes the locale's encoding when piped, and on a default Windows
install the locale is `cp1252`, which has no character for five byte values.
On Windows the resulting decode error is raised in `subprocess`'s reader thread,
not in the caller, so `subprocess.run` returns with `stdout` and `stderr` as `None`
and anything that then reads them fails far from the cause. On POSIX it raises in
the caller. `PYTHONUTF8=1` hides the whole class without defining what any stream
is.

Three facts shape the decision:

- **The engine-source worker protocol was safe only by accident.** `json.dumps`
  defaults to `ensure_ascii=True`, so both directions happened to be ASCII. But
  the parent decoded the worker's *stderr* with the locale as well, and
  `json.loads(result.stdout)` on a `None` escaped as a raw `TypeError`, since only
  `JSONDecodeError` was caught.
- **Most sites never needed to decode.** Their output is never shown (ADR
  0044/0045/0046 forbid echoing raw process output, because it can carry a
  credential) and only the exit status is used.
- **The reported failures did not reproduce.** On clean `main`, in ambient
  `cp1252` mode, the fast suite (1108) and every e2e module passed with no
  failure; the five cases are named nowhere in the repository. What reproduces is
  the mechanism: against the old code, 12 of the 36 site tests in
  `tests/test_subprocess_decoding.py` fail. The unreproduced cases remain
  [CF-23.02 (#197)](https://github.com/Sandsy09/create-forge/issues/197)'s.

## Decision

1. **One seam.** `src/create_forge/capture.py` is the only module in the package
   that starts a process. `run_captured(argv, *, cwd, env, stdin, timeout)` returns
   `Captured(returncode, stdout, stderr)` as **bytes**. It never passes `text=`,
   `encoding=`, `errors=` or `universal_newlines`, and translates no newline.
   `OSError` and `subprocess.TimeoutExpired` propagate, so each caller keeps its own
   error translation, and return codes (including negative "killed by signal"
   codes) are unchanged. It is engine-free and is added to the engine-boundary
   guard.

2. **Three named decoding rules, and nothing else.**
   - *Diagnostic* (`decode_diagnostic`): UTF-8, `errors="replace"`, never raises.
     For extracting a fact from human-oriented output; never shown raw.
   - *Protocol* (`decode_protocol`, `parse_protocol_json`): UTF-8, **strict**, then
     strict JSON. Malformed bytes, a byte order mark, an empty body, a body that is
     not JSON, or JSON nested past the parser's limit raise `ProtocolDecodeError`,
     so malformed bytes cannot silently become valid protocol data.
   - *Path or binary*: bytes are left alone (`git merge-file`'s content), or a
     path is `os.fsdecode`d (`decode_path`), the filesystem's own round trip. **No
     replacement decoding of file or path data**: a replacement character in a
     path names a different file.

3. **A site that reads only an exit status decodes nothing.** `_run_uv`,
   `lifecycle`, and `create_uv_lock` capture bytes and look at `returncode`.
   `_is_git_repository` compares `b"true"`; `require_clean_tree` tests whether
   bytes are empty; `_uv_version` and `_git_config` use the diagnostic rule and
   expose only a validated token or a truthiness. The site inventory is in the
   [subprocess output contract](../subprocess-output.md).

4. **The worker's wire format is explicit UTF-8, read strictly.** The worker runs
   standalone in a provisioned environment that has no `create_forge`, so it carries
   the rule itself: it reads `sys.stdin.buffer` and writes `sys.stdout.buffer` as
   UTF-8, keeping `ensure_ascii=True` (ASCII is valid UTF-8, so the wire is what it
   was) and writing `\n` with no platform translation. The parent sends
   `json.dumps(...).encode("utf-8")` and parses with `parse_protocol_json`. Every
   failure is an `EngineSourceError` with a fixed message, never a raw exception and
   never the child's bytes. `PYTHONUTF8=1` is deliberately **not** set for the
   worker: explicit I/O is the fix, not an environment variable.

5. **Make the one derived path printable, without changing it.** The repository root
   that `git` prints is path data and is decoded with `decode_path`. `display_safe`
   renders a lone surrogate as a visible `\udcXX` at the point of display, so the
   recovery guidance cannot crash while printing in the failure path where a crash is
   worst, and the string a command runs with is untouched.

6. **Enforce it by parsing source.** `tests/test_subprocess_policy.py` fails if any
   module in `src/create_forge/` other than `capture.py` spawns a process, if
   `capture.py` asks `subprocess` to decode, or if a test captures text without an
   explicit `encoding=`. The checks are themselves tested against synthetic source,
   so a guard that has stopped matching anything fails.

7. **The test harness names its encoding.** `tests/process.py::run_text` captures
   bytes and decodes with `encoding=` (default UTF-8, replacement on error), and
   translates newlines as `text=True` did, so existing assertions are unchanged.
   `installed_client.run`, `legacy_template.git` and the e2e and installed modules
   use it. A test that deliberately runs a child under a non-UTF-8 setting passes
   the encoding that child writes; CF-23.02 does this.

8. **Deliberately unchanged.** The CLI's own stdout and stderr encoding (Rich
   propagates `UnicodeEncodeError` for text a console cannot encode; that is a
   console-behaviour question, and anything CF-23.02 finds is filed separately);
   Copier's own subprocess use through `plumbum`; and the developer tooling under
   `scripts/`. Exit codes and every user-facing message are unchanged, except that
   failures that used to escape as raw exceptions are now `EngineSourceError`.

## Consequences

- **A finding of its own:** the old worker wrote its response with `print`, so on
  Windows it emitted `\r\n` where the protocol says `\n`. It was harmless to
  `json.loads` and is now covered by a test.
- **CF-22.03's stale-evidence guard turns red on purpose.** `update.py` and
  `staging.py` are hashed by `docs/update-safety-validation.md`'s safety-relevant
  source digest, and this change edits both, so the installed update-safety suite is
  re-run and that record refreshed in the same pull request.
- **CF-23.02 inherits** an explicit harness default and an `encoding=` override, the
  unreproduced failures, and the untouched console-encoding question.
- **CF-25** (the CLI decomposition epic) must keep `capture.run_captured` the only
  subprocess seam; the guard enforces it.
- **The canonical documents move with it:** the new
  [subprocess output contract](../subprocess-output.md),
  [engine-resolution.md](../engine-resolution.md),
  [filesystem-generation.md](../filesystem-generation.md),
  [end-to-end-tests.md](../end-to-end-tests.md), the docs index and `CLAUDE.md`.
- **Out of scope:** the console's own encoding, a forced global UTF-8, Copier, and
  `scripts/`. ADRs 0001-0054 are untouched.
