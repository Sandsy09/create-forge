"""Windows text-encoding lanes for the installed console (CF-23.02, ADR 0057).

`tests/subprocess-output.md` fixed the *mechanism* -- every child's output is
captured as bytes and decoded by an explicit rule. What is missing is proof
that the **installed console itself** behaves correctly under a genuinely
verified non-UTF-8 interpreter setting, not one merely assumed from
`PYTHONUTF8`'s absence. `PYTHONUTF8=1` hides a decoding gap; it does not
prove one does not exist, which is why a lane's probe is checked rather than
trusted.

Three lanes:

- **ambient** -- no `PYTHONUTF8`/`PYTHONIOENCODING` override, the setting a
  plain Windows install starts with.
- **utf8-off** -- `PYTHONUTF8=0` explicitly, the same starting point stated
  rather than merely absent.
- **utf8-on** -- `PYTHONUTF8=1`, the control: everything the other two lanes
  prove must also hold here, since this is the setting most guidance
  recommends and must not be required for correctness (the acceptance
  criterion this whole module answers).

A discovered environment quirk shapes `lane_env`: some developer shells (this
one included, through the tool that launches PowerShell commands) inherit a
`PYTHONIOENCODING` set by the shell layer itself, not by anything under test.
Trusting "whatever the invoking shell happens to have" would make "ambient"
mean something different on every machine, so both variables are always
cleared before a lane applies its own overrides -- never merely left alone.
"""

from __future__ import annotations

import json
import locale
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_PROBE = (
    "import json, locale, sys;"
    "print(json.dumps({"
    '"utf8_mode": sys.flags.utf8_mode,'
    '"preferred_encoding": locale.getpreferredencoding(False),'
    '"stdout_encoding": sys.stdout.encoding,'
    '"stderr_encoding": sys.stderr.encoding,'
    '"fs_encoding": sys.getfilesystemencoding(),'
    "}))"
)

# Cleared before every lane applies its own overrides -- see the module
# docstring's "discovered environment quirk" paragraph.
_ENCODING_ENV_KEYS = ("PYTHONUTF8", "PYTHONIOENCODING")

_UTF8_ALIASES = frozenset({"utf-8", "utf8", "cp65001"})


@dataclass(frozen=True, slots=True)
class EncodingLane:
    """One interpreter-encoding setting the installed console is proven under."""

    name: str
    overrides: Mapping[str, str]
    expect_utf8_mode: bool
    windows_only: bool
    """Whether this lane is meaningful only on Windows.

    `ambient`/`utf8-off` assert a genuinely non-UTF-8 setting, which a
    Linux/macOS host's own default locale does not generally give (CF-23.02's
    outcome is specifically about *Windows* settings); `utf8-on` is a control
    that must hold everywhere.
    """


AMBIENT = EncodingLane(
    "ambient", overrides={}, expect_utf8_mode=False, windows_only=True
)
UTF8_OFF = EncodingLane(
    "utf8-off",
    overrides={"PYTHONUTF8": "0"},
    expect_utf8_mode=False,
    windows_only=True,
)
UTF8_ON = EncodingLane(
    "utf8-on",
    overrides={"PYTHONUTF8": "1"},
    expect_utf8_mode=True,
    windows_only=False,
)

LANES = (AMBIENT, UTF8_OFF, UTF8_ON)


def is_windows() -> bool:
    """Whether this host is Windows -- the only platform this module's
    non-UTF-8 lanes are meaningful on; `sys.platform`, not `os.name`, so a
    Windows-on-ARM or Cygwin-hosted interpreter is still covered the same way
    CI's `windows-latest` runner is.
    """
    return sys.platform == "win32"


def lane_env(base: Mapping[str, str], lane: EncodingLane) -> dict[str, str]:
    """`base` with `lane`'s encoding setting applied, cleared first.

    `base` is ordinarily `InstalledClient.env` -- the isolated child
    environment every installed suite already builds -- never the raw
    ambient `os.environ` a lane's own override could be shadowed by.
    """
    env = dict(base)
    for key in _ENCODING_ENV_KEYS:
        env.pop(key, None)
    env.update(lane.overrides)
    return env


def probe(python: Path, env: Mapping[str, str]) -> dict[str, object]:
    """Run `python` under `env` and report what it actually resolved to.

    Never trusts what a lane *asked* for -- this is what makes
    `require_lane` able to fail instead of silently exercising the wrong
    setting.
    """
    result = subprocess.run(  # noqa: S603 - fixed interpreter, fixed inline script
        [str(python), "-c", _PROBE],
        env=dict(env),
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        msg = (
            f"encoding probe failed (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
        raise RuntimeError(msg)
    parsed: dict[str, object] = json.loads(result.stdout.decode("utf-8"))
    return parsed


def _is_utf8_encoding(name: object) -> bool:
    return isinstance(name, str) and name.lower().replace("_", "-") in _UTF8_ALIASES


def require_lane(lane: EncodingLane, measured: Mapping[str, object]) -> None:
    """Fail loudly when a probe contradicts the lane it was supposed to prove.

    A lane that claims `utf8_mode=False` but measures UTF-8 mode, or a
    preferred encoding that is UTF-8 under another name, would silently
    degrade "prove this under a non-UTF-8 setting" into "prove this under
    whatever the host happens to default to" -- exactly the gap CF-23.01 left
    open. This is an `AssertionError`, not a skip: a lane failing this check
    on Windows is the finding, not a reason to look away from it.
    """
    utf8_mode = bool(measured.get("utf8_mode"))
    if utf8_mode != lane.expect_utf8_mode:
        msg = (
            f"lane {lane.name!r} expected utf8_mode={lane.expect_utf8_mode} but "
            f"the probe measured {measured.get('utf8_mode')!r}"
        )
        raise AssertionError(msg)
    preferred = measured.get("preferred_encoding")
    if not lane.expect_utf8_mode and _is_utf8_encoding(preferred):
        msg = (
            f"lane {lane.name!r} is supposed to be non-UTF-8 but the probe's "
            f"preferred encoding is {preferred!r} -- this host cannot "
            "exercise it; see the module docstring"
        )
        raise AssertionError(msg)


def report_header_line() -> str:
    """One line for `pytest_report_header`: the *running* interpreter's own
    encoding state, so every job's log states what it actually ran under
    without needing to open this module's tests to find out.
    """
    import os  # noqa: PLC0415 - only needed for this one-off diagnostic line

    return (
        "encoding: utf8_mode="
        f"{sys.flags.utf8_mode} preferred={locale.getpreferredencoding(False)} "
        f"PYTHONUTF8={os.environ.get('PYTHONUTF8')!r} "
        f"PYTHONIOENCODING={os.environ.get('PYTHONIOENCODING')!r}"
    )
