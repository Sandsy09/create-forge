# Subprocess output contract

This is the canonical contract for how `create-forge` captures and decodes the
output of the processes it starts. It is delivered by
[CF-23.01 / #196](https://github.com/Sandsy09/create-forge/issues/196), the
first child of
[CF-EPIC-23](https://github.com/Sandsy09/create-forge/issues/189), and accepted
under
[ADR 0055](adr/0055-capture-subprocess-output-as-bytes-and-decode-by-rule.md).
The proof that the installed CLI behaves under a non-UTF-8 Windows setting is
[CF-23.02 / #197](https://github.com/Sandsy09/create-forge/issues/197)'s,
recorded in
[installed-encoding-validation.md](installed-encoding-validation.md) (ADR 0057),
which also fixed the CLI's own stdout/stderr encoding this contract deliberately
left open.

## Status

The rule is in force for every process `src/create_forge/` starts, and for the
capturing helpers in `tests/`. It is enforced by `tests/test_subprocess_policy.py`.

## The rule

**Nothing here captures text.** `subprocess.run(..., text=True)` decodes with the
host locale — `cp1252` on a default Windows install — so what a child writes and
how this process reads it were only ever lined up by accident. `git` and `uv`
write UTF-8; a Python child writes the locale encoding when piped. On a
non-UTF-8 host, one undecodable byte in a child's stderr raised inside
`subprocess.run` and left `stdout` as `None`. `PYTHONUTF8=1` hides that; it does
not define what the bytes are, and it is not part of this contract.

`capture.run_captured` returns **bytes**. A caller decodes only what it
genuinely reads, under exactly one of three rules. Most callers read only the
return code and decode nothing.

## The three policies

| Class | Rule | Used for | Never |
| --- | --- | --- | --- |
| **Diagnostic** — `decode_diagnostic` | UTF-8, `errors="replace"`; never raises | a fact extracted from human-oriented output: a version token, whether a value is set, a status prefix | shown raw: argv, stdout and stderr are never echoed, because they can carry a credential |
| **Protocol** — `decode_protocol`, `parse_protocol_json` | UTF-8, **strict**, then strict JSON; raises `ProtocolDecodeError` | the engine-source worker's request and response | skipping a byte order mark, replacing a byte, or accepting a body that is not JSON |
| **Path or binary** — bytes, or `decode_path` | bytes left alone; a path is `os.fsdecode`d, which is the filesystem's own round trip | `git merge-file`'s content; the repository root `git` prints | replacement decoding: replacing bytes in a path would name a different file |

`display_safe` makes a decoded path printable at the point of display (a lone
surrogate becomes a visible `\udcXX`); it never changes the string a command runs
with.

## The capture seam

`src/create_forge/capture.py` is engine-free and is the **only** module in the
package that starts a process.

- `run_captured(argv, *, cwd, env, stdin, timeout) -> Captured(returncode,
  stdout, stderr)`. It never passes `text=`, `encoding=`, `errors=` or
  `universal_newlines`, and translates no newline. `stdin`, when given, is bytes:
  the caller states the encoding it sends.
- `OSError` and `subprocess.TimeoutExpired` propagate unchanged, so each caller
  keeps translating them into its own safe error. Return codes, including the
  negative "killed by signal" codes on POSIX, reach the caller exactly as
  `subprocess.run` reports them.

## The site inventory

Every production site that captures process output, and the rule it follows.

| Site | Process | What it reads | Rule |
| --- | --- | --- | --- |
| `cli._uv_version` | `uv --version` | a version token, validated by regex before use | diagnostic |
| `cli._git_config` | `git config --get <key>` | whether a value is set | diagnostic |
| `engine_source._run_uv` | `uv venv`, `uv pip install` | the return code only; output is never forwarded | not decoded |
| `engine_source._call_worker` | the provisioned interpreter running `_engine_worker.py` | the JSON response | **protocol** |
| `lifecycle._run_git`, `lifecycle._run_pre_commit_install` | `git init/add/commit`, `uv run pre-commit install` | the return code only | not decoded |
| `staging.create_uv_lock` | `uv lock` | the return code only | not decoded |
| `update._git_output`, `update._is_git_repository` | `git status/add/mv/rev-parse` | whether output is empty, and `true` | diagnostic |
| `update._read_git` | `git rev-parse`, `git status --porcelain` | the repository root; two-character status prefixes | path (`decode_path`) and diagnostic |
| `update.merge_target` | `git merge-file -p` | the merged file content | **binary**: never decoded |
| `_engine_worker.py` (the child's own stdio) | — | JSON on stdin, JSON on stdout | **protocol** |

Not part of this surface: `runner.py`, whose subprocesses are Copier's own
(through `plumbum`) and are not started by this package; and the developer
tooling under `scripts/`, which is never shipped.

## The worker protocol

`_engine_worker.py` runs standalone inside a provisioned environment that has no
`create_forge`, so it carries the policy itself: it reads `sys.stdin.buffer` and
writes `sys.stdout.buffer`, both as UTF-8, and emits `json.dumps` with its default
`ensure_ascii=True`. ASCII is valid UTF-8, so the wire is byte-for-byte what it
was; what changes is that it no longer depends on either side's locale.

The parent sends `json.dumps(request).encode("utf-8")` and parses the response with
`parse_protocol_json`. Any of these becomes an `EngineSourceError` with a fixed
message, never a raw exception and never the child's bytes:

- a response that is not valid UTF-8;
- a byte order mark, an empty body, or a body that is not JSON;
- JSON nested past the parser's limit.

The worker always exits `0` and writes exactly one object; a crash before it runs
leaves stdout empty and is reported the same way. Its stderr is never read for
content.

## The test harness

`tests/process.py::run_text` captures bytes and decodes with an explicit
encoding (default UTF-8, `errors="replace"`), so a decode can never raise. A
test that deliberately runs a child under a non-UTF-8 setting passes
`encoding=` for what that child writes. `tests/test_subprocess_policy.py` fails
any other text-mode capture in `tests/` that does not name its encoding.

## Reported failures

The Stage 21 review recorded five existing test cases (one in the fast suite,
four in e2e) failing locally under a non-UTF-8 Windows console, and passing with
`PYTHONUTF8=1`. **None of the five is named anywhere in the repository, and none
reproduced when this contract was written.** Measured on 2026-09-21 on clean
`main` (`a9c48c7`), Windows 11, Python 3.13.1 with
`locale.getpreferredencoding(False) == "cp1252"`, UTF-8 mode off, and neither
`PYTHONUTF8` nor `PYTHONIOENCODING` set:

| Suite (before this change) | Result |
| --- | --- |
| fast (`-m "not network and not e2e"`) | 1108 passed, 10 skipped, **0 failed** |
| `tests/test_e2e_engine_generation.py` | 24 passed |
| `tests/test_e2e_installed_cutover.py` | 18 passed |
| `tests/test_e2e_installed_rollout.py` | 39 passed |
| `tests/test_e2e_generation.py` | 5 passed |
| `tests/test_e2e_installed_update_safety.py` | 14 passed, 1 skipped |
| `tests/test_e2e_installed_data_science.py` | 5 passed |
| `tests/test_e2e_installed_streamlit.py` | 17 passed |
| `tests/test_update_engine.py`, `tests/test_engine_source.py` (e2e) | 3 passed |

So the failures depend on something not present in that run; what differed is not
established, and no hypothesis is asserted here.

**Resolution (CF-23.02):** sought again at `c9a33cc` -- the commit closest to
when the review is dated -- under the same ambient `cp1252` setting. None of
the five reproduced there either; see
[installed-encoding-validation.md](installed-encoding-validation.md#the-five-reported-failures)
for the full disposition, including two suites in the table above that did not
exist yet at that commit. What *did* reproduce, both times, is the mechanism
this contract fixes.

**What did reproduce is the mechanism.** On Windows the decode error is raised
in `subprocess`'s reader thread, not in the caller, so `subprocess.run` returns
with `stdout` and `stderr` as `None` and pytest reports an unhandled thread
exception; whatever then reads the output fails on `None`, far from the cause.
`tests/test_subprocess_decoding.py` drives each production site with a real child
that writes bytes with no valid reading. Run against the production code as it was
on `main`, **12 of its 36 tests fail** on this host, and the run emits 21
unhandled-thread-exception warnings. The failures are in the worker response
(malformed UTF-8 inside otherwise valid JSON, undecodable bytes, JSON nested past
the parser's limit), the worker's request and response encoding, `cli._uv_version`,
`cli._git_config`, `update._is_git_repository`, and `update.require_clean_tree`.
One is a finding of its own: the old worker wrote its response with `print`, so on
Windows it emitted `\r\n` where the protocol says `\n`. Sites that read only an
exit status survived on Windows and would not on POSIX, where the decode raises in
the caller. Against this change all 36 pass and the warnings are gone.

## Enforcement

- `tests/test_subprocess_policy.py`: `capture.py` is the only production module
  that starts a process, and it never asks `subprocess` to decode; no test
  captures text without an explicit encoding. The checks are themselves tested
  against synthetic source.
- `tests/test_capture.py`: each policy on malformed, non-ASCII and byte-order-mark
  input, and `run_captured` against real children that write bytes with no valid
  reading.
- `tests/test_subprocess_decoding.py`: every production site driven by a real child
  writing such bytes. A worker that writes malformed bytes, a byte order mark,
  non-UTF-8, nothing, or a non-JSON body is rejected as an `EngineSourceError`; a
  failing `uv`, `git` step or `uv lock` whose stderr is undecodable and carries a
  credential-shaped URL yields the fixed message with nothing of it; and a real
  worker run under `PYTHONUTF8=0 PYTHONIOENCODING=cp1252` still speaks UTF-8.
- `tests/test_process_helper.py`: the harness's `run_text`.
- `tests/test_engine_contract.py`: `capture.py` imports no `forge_template`, and
  this contract stays linked from the docs index, `engine-resolution.md` and
  `end-to-end-tests.md`.

## Executable examples

```bash
uv run pytest tests/test_capture.py tests/test_subprocess_decoding.py \
    tests/test_subprocess_policy.py tests/test_process_helper.py
uv run poe check
```
