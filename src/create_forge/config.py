"""User configuration.

Purely a convenience layer: it remembers answers you would otherwise retype on
every scaffold. It deliberately cannot change which template is cloned — that
address is bundled with the release so the code being trusted is the code that
was reviewed. Use `--template-url` for a one-off override.

Resolution order, lowest to highest precedence:

  1. built-in defaults
  2. $XDG_CONFIG_HOME/create-forge/config.toml (or ~/.config/...)
  3. FORGE_* environment variables
  4. command line flags (applied by cli.py, not here)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

_ENV_PREFIX = "FORGE_"
_FILENAME = "config.toml"


class UserConfig(BaseModel):
    """Remembered answers, all optional."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    author_name: str | None = None
    author_email: str | None = None
    github_org: str | None = None
    default_template: str | None = None

    @model_validator(mode="after")
    def _blank_is_unset(self) -> Self:
        # A key present but empty in TOML should behave as absent rather than
        # pre-filling a prompt with "".
        cleaned = {
            k: (v.strip() or None) if isinstance(v, str) else v
            for k, v in self.__dict__.items()
        }
        if cleaned != self.__dict__:
            return self.model_copy(update=cleaned)
        return self

    def as_answers(self) -> dict[str, object]:
        """The subset usable as template answers."""
        return {
            key: value
            for key, value in (
                ("author_name", self.author_name),
                ("author_email", self.author_email),
                ("github_org", self.github_org),
            )
            if value is not None
        }


def config_path() -> Path:
    """Where the config file is expected to live."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "create-forge" / _FILENAME


def load_config(path: Path | None = None) -> UserConfig:
    """Read config from disk and environment.

    A malformed config is the user's to fix, so it raises with the path rather
    than being silently ignored — silently ignoring it produces the far more
    confusing failure of settings that appear to do nothing.
    """
    target = path or config_path()
    data: dict[str, object] = {}

    if target.is_file():
        try:
            data = tomllib.loads(target.read_text("utf-8"))
        except tomllib.TOMLDecodeError as exc:
            msg = f"{target} is not valid TOML: {exc}"
            raise ValueError(msg) from exc
        except OSError as exc:
            msg = f"Could not read {target}: {exc}"
            raise ValueError(msg) from exc

    data |= _from_env()

    try:
        return UserConfig.model_validate(data)
    except ValidationError as exc:
        msg = f"Invalid configuration in {target}:\n{exc}"
        raise ValueError(msg) from exc


def _from_env() -> dict[str, object]:
    """Environment overrides, e.g. FORGE_GITHUB_ORG."""
    return {
        field: os.environ[key]
        for field in UserConfig.model_fields
        if (key := f"{_ENV_PREFIX}{field.upper()}") in os.environ
    }


def write_example(path: Path | None = None) -> Path:
    """Write a commented starter config. Never overwrites."""
    target = path or config_path()
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# create-forge configuration.\n"
        "# These pre-fill prompts; every value is optional.\n"
        "\n"
        '# author_name = "Your Name"\n'
        '# author_email = "you@example.com"\n'
        '# github_org = "your-org"\n'
        '# default_template = "library"\n',
        encoding="utf-8",
    )
    return target