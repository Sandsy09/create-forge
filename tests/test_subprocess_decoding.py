"""CF-23.01 (ADR 0055): what each production capture site does with bytes that
have no valid reading.

The reported failure was `subprocess.run(..., text=True)` decoding a child's
output with the host locale and raising on a byte it could not read. Each test
here drives one production site with a *real child process* that writes such
bytes, so decoding behaves exactly as in production -- only the command run is
substituted. A site that still decodes with the ambient locale fails here on any
host: `cp1252` has no character for `0x81`/`0x8D`/`0x8F`/`0x90`/`0x9D`, and UTF-8
has none for a lone `0xFF`.

Every site is proven three ways: an undecodable stream does not raise; the fixed
diagnostic never contains what the child wrote (a credential-shaped URL below
stands for anything sensitive); and the return code, timeout and error behaviour
are unchanged.

No network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from create_forge import capture, engine_source, lifecycle, staging, update
from create_forge import cli as cli_module

if TYPE_CHECKING:
    from collections.abc import Callable

_REAL_RUN = subprocess.run

# Not UTF-8, and cp1252 has no character for the last five.
UNDECODABLE = b"\xff\xfe\x81\x8d\x8f\x90\x9d"
SECRET = b"https://user:hunter2@example.com/private/repo"


def _script(
    monkeypatch: pytest.MonkeyPatch,
    decide: Callable[[list[str]], tuple[int, bytes, bytes]],
) -> list[list[str]]:
    """Make every `subprocess.run` start a scripted child instead.

    `decide(argv)` returns `(returncode, stdout, stderr)` for the command the code
    under test tried to run; the real process machinery still runs, so the
    caller's decoding, timeout and newline handling are exactly production's.
    Returns the list the attempted argvs are appended to.
    """
    attempted: list[list[str]] = []

    def fake(argv: Any, **kwargs: Any) -> Any:
        argv = list(argv)
        attempted.append(argv)
        returncode, out, err = decide(argv)
        code = (
            "import sys;"
            f"sys.stdout.buffer.write({out!r});"
            f"sys.stderr.buffer.write({err!r});"
            f"sys.exit({returncode})"
        )
        kwargs.pop("cwd", None)  # the scripted child needs no working directory
        return _REAL_RUN([sys.executable, "-c", code], **kwargs)

    monkeypatch.setattr(subprocess, "run", fake)
    return attempted


def _always(
    returncode: int, out: bytes = b"", err: bytes = b""
) -> Callable[[list[str]], tuple[int, bytes, bytes]]:
    return lambda argv: (returncode, out, err)


# --------------------------------------------------------------------------- #
# engine_source._run_uv -- output is never read or forwarded                   #
# --------------------------------------------------------------------------- #


def test_a_uv_that_fails_with_undecodable_stderr_gives_the_fixed_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("create_forge.engine_source.shutil.which", lambda name: "uv")
    _script(monkeypatch, _always(1, err=UNDECODABLE + SECRET))

    with pytest.raises(engine_source.EngineSourceError) as excinfo:
        engine_source._run_uv(["pip", "install", "x"])

    message = str(excinfo.value)
    assert "could not provision the engine source" in message
    assert "hunter2" not in message
    assert "example.com" not in message


def test_a_uv_that_succeeds_with_undecodable_output_is_still_a_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("create_forge.engine_source.shutil.which", lambda name: "uv")
    _script(monkeypatch, _always(0, out=UNDECODABLE, err=UNDECODABLE))

    engine_source._run_uv(["venv", "x"])  # must not raise


def test_a_uv_timeout_is_still_a_clean_engine_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("create_forge.engine_source.shutil.which", lambda name: "uv")

    def _slow(argv: Any, **kwargs: Any) -> Any:
        return _REAL_RUN(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            **{**kwargs, "timeout": 0.3},
        )

    monkeypatch.setattr(subprocess, "run", _slow)

    with pytest.raises(engine_source.EngineSourceError, match="timed out"):
        engine_source._run_uv(["venv", "x"])


# --------------------------------------------------------------------------- #
# engine_source._call_worker -- protocol output: strict                        #
# --------------------------------------------------------------------------- #


def _runtime(tmp_path: Path) -> engine_source.ProvisionedEngine:
    return engine_source.ProvisionedEngine(python=Path(sys.executable), root=tmp_path)


@pytest.mark.parametrize(
    ("stdout", "why"),
    [
        (b"", "empty"),
        (b"   \n", "blank"),
        (b"not json", "text"),
        (b'{"ok": true', "truncated"),
        (b'\xef\xbb\xbf{"ok": true, "result": {}}', "byte-order-mark"),
        (b'{"ok": true, "result": {"x": "\xff"}}', "invalid-utf-8-inside-json"),
        (UNDECODABLE, "undecodable"),
        (b'{"ok": true}\xff', "trailing-garbage-byte"),
        (b"[" * 5_000, "nested-too-deep"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_a_worker_response_that_is_not_strict_utf8_json_is_rejected_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stdout: bytes, why: str
) -> None:
    _script(monkeypatch, _always(0, out=stdout))

    with pytest.raises(engine_source.EngineSourceError, match="unreadable response"):
        engine_source._call_worker(_runtime(tmp_path), "info")


def test_a_worker_that_crashes_with_undecodable_stderr_is_rejected_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A crash before the worker's `main` writes nothing to stdout and a traceback
    to stderr -- here one with bytes no locale can read and a credential.
    """
    _script(monkeypatch, _always(1, err=b"Traceback... " + UNDECODABLE + SECRET))

    with pytest.raises(engine_source.EngineSourceError) as excinfo:
        engine_source._call_worker(_runtime(tmp_path), "info")

    assert "hunter2" not in str(excinfo.value)
    assert "example.com" not in str(excinfo.value)


