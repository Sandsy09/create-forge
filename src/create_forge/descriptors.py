"""Engine-free component-descriptor views shared by both generation routes.

`prompts.py` already defines `ArchetypeChoice`/`ComponentOptionSpec` as
structural `Protocol`s so a shipped module can describe the engine's
`ComponentDescriptor`/`ComponentOption` shape without importing
`forge_template` (ADR 0013). `pipeline.Catalogue` needs two attributes those
narrower Protocols don't carry -- `kind` and `requires` -- because it groups
descriptors by kind and resolves requirement ids from them (CF-13.03,
ADR 0028).

This module extends the same pattern one attribute further: `DescriptorView`
(with its own `RelationView`/`OptionView` members) is the Protocol
`pipeline.Catalogue.descriptors` is typed against. It is a strict superset of
`ArchetypeChoice`, so every function in `prompts.py`/`cli.py` already typed
against `ArchetypeChoice` accepts a `DescriptorView` unchanged -- no call site
elsewhere needs to change for either generation route.

It is satisfied structurally by two different concrete shapes:

- the engine's own `ComponentDescriptor`/`ComponentOption`/`ComponentRelation`,
  used unchanged by the default, in-process `new` route (`engine.py`);
- the frozen, `extra="forbid"` models below, which `engine_source.py`
  deserialises from `_engine_worker.py`'s JSON response on the
  `--engine-source` override route (ADR 0044) -- a real engine type cannot
  cross that process boundary, so the wire contract is this module's own
  minimal shape instead.

Deliberately engine-free: nothing here imports `forge_template`, not even
under `TYPE_CHECKING` -- `tests/test_engine_contract.py`'s `_SHIPPED_MODULES`
guard covers this module for exactly that reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Sequence


class OptionView(Protocol):
    """The engine's `ComponentOption` shape `prompts.ComponentOptionSpec` needs.

    Structurally identical to `prompts.ComponentOptionSpec` -- duplicated
    rather than imported, since `prompts.py` is itself a shipped, engine-free
    module and a cross-import between the two would gain nothing a plain
    structural match doesn't already give both callers.
    """

    @property
    def name(self) -> str:
        """The option's identifier within its component's namespace."""
        ...

    @property
    def type(self) -> str:
        """One of `string`, `integer`, `boolean`, `string_list`."""
        ...

    @property
    def required(self) -> bool:
        """Whether the component rejects generation without this option."""
        ...

    @property
    def default(self) -> object:
        """The value applied when the option is left unanswered."""
        ...

    @property
    def choices(self) -> Sequence[object]:
        """A closed set of acceptable values, or empty for an open one."""
        ...

    @property
    def description(self) -> str:
        """The one-line explanation shown as the prompt message."""
        ...

    @property
    def format(self) -> str | None:
        """An additional shape constraint (e.g. `pep440`), or `None`."""
        ...


class RelationView(Protocol):
    """The engine's `ComponentRelation` shape `Catalogue.required_ids` needs."""

    @property
    def id(self) -> str:
        """The related component's canonical identifier."""
        ...


class DescriptorView(Protocol):
    """The engine's `ComponentDescriptor` shape `pipeline.Catalogue` needs.

    A superset of `prompts.ArchetypeChoice`: adds `kind` (`Catalogue.of_kind`,
    `.kind_of`) and `requires` (`Catalogue.required_ids`) to the
    `id`/`name`/`description`/`options` quartet that module already relies on.
    Read-only properties, not plain attributes, for the same reason
    `ArchetypeChoice` uses them: both the engine's frozen `ComponentDescriptor`
    and this module's own frozen `Descriptor` satisfy a read-only protocol
    member without either knowing about the other.
    """

    @property
    def id(self) -> str:
        """The canonical component identifier."""
        ...

    @property
    def name(self) -> str:
        """The display name shown in the prompt."""
        ...

    @property
    def description(self) -> str:
        """The one-line description shown alongside the name."""
        ...

    @property
    def kind(self) -> str:
        """One of `archetype`, `capability`, `platform`."""
        ...

    @property
    def requires(self) -> Sequence[RelationView]:
        """Direct requirement relations, each naming a required component id."""
        ...

    @property
    def options(self) -> Sequence[OptionView]:
        """This component's own declared, directly-promptable options."""
        ...


class _WireModel(BaseModel):
    """Shared immutable, extra-forbidding wire-model behaviour.

    Mirrors `forge_template`'s own `_PublicModel` base without importing it --
    this module must stay importable with no engine present -- except for
    `strict=True`: these models parse `_engine_worker.py`'s JSON, and JSON has
    no tuple type, so a lax (non-strict) mode is what actually lets a
    plain-list `requires`/`options`/`choices` field coerce to the `tuple[...]`
    shape `DescriptorView`/`OptionView` declare. The engine's own models stay
    strict because internal, already-Python-typed construction is what
    populates them; this module's models exist specifically to cross a JSON
    boundary, where strict tuple-only input would reject every real response.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class Relation(_WireModel):
    """`RelationView`, deserialised from `_engine_worker.py`'s JSON."""

    id: str


class Option(_WireModel):
    """`OptionView`, deserialised from `_engine_worker.py`'s JSON."""

    name: str
    type: str
    required: bool
    default: object = None
    choices: tuple[object, ...] = ()
    description: str = ""
    format: str | None = None


class Descriptor(_WireModel):
    """`DescriptorView`, deserialised from `_engine_worker.py`'s JSON.

    Carries only the fields the client actually consumes (CF-ROADMAP-01-AC-02
    -- no component semantics or resources are copied downstream): not
    `version`, `projectspec_protocols`, `requires_python`, or `conflicts`,
    which nothing in `create_forge` reads today.
    """

    id: str
    name: str
    description: str
    kind: str
    requires: tuple[Relation, ...] = ()
    options: tuple[Option, ...] = ()
