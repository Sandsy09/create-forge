"""load_config precedence, error behaviour, and write_example."""

from __future__ import annotations

from pathlib import Path

import pytest

from create_forge.config import UserConfig, load_config, write_example


@pytest.fixture(autouse=True)
def _clean_forge_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real FORGE_* variables in the developer's shell would otherwise leak
    # into these tests and make them depend on who runs them.
    for field in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{field.upper()}", raising=False)


def test_missing_file_returns_all_unset(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does-not-exist.toml")
    assert config == UserConfig()


def test_file_value_is_used_when_no_env_override(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('author_name = "File Name"\n', encoding="utf-8")
    config = load_config(path)
    assert config.author_name == "File Name"


def test_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "config.toml"
    path.write_text('author_name = "File Name"\n', encoding="utf-8")
    monkeypatch.setenv("FORGE_AUTHOR_NAME", "Env Name")
    config = load_config(path)
    assert config.author_name == "Env Name"


def test_malformed_toml_raises_with_the_path(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("not = [valid toml", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid TOML") as exc_info:
        load_config(path)
    assert str(path) in str(exc_info.value)


def test_unknown_field_raises_with_the_path(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('nonexistent_field = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid configuration") as exc_info:
        load_config(path)
    assert str(path) in str(exc_info.value)


def test_blank_string_is_treated_as_unset() -> None:
    # Constructed via model_validate, matching how load_config() builds it --
    # the mode="after" validator's model_copy(update=...) only takes effect
    # on that path, not on direct UserConfig(...) construction.
    config = UserConfig.model_validate({"author_name": "   "})
    assert config.author_name is None


def test_as_answers_omits_none_values() -> None:
    config = UserConfig(author_name="Alex")
    assert config.as_answers() == {"author_name": "Alex"}


def test_as_answers_excludes_default_template() -> None:
    # default_template steers which template is picked, not a scaffold
    # answer -- it must never leak into `data` passed to Copier.
    config = UserConfig(author_name="Alex", default_template="library")
    assert "default_template" not in config.as_answers()


def test_write_example_creates_a_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"
    result = write_example(path)
    assert result == path
    assert path.exists()


def test_write_example_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("custom content", encoding="utf-8")
    result = write_example(path)
    assert result == path
    assert path.read_text(encoding="utf-8") == "custom content"
