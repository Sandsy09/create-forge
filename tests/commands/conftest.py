"""Fixtures shared by more than one `tests/commands/*` module.

CF-25.03 moved these out of `tests/test_cli.py` unchanged: `_isolated_config`
is needed by every command (`new`, `list`, `update`, `doctor`, `config` all
read config/env), and `recorder` is needed by both `new` routes
(`test_new_copier_route.py`, `test_new_engine_route.py`,
`test_new_selection.py`) and `test_update_copier_route.py`, which drives
`new --legacy` inside one of its own tests. A module needing only one of the
two keeps requesting it by name; pytest resolves it from here either way.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import create_forge.runner as runner_module
from create_forge.config import UserConfig, config_path
from create_forge.runner import ScaffoldRequest


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point config_path() at a throwaway directory with no FORGE_* leakage.

    Without this, `new`/`doctor`/`config` would read the developer's real
    ~/.config/create-forge/config.toml and environment, making these tests
    depend on who runs them -- the same reasoning as test_config.py's
    _clean_forge_env, extended to also isolate the file path.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # doctor now probes Copier's cache directory; keep that off the real
    # user cache the same way config is kept off the real config file.
    monkeypatch.setenv("COPIER_CACHE_DIR", str(tmp_path / "copier-cache"))
    for field in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{field.upper()}", raising=False)
    return config_path()


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> list[ScaffoldRequest]:
    calls: list[ScaffoldRequest] = []

    def fake_scaffold(request: ScaffoldRequest) -> None:
        calls.append(request)

    # Patch the name on `runner`, not `cli`/`commands.new` -- since ADR 0040
    # (CF-18.01) made `copier` the optional `legacy` extra, the `--legacy`
    # route imports `scaffold` from `create_forge.runner` lazily, inside the
    # function body, on every invocation. That late-binding `from
    # create_forge.runner import scaffold` re-reads the module attribute at
    # call time, so patching it here is what actually reaches `new --legacy`.
    monkeypatch.setattr(runner_module, "scaffold", fake_scaffold)
    return calls
