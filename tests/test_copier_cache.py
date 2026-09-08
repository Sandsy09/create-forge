"""ADR 0039: `runner` models where Copier keeps its git-mirror cache and
whether create-forge could use it, so `doctor` can report it and a cache
failure can be explained instead of misattributed to the network. This pins
that model to Copier's own resolver and exercises the non-destructive probe.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Copier's own resolver. Private and relocated between supported releases --
# imported here, in a test only, precisely so a drift fails CI rather than
# `doctor` silently reporting a stale rule. Shipped code never imports it.
from copier._vcs import _get_cache_dir

from create_forge import runner
from create_forge.runner import CacheLocation, cache_probe, copier_cache_location


@pytest.fixture(autouse=True)
def _no_ambient_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COPIER_CACHE_DIR", raising=False)


def test_default_location_matches_copiers_own_resolver() -> None:
    location = copier_cache_location()

    assert location.overridden is False
    assert location.path == _get_cache_dir()


def test_override_is_used_verbatim_with_no_git_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "corp cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(override))

    location = copier_cache_location()

    assert location.overridden is True
    assert location.path == override
    assert location.path == _get_cache_dir()


def test_empty_override_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPIER_CACHE_DIR", "")

    location = copier_cache_location()

    assert location.overridden is False
    assert location.path == _get_cache_dir()


def test_probe_passes_a_writable_existing_cache(tmp_path: Path) -> None:
    (tmp_path / "cache").mkdir()

    probe = cache_probe(CacheLocation(path=tmp_path / "cache", overridden=True))

    assert probe.exists is True
    assert probe.writable is True


def test_probe_never_creates_a_missing_cache_directory(tmp_path: Path) -> None:
    missing = tmp_path / "not yet" / "git"

    probe = cache_probe(CacheLocation(path=missing, overridden=True))

    assert probe.exists is False
    assert probe.writable is True  # the existing tmp_path ancestor accepts writes
    assert not missing.exists()


def test_probe_leaves_an_existing_cache_untouched(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "abc123.git").mkdir()
    before = sorted(p.name for p in cache.iterdir())

    cache_probe(CacheLocation(path=cache, overridden=True))

    assert sorted(p.name for p in cache.iterdir()) == before


def test_probe_reports_a_denied_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Portable coverage of the unwritable branch -- Windows CI cannot make a
    directory unwritable with a permission bit.
    """
    cache = tmp_path / "cache"
    cache.mkdir()

    def deny(directory: Path) -> None:
        raise PermissionError(13, "denied", str(directory))

    monkeypatch.setattr(runner, "_write_probe", deny)

    probe = cache_probe(CacheLocation(path=cache, overridden=True))

    assert probe.exists is True
    assert probe.writable is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_probe_reports_a_real_unwritable_directory(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o500)
    try:
        probe = cache_probe(CacheLocation(path=cache, overridden=True))
        assert probe.writable is False
    finally:
        cache.chmod(0o700)


def test_a_cache_path_containing_spaces_resolves_and_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "Program Files" / "forge cache"
    override.mkdir(parents=True)
    monkeypatch.setenv("COPIER_CACHE_DIR", str(override))

    location = copier_cache_location()

    assert location.path == override
    assert cache_probe(location).writable is True
