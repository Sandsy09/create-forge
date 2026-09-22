"""Installed-console proof under non-UTF-8 Windows settings (CF-23.02, ADR 0057).

`docs/subprocess-output.md` (CF-23.01) fixed the *mechanism*: every process
`create_forge` starts is captured as bytes and decoded by an explicit rule,
proven against synthetic children. What that work deliberately left open is
this module's job: the **installed console**, under a *verified* non-UTF-8
interpreter setting -- `tests/encoding_lanes.py`'s lanes, never merely assumed
from `PYTHONUTF8`'s absence -- and the CLI's own stdout/stderr encoding, which
CF-23.01 explicitly did not touch.

What this proves, through the real built wheel's console script:

- **The three lanes are what they claim to be.** `ambient`/`utf8-off` measure
  as genuinely non-UTF-8 on Windows, or the test fails rather than silently
  passing under the wrong setting; `utf8-on` is the control every scenario
  below must also pass under.
- **A path outside the console's codepage does not crash generation, `doctor`,
  or `update`.** This is the CF-23.02 finding: printing such a path used to
  raise `UnicodeEncodeError` reaching the user *after* `new` had already
  written and committed the project -- fixed by `cli._harden_console_encoding`
  (see `tests/test_cli.py` for the fast, cross-platform half of this proof;
  this module is what confirms it against the real Windows console path Rich
  takes when there is no console at all, only a pipe).
- **Invalid diagnostic bytes reach `doctor` without a traceback**, through a
  real `git`/`uv` shim on `PATH` (`tests/fake_tools.py`) that emits exactly
  the undecodable bytes `tests/test_subprocess_decoding.py` proves against a
  synthetic child -- here proven through the installed console instead.
  A `git commit` failure with a credential-shaped stderr is shown as the
  fixed, sanitised warning `lifecycle._run_git` promises, never the secret.
- **The worker's strict protocol rejects a corrupted response** through a real
  out-of-process `--engine-source` worker talking to a hand-built
  `forge_template` look-alike (`tests/fake_tools.py`), for each of the four
  ways `capture.parse_protocol_json` can refuse a body.
- **A real engine-source connection failure is explained, not echoed.**

Reproducing the five originally reported failures (AC-03) is recorded in
`docs/installed-encoding-validation.md`, not here: they were sought at the
commit closest to when they were seen (`c9a33cc`) and did not reproduce, the
same outcome CF-23.01 recorded at a later commit -- there is nothing left to
pin into an executable test.

Windows-specific coverage runs only on Windows (`encoding_lanes.is_windows`);
the module still runs on Linux as a UTF-8 control (CI's existing `e2e` job),
where every non-Windows-only scenario below is exercised once under the
host's own ambient setting.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.encoding_lanes import (
    LANES,
    UTF8_ON,
    EncodingLane,
    is_windows,
    lane_env,
    probe,
    require_lane,
)
from tests.fake_tools import build_fake_engine_wheel, build_shim_wheel
from tests.installed_client import (
    ENGINE_VERSION,
    InstalledClient,
    assert_success,
    build_client,
    run,
    venv_python,
    venv_script,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.e2e

# Matches the matrix `e2e-windows-encoding`'s CI job feeds one interpreter to
# per cell (3.11/3.13/3.14); local runs default to the same interpreter every
# other installed suite in this repository does.
_PYTHON = os.environ.get("CREATE_FORGE_E2E_PYTHON", "3.13")

_ANSWERS = {
    "project_description": "create-forge installed encoding validation.",
    "license": "mit",
    "author_name": "create-forge e2e",
    "author_email": "create-forge-e2e@example.invalid",
}

# A CJK path segment: not representable in `cp1252`, the codepage a plain
# Windows install defaults to outside Windows Terminal -- the exact character
# class the CF-23.02 finding was about. `Café`, by contrast, is representable
# in `cp1252` and would not have reproduced it (recorded during investigation).
_NON_ASCII_SEGMENT = "项目"


def _new_args(name: str, dest: Path) -> list[str]:
    args = ["new", name, "--archetype", "library", "--yes", "--path", str(dest)]
    for key, value in _ANSWERS.items():
        args += ["--data", f"{key}={value}"]
    return args


def _lane_id(lane: EncodingLane) -> str:
    return lane.name


# --------------------------------------------------------------------------- #
# fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def encoding_client(
    candidate_wheel: Path, e2e_child_env: dict[str, str]
) -> Iterator[InstalledClient]:
    """The candidate wheel installed at `_PYTHON`, the interpreter this
    module's CI matrix cell feeds through `CREATE_FORGE_E2E_PYTHON` -- a
    dedicated fixture rather than `conftest.py`'s shared `installed_client`,
    which is fixed at a single interpreter (ADR 0057).
    """
    with build_client(
        candidate_wheel,
        e2e_child_env,
        engine=f"forge-template=={ENGINE_VERSION}",
        python=_PYTHON,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def shim_scripts_dir(e2e_child_env: dict[str, str]) -> Iterator[Path]:
    """A throwaway venv with the `git`/`uv` fault-injection shim installed
    (`tests/fake_tools.py`) -- its `Scripts`/`bin` directory, to prepend ahead
    of a client's own `PATH` for the one call under test.
    """
    with tempfile.TemporaryDirectory(prefix="create-forge-fake-tools-") as tmp:
        root = Path(tmp)
        wheel = build_shim_wheel(root)
        venv = root / "shim-venv"
        created = run(["uv", "venv", str(venv)], root, env=e2e_child_env)
        assert_success(created, "shim venv creation")
        installed = run(
            ["uv", "pip", "install", "--python", str(venv_python(venv)), str(wheel)],
            root,
            env=e2e_child_env,
        )
        assert_success(installed, "shim wheel installation")
        yield venv_script(venv, "git").parent


@pytest.fixture(scope="session")
def fake_engine_wheel(e2e_child_env: dict[str, str]) -> Iterator[Path]:
    """The `forge_template` look-alike `--engine-source` provisions
    (`tests/fake_tools.py`), built once per session.
    """
    del e2e_child_env  # building needs no subprocess; kept for fixture symmetry
    with tempfile.TemporaryDirectory(prefix="create-forge-fake-engine-") as tmp:
        yield build_fake_engine_wheel(Path(tmp))


def _shim_env(
    client: InstalledClient, shim_scripts_dir: Path, *, real_git: str, real_uv: str
) -> dict[str, str]:
    """`client.env` with the shim ahead of it on `PATH`, and the real tools it
    delegates to named -- never the client's own venv `uv`, which the shim
    must not shadow itself when it delegates.
    """
    env = dict(client.env)
    path_key = next((key for key in env if key.upper() == "PATH"), "PATH")
    env[path_key] = f"{shim_scripts_dir}{os.pathsep}{env.get(path_key, '')}"
    env["CF_FAKE_REAL_GIT"] = real_git
    env["CF_FAKE_REAL_UV"] = real_uv
    return env


# --------------------------------------------------------------------------- #
# The lanes are what they claim to be                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lane", LANES, ids=_lane_id)
def test_the_lane_is_verified_not_assumed(
    encoding_client: InstalledClient, lane: EncodingLane
) -> None:
    """`ambient`/`utf8-off` fail here rather than silently pass under the
    wrong setting if this host cannot give a genuinely non-UTF-8 environment
    (the acceptance criterion this whole module exists to satisfy); off
    Windows they are not meaningful and are skipped instead (module docstring).
    """
    if lane.windows_only and not is_windows():
        pytest.skip(f"lane {lane.name!r} is only meaningful on Windows")
    measured = probe(encoding_client.python, lane_env(encoding_client.env, lane))
    require_lane(lane, measured)


# --------------------------------------------------------------------------- #
# Non-ASCII paths: generation, doctor, and update survive every lane          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lane", LANES, ids=_lane_id)
def test_generation_into_a_non_ascii_path_survives_every_lane(
    encoding_client: InstalledClient, lane: EncodingLane, tmp_path: Path
) -> None:
    """The regression: the success panel names the destination path, which
    used to raise `UnicodeEncodeError` on a `cp1252` console for a path
    outside its codepage -- *after* the project was already written and
    committed (`cli._harden_console_encoding`, CF-23.02).
    """
    if lane.windows_only and not is_windows():
        pytest.skip(f"lane {lane.name!r} is only meaningful on Windows")
    env = lane_env(encoding_client.env, lane)
    require_lane(lane, probe(encoding_client.python, env))

    dest = tmp_path / _NON_ASCII_SEGMENT / "widget"
    result = run(
        [str(encoding_client.console), *_new_args("Widget", dest)],
        tmp_path,
        env=env,
    )
    assert_success(result, f"generation into a non-ASCII path (lane {lane.name})")
    assert "Traceback" not in result.stdout + result.stderr
    assert (dest / "pyproject.toml").is_file()
    assert (dest / ".forge" / "generation.json").is_file()


@pytest.mark.parametrize("lane", LANES, ids=_lane_id)
def test_update_through_a_non_ascii_path_survives_every_lane(
    encoding_client: InstalledClient, lane: EncodingLane, tmp_path: Path
) -> None:
    if lane.windows_only and not is_windows():
        pytest.skip(f"lane {lane.name!r} is only meaningful on Windows")
    env = lane_env(encoding_client.env, lane)
    require_lane(lane, probe(encoding_client.python, env))

    dest = tmp_path / _NON_ASCII_SEGMENT / "widget"
    generated = run(
        [str(encoding_client.console), *_new_args("Widget", dest)], tmp_path, env=env
    )
    assert_success(generated, f"generation for update (lane {lane.name})")

    dry_run = run([str(encoding_client.console), "update", "--dry-run"], dest, env=env)
    assert_success(dry_run, f"update --dry-run (lane {lane.name})")
    assert "Traceback" not in dry_run.stdout + dry_run.stderr

    update = run([str(encoding_client.console), "update"], dest, env=env)
    assert_success(update, f"update (lane {lane.name})")
    assert "Traceback" not in update.stdout + update.stderr


def test_doctor_reports_a_non_ascii_git_identity(
    encoding_client: InstalledClient, tmp_path: Path
) -> None:
    """A real, not-injected, non-ASCII value: `doctor` shows it (`git`'s own
    UTF-8 output, `capture.decode_diagnostic`), it must not crash printing it.

    Under the `utf8-on` lane deliberately: this test's own harness
    (`tests.process.run_text`, through `installed_client.run`) decodes the
    child's stdout as UTF-8 with no override, so it needs the console's own
    output encoding to actually be UTF-8 to read the value back correctly --
    that the value is not lost or garbled under the *other* lanes is what the
    `Traceback`-free assertions in the non-ASCII path tests above already
    prove without needing to decode anything console-side.
    """
    identity = "Café Ünïcode"
    env = lane_env(dict(encoding_client.env), UTF8_ON)
    # `_git_config` reads the *configured* identity, not `GIT_AUTHOR_NAME`
    # (which only names commits, not `git config --get`'s answer) -- write a
    # real `--global` config into an isolated `HOME`/`USERPROFILE`
    # (`XDG_CONFIG_HOME` is create-forge's own config, not git's). Windows
    # environment blocks are case-insensitive but a plain `dict` is not, so
    # both are found by their existing case rather than assumed to be exactly
    # `"HOME"`/`"USERPROFILE"` (found by hand: this host's shell exports
    # `Home`, and a literal overwrite left the stale one sitting alongside it).
    #
    # The value is written to `.gitconfig` directly, in UTF-8, rather than via
    # `git config --global user.name <value>` -- passed a non-ASCII value as
    # an argv element, this host's `git.exe` (found by hand: reproduces with a
    # plain Python `subprocess.run`, not with the identical command run from
    # an MSYS2 shell) narrows it through the console codepage before writing,
    # corrupting anything outside ASCII. That is a platform/tool interaction
    # in how this fixture would otherwise *set up* the scenario, not a
    # create-forge bug and not what this test is proving -- the write is
    # replaced with one that cannot suffer it, and `git config --get` (a pure
    # read, no non-ASCII argv) still exercises the real binary `_git_config`
    # calls.
    config_home = tmp_path / "git-home"
    config_home.mkdir()
    (config_home / ".gitconfig").write_text(
        f"[user]\n\tname = {identity}\n\temail = e2e@example.invalid\n",
        encoding="utf-8",
    )
    for name in ("HOME", "USERPROFILE"):
        key = next((k for k in env if k.upper() == name), name)
        env[key] = str(config_home)

    result = run([str(encoding_client.console), "doctor"], tmp_path, env=env)

    assert_success(result, "doctor with a non-ASCII git identity")
    assert identity in result.stdout
    assert "Traceback" not in result.stdout + result.stderr

    json_result = run(
        [str(encoding_client.console), "doctor", "--json"], tmp_path, env=env
    )
    assert json_result.returncode in (0, 1), json_result.stdout + json_result.stderr
    # `json.dumps`'s default `ensure_ascii=True` escapes it as `é` etc,
    # not the raw characters -- parse before comparing, as any JSON consumer
    # would, rather than searching the escaped text for the literal string.
    payload = json.loads(json_result.stdout)
    identity_check = next(c for c in payload["checks"] if c["name"] == "git identity")
    assert identity in identity_check["detail"]


# --------------------------------------------------------------------------- #
# Invalid diagnostic bytes, through a real git/uv shim on PATH                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lane", LANES, ids=_lane_id)
def test_doctor_survives_undecodable_git_config_bytes(
    encoding_client: InstalledClient,
    shim_scripts_dir: Path,
    lane: EncodingLane,
    tmp_path: Path,
) -> None:
    """`git config --get` writing bytes with no valid UTF-8 reading: the
    diagnostic rule (`decode_diagnostic`) replaces them with `U+FFFD`, which
    is itself outside `cp1252` -- doubling as a second, independent proof that
    `_harden_console_encoding` is what keeps `doctor`'s table from raising,
    this time for content this package chose to substitute, not a path the
    user chose.
    """
    if lane.windows_only and not is_windows():
        pytest.skip(f"lane {lane.name!r} is only meaningful on Windows")
    env = lane_env(
        _shim_env(
            encoding_client,
            shim_scripts_dir,
            real_git="git",
            real_uv=str(encoding_client.uv),
        ),
        lane,
    )
    require_lane(lane, probe(encoding_client.python, env))
    env["CF_FAKE_GIT_MODE"] = "bad-config-bytes"

    result = run([str(encoding_client.console), "doctor"], tmp_path, env=env)

    # `UNDECODABLE` has no cp1252 reading either (it is deliberately
    # undefined in *both* encodings), so what matters is only that
    # `decode_diagnostic`'s substitution (`U+FFFD`) reaches the console
    # without raising -- not a byte-for-byte comparison against content that
    # cannot itself be decoded as either.
    assert result.returncode in (0, 1), result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_doctor_survives_undecodable_uv_version_bytes(
    encoding_client: InstalledClient, shim_scripts_dir: Path, tmp_path: Path
) -> None:
    env = _shim_env(
        encoding_client,
        shim_scripts_dir,
        real_git="git",
        real_uv=str(encoding_client.uv),
    )
    env["CF_FAKE_UV_MODE"] = "bad-version-bytes"

    result = run([str(encoding_client.console), "doctor"], tmp_path, env=env)

    assert result.returncode in (0, 1), result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_a_failing_git_commit_shows_the_fixed_warning_never_the_secret(
    encoding_client: InstalledClient, shim_scripts_dir: Path, tmp_path: Path
) -> None:
    """`lifecycle._run_git`'s own rule: a fixed warning, never the child's raw
    output, which the real `git` binary would otherwise have carried straight
    through to `new`'s own warnings. The lifecycle's warn-and-continue posture
    (ADR 0041 rule 4) means `new` still exits `0` and the project is kept.
    """
    secret = "https://user:hunter2@example.com/private/repo"  # noqa: S105 - fixture
    env = _shim_env(
        encoding_client,
        shim_scripts_dir,
        real_git="git",
        real_uv=str(encoding_client.uv),
    )
    env["CF_FAKE_GIT_MODE"] = "fail-commit"
    env["CF_FAKE_SECRET_URL"] = secret
    dest = tmp_path / "commit-failure"

    result = run(
        [str(encoding_client.console), *_new_args("Commit Failure", dest)],
        tmp_path,
        env=env,
    )

    assert_success(result, "new with a failing git commit")
    assert secret not in result.stdout
    assert secret not in result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert (dest / "pyproject.toml").is_file()  # the sound render is kept


# --------------------------------------------------------------------------- #
# The engine-source worker's strict protocol, through a real fake engine     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "mode",
    ["malformed-utf8", "byte-order-mark", "empty-body", "non-json"],
)
def test_worker_rejects_a_corrupted_response(
    encoding_client: InstalledClient, fake_engine_wheel: Path, mode: str, tmp_path: Path
) -> None:
    """Each way `capture.parse_protocol_json` can refuse a body
    (`tests/test_capture.py`, `tests/test_subprocess_decoding.py`), proven
    here through the real out-of-process worker talking to a real (if fake)
    provisioned engine, not a monkeypatched `subprocess.run`.
    """
    env = dict(encoding_client.env)
    env["CF_FAKE_ENGINE_MODE"] = mode
    dest = tmp_path / "engine-source-rejected"

    result = run(
        [
            str(encoding_client.console),
            *_new_args("Rejected", dest),
            "--engine-source",
            str(fake_engine_wheel),
        ],
        tmp_path,
        env=env,
        timeout=120,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "unreadable response" in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert not dest.exists()


def test_engine_source_connection_failure_is_explained_not_echoed(
    encoding_client: InstalledClient, tmp_path: Path
) -> None:
    """A real `uv` failure (nothing answers on this loopback port) -- the
    fixed message, never `uv`'s own output, which could carry index
    credentials (`engine_source._run_uv`'s rule). The source itself is
    deliberately shown once, in the confirmation panel this route always
    prints before it runs anything -- that is the intended trust warning
    (`_confirm_third_party`, proven by `test_warning_renders_source_as_literal
    _text` in `tests/test_engine_source.py`), not a leak; a source carrying
    embedded credentials is rejected before that panel even exists, at
    `sources.validate_source` (`tests/test_sources.py`). What this proves is
    narrower and specific to a real, out-of-process `uv` failure: the fixed
    message is *all* that follows the panel, not `uv`'s own output appended
    to it.
    """
    dest = tmp_path / "engine-source-connection-failure"
    source = "https://127.0.0.1:1/nonexistent-private-repo.git"
    fixed_message = (
        "could not provision the engine source. Check the --engine-source "
        "path or VCS URL, --engine-ref, network access, and repository "
        "permissions, then retry."
    )

    result = run(
        [
            str(encoding_client.console),
            *_new_args("ConnFail", dest),
            "--engine-source",
            source,
        ],
        tmp_path,
        env=encoding_client.env,
        timeout=120,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    # Rich word-wraps the panel and the message to a console width even when
    # output is only piped, not a real terminal -- collapse whitespace before
    # comparing, the same normalisation every other prose-matching assertion
    # in this repository uses for exactly that reason. Splitting on the fixed
    # message's own known start, rather than trying to locate the end of the
    # (bordered, also-wrapped) confirmation panel above it, sidesteps having
    # to reconstruct exactly where Rich puts the border line.
    flat = " ".join(combined.split())
    _before, found, after_message = flat.partition(fixed_message)
    assert found, combined  # the fixed message must actually appear
    assert not after_message.strip(), combined  # and nothing else follows it
    assert "Traceback" not in combined
    assert not dest.exists()
