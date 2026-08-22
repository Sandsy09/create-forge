"""Real end-to-end update() against forge-template's actual tags.

test_update.py proves the mechanics offline against a throwaway fixture
template. This proves the same code path against the genuine registry entry:
scaffold at forge-template's first tag, update to its second, confirm it
succeeds and the answers file records the new version.

Marked network, like test_drift.py -- picked up by the existing `drift` CI
job (`pytest -m network`) with no workflow change beyond that job's rename,
and by the Monday cron. Skips rather than fails when GitHub is unreachable,
so a connectivity blip is never mistaken for a real regression -- same
reasoning as test_drift.py's `copier_yml` fixture.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from create_forge.registry import load_registry
from create_forge.runner import ScaffoldRequest, scaffold, update

pytestmark = pytest.mark.network


@pytest.fixture(autouse=True)
def _isolated_copier_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(
        "COPIER_SETTINGS_PATH", str(tmp_path / "unused-copier-settings.yml")
    )


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_update_against_the_real_template(tmp_path: Path) -> None:
    """forge-template has exactly two tags today: v0.1.0 and v0.1.1. If it
    ever gains a third, this still updates from the first to the second --
    the point is proving the update path works against a real template
    repository, not pinning an exact version pair forever."""
    load_registry.cache_clear()
    registry = load_registry()
    url = str(registry.get(registry.default_template).url)

    try:
        remote_tags = _git("ls-remote", "--tags", "--refs", url, cwd=tmp_path).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not reach {url}: {exc}")

    tags = sorted(
        line.rsplit("refs/tags/", 1)[-1] for line in remote_tags.splitlines() if line
    )
    if len(tags) < 2:
        pytest.skip(f"{url} does not have two tags yet to update between")
    old_tag, new_tag = tags[0], tags[1]

    project = tmp_path / "project"
    try:
        scaffold(
            ScaffoldRequest(
                src=url,
                dst=project,
                data={
                    "project_name": "Update Network Test",
                    "project_description": "update network test",
                },
                vcs_ref=old_tag,
            )
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"could not clone {url}: {exc}")

    # forge-template's own post-generation task already runs `git init` and
    # commits -- the README's "arrives already git-initialised" promise. Only
    # do it ourselves if that didn't happen, so this stays robust to that
    # task changing.
    if not (project / ".git").is_dir():
        _git("init", "--quiet", cwd=project)
        _git("config", "user.name", "Test", cwd=project)
        _git("config", "user.email", "test@example.com", cwd=project)
        _git("config", "core.autocrlf", "false", cwd=project)
        _git("add", "-A", cwd=project)
        _git("commit", "--quiet", "-m", "initial scaffold", cwd=project)

    update(project, vcs_ref=new_tag)

    answers = yaml.safe_load(
        (project / ".copier-answers.yml").read_text(encoding="utf-8")
    )
    assert answers["_commit"] == new_tag