def test_a_valid_worker_response_survives_undecodable_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stderr is never read for content, so noise on it cannot fail a good call."""
    _script(
        monkeypatch,
        _always(0, out=b'{"ok": true, "result": {"n": 1}}', err=UNDECODABLE),
    )

    assert engine_source._call_worker(_runtime(tmp_path), "info") == {"n": 1}


def test_a_worker_response_with_non_ascii_is_read_as_utf8(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    body = '{"ok": true, "result": {"name": "café 项目"}}'.encode()
    _script(monkeypatch, _always(0, out=body))

    assert engine_source._call_worker(_runtime(tmp_path), "info") == {
        "name": "café 项目"
    }


def test_the_worker_request_is_sent_as_utf8_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def fake(argv: Any, **kwargs: Any) -> Any:
        seen["input"] = kwargs.get("input")
        seen["text"] = kwargs.get("text")
        return _REAL_RUN(
            [sys.executable, "-c", "import sys; sys.stdout.write('{\"ok\": true}')"],
            **{k: v for k, v in kwargs.items() if k != "input"},
        )

    monkeypatch.setattr(subprocess, "run", fake)

    engine_source._call_worker(
        _runtime(tmp_path), "render", {"payload": {"name": "café 项目"}}
    )

    assert isinstance(seen["input"], bytes)
    assert b"caf" in seen["input"]
    seen["input"].decode("utf-8")  # valid UTF-8
    assert not seen["text"]


# --------------------------------------------------------------------------- #
# cli: diagnostic facts                                                        #
# --------------------------------------------------------------------------- #


def test_a_uv_version_survives_undecodable_bytes_around_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _script(monkeypatch, _always(0, out=b"uv 0.12.13 " + UNDECODABLE + b"\n"))

    assert cli_module._uv_version("uv") == "0.12.13"


def test_a_uv_version_that_is_entirely_undecodable_is_simply_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _script(monkeypatch, _always(0, out=UNDECODABLE))

    assert cli_module._uv_version("uv") is None


def test_a_git_config_value_with_non_ascii_is_a_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _script(monkeypatch, _always(0, out="José 项目\n".encode()))

    assert cli_module._git_config("user.name") == "José 项目"


def test_an_undecodable_git_config_value_still_counts_as_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _script(monkeypatch, _always(0, out=UNDECODABLE + b"\n"))

    assert cli_module._git_config(
        "user.name"
    )  # doctor's identity check only asks "set?"


def test_an_unset_git_config_key_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, _always(1))

    assert cli_module._git_config("user.name") is None


# --------------------------------------------------------------------------- #
# lifecycle, staging: return code only                                         #
# --------------------------------------------------------------------------- #


def test_a_failing_git_lifecycle_step_warns_without_the_childs_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(1, err=UNDECODABLE + SECRET))

    warning = lifecycle._run_git(["init"], tmp_path)

    assert warning is not None
    assert "failed" in warning
    assert "hunter2" not in warning
    assert "example.com" not in warning


def test_a_failing_pre_commit_install_warns_without_the_childs_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(1, err=UNDECODABLE + SECRET))

    warning = lifecycle._run_pre_commit_install(tmp_path)

    assert warning is not None
    assert "hunter2" not in warning


def test_a_succeeding_lifecycle_step_ignores_undecodable_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(0, out=UNDECODABLE, err=UNDECODABLE))

    assert lifecycle._run_git(["init"], tmp_path) is None
    assert lifecycle._run_pre_commit_install(tmp_path) is None


def test_a_failing_uv_lock_gives_the_fixed_message_without_the_childs_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(2, err=UNDECODABLE + SECRET))

    with pytest.raises(staging.StagingError) as excinfo:
        staging.create_uv_lock(tmp_path)

    assert "exit status 2" in str(excinfo.value)
    assert "hunter2" not in str(excinfo.value)
    assert "example.com" not in str(excinfo.value)


def test_a_succeeding_uv_lock_ignores_undecodable_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(0, out=UNDECODABLE, err=UNDECODABLE))

    staging.create_uv_lock(tmp_path)  # must not raise


# --------------------------------------------------------------------------- #
# update: git facts, and merge content                                         #
# --------------------------------------------------------------------------- #


def test_is_git_repository_reads_true_and_survives_undecodable_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(0, out=b"true\n"))
    assert update._is_git_repository(tmp_path) is True

    _script(monkeypatch, _always(0, out=UNDECODABLE))
    assert update._is_git_repository(tmp_path) is False

    _script(monkeypatch, _always(128, err=UNDECODABLE))
    assert update._is_git_repository(tmp_path) is False


def test_a_dirty_tree_is_recognised_whatever_the_status_bytes_are(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def decide(argv: list[str]) -> tuple[int, bytes, bytes]:
        if "rev-parse" in argv:
            return 0, b"true\n", b""
        return 0, b" M caf\xc3\xa9.txt\n?? " + UNDECODABLE + b"\n", b""

    _script(monkeypatch, decide)

    with pytest.raises(update.UpdateError, match="uncommitted changes"):
        update.require_clean_tree(tmp_path)


def test_a_clean_tree_is_recognised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def decide(argv: list[str]) -> tuple[int, bytes, bytes]:
        return (0, b"true\n", b"") if "rev-parse" in argv else (0, b"", b"")

    _script(monkeypatch, decide)

    update.require_clean_tree(tmp_path)  # must not raise


def test_a_failing_git_step_reports_the_command_not_the_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _script(monkeypatch, _always(1, err=UNDECODABLE + SECRET))

    with pytest.raises(update.UpdateError) as excinfo:
        update._git_output(["add", "-A"], tmp_path)

    assert "hunter2" not in str(excinfo.value)
    assert "example.com" not in str(excinfo.value)


def test_the_repository_root_keeps_its_non_ascii_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = "/repos/café-项目"

    def decide(argv: list[str]) -> tuple[int, bytes, bytes]:
        if "--show-toplevel" in argv:
            return 0, root.encode() + b"\n", b""
        if "HEAD^{commit}" in argv:
            return 0, b"abc\n", b""
        return 0, b" M x\n", b""

    _script(monkeypatch, decide)

    guidance = update.recovery_guidance(tmp_path)

    assert guidance.root == Path(root)
    assert guidance.state is update.RecoveryState.RESTORABLE


def test_a_status_with_undecodable_bytes_is_still_classified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def decide(argv: list[str]) -> tuple[int, bytes, bytes]:
        if "--show-toplevel" in argv:
            return 0, b"/repo\n", b""
        if "HEAD^{commit}" in argv:
            return 0, b"abc\n", b""
        return 0, b"?? " + UNDECODABLE + b"\n M other\n", b""

    _script(monkeypatch, decide)

    guidance = update.recovery_guidance(tmp_path)

    assert guidance.state is update.RecoveryState.RESTORABLE
    assert guidance.has_untracked is True


def test_merge_content_is_binary_and_never_decoded() -> None:
    """Invalid UTF-8 and CRLF line endings pass through `git merge-file` exactly."""
    base = b"a\r\n\xff\x81\r\n"
    ours = base + b"ours\r\n"
    theirs = b"theirs\r\n" + base

    merged, conflicted = update.merge_target(base=base, ours=ours, theirs=theirs)

    assert conflicted is False
    assert merged == b"theirs\r\n" + base + b"ours\r\n"


# --------------------------------------------------------------------------- #
# the worker's own stdio: UTF-8 whatever the interpreter's locale              #
# --------------------------------------------------------------------------- #

WORKER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "create_forge"
    / "_engine_worker.py"
)


def _non_utf8_env() -> dict[str, str]:
    """A child interpreter forced into a non-UTF-8 stdio configuration.

    CPython honours these on every platform, so this exercises the same situation
    a default Windows install is in without needing Windows.
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "0"
    env["PYTHONIOENCODING"] = "cp1252"
    return env


def test_the_real_worker_speaks_utf8_json_under_a_non_utf8_interpreter() -> None:
    result = capture.run_captured(
        [sys.executable, str(WORKER_PATH), "info"],
        stdin=b"{}",
        env=_non_utf8_env(),
        timeout=60,
    )

    response = capture.parse_protocol_json(result.stdout)

    assert result.returncode == 0
    assert isinstance(response, dict)
    assert response["ok"] is True
    assert result.stdout.isascii()  # ensure_ascii: valid UTF-8 whatever the locale


def test_the_real_worker_reports_a_request_that_is_not_utf8_as_a_structured_error() -> (
    None
):
    result = capture.run_captured(
        [sys.executable, str(WORKER_PATH), "info"],
        stdin=b'{"payload": "\xff\x81"}',
        env=_non_utf8_env(),
        timeout=60,
    )

    response = capture.parse_protocol_json(result.stdout)

    assert result.returncode == 0  # always exits 0; failure is in the body
    assert isinstance(response, dict)
    assert response["ok"] is False
    assert "error" in response


def test_the_real_worker_writes_no_newline_translation_on_any_platform() -> None:
    result = capture.run_captured(
        [sys.executable, str(WORKER_PATH), "info"], stdin=b"{}", timeout=60
    )

    assert result.stdout.endswith(b"\n")
    assert b"\r" not in result.stdout
