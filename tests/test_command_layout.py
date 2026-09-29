"""Enforces the two structural rules CF-25.03 introduced for `cli.py` and
`src/create_forge/commands/*` -- both documented (ADR 0014, extended by ADR
0060 decision 3; `docs/cli-command-map.md`'s "Test map" section) but, before
this file, not actually tested:

1. Neither `cli.py` nor any `commands/*` module imports `copier` or any of
   `create_forge.runner`/`pipeline`/`engine`/`engine_source`/`update` at
   module scope -- only lazily, inside a function body. This is what lets a
   plain `pip install create-forge` (no `legacy` extra, no scaffold ever
   run) import `cli.py` without `copier` installed. `tests/test_engine_
   contract.py::test_shipped_cli_modules_do_not_import_the_engine` already
   guards `forge_template` the same way; this widens the same shape to the
   other lazily-reached modules.
2. No `commands/*` module imports `create_forge.cli` (ADR 0060 decision 3:
   dependency direction is one-way, `cli` -> `commands/*`, never back).
3. A command module's private/use-site seams (a `monkeypatch.setattr` onto
   a `cli`/`commands.*` module, or a direct call through one) are reached
   only from that module's own mirror test file(s) -- CF-25.03's design
   decision for removing "accidental private-module coupling" (see the
   issue's own acceptance criterion). A genuine exception is recorded in
   `_ALLOWED_CROSS_MODULE_COUPLING` with a reason, not silently permitted.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.source_tree import SRC_ROOT, production_modules

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = REPO_ROOT / "tests"

# --------------------------------------------------------------------------- #
# 1 & 2: module-scope import rules for cli.py and commands/*                  #
# --------------------------------------------------------------------------- #

_LAZY_ONLY = frozenset(
    {"copier", "runner", "pipeline", "engine", "engine_source", "update"}
)


def _cli_and_command_modules() -> list[Path]:
    return [
        p
        for p in production_modules()
        if p == SRC_ROOT / "cli.py" or p.parent.name == "commands"
    ]


def _module_scope_import_roots(path: Path) -> set[str]:
    """Every module a *top-level* `import`/`from` statement in `path` names,
    reduced to its first dotted component past `create_forge` (so
    `from create_forge import pipeline` and `from create_forge.pipeline
    import X` are both just `pipeline`) -- deliberately not `ast.walk`,
    which would also catch a lazy import nested inside a function body or an
    `if TYPE_CHECKING:` block (both fine; only true module-scope statements
    in `tree.body` are the rule).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                roots.add(
                    parts[1]
                    if parts[0] == "create_forge" and len(parts) > 1
                    else parts[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "create_forge":
                if len(parts) > 1:
                    roots.add(parts[1])
                else:
                    roots.update(alias.name for alias in node.names)
            else:
                roots.add(parts[0])
    return roots


def test_cli_and_commands_import_copier_and_the_engine_lazily_only() -> None:
    for path in _cli_and_command_modules():
        roots = _module_scope_import_roots(path)
        offenders = roots & _LAZY_ONLY
        assert not offenders, (
            f"{path.relative_to(SRC_ROOT)} imports {sorted(offenders)} at "
            "module scope -- ADR 0014/0060 decision 3 requires these lazy, "
            "inside the function that needs them, so a plain install (no "
            "`legacy` extra, no scaffold ever run) can import this module "
            "with copier/forge_template absent."
        )


def test_no_command_module_imports_cli() -> None:
    """ADR 0060 decision 3: dependency direction is one-way. `commands/*`
    may be imported by `cli.py`; it must never import `cli.py` back.
    """
    for path in production_modules():
        if path.parent.name != "commands":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in {
                "create_forge.cli",
                "create_forge",
            }:
                names = {alias.name for alias in node.names}
                assert "cli" not in names, (
                    f"{path.relative_to(SRC_ROOT)} imports create_forge.cli "
                    "-- commands/* must never import back into cli.py "
                    "(ADR 0060 decision 3)."
                )
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name == "create_forge.cli" for alias in node.names
                ), f"{path.relative_to(SRC_ROOT)} imports create_forge.cli directly."


# --------------------------------------------------------------------------- #
# 3: private/use-site coupling stays inside each module's own mirror file(s)  #
# --------------------------------------------------------------------------- #

# Every cli.py/commands/* module, and the test file(s) allowed to reach its
# private names or use-site bindings via `monkeypatch.setattr` or a direct
# call. A module split across several route-specific test files (new.py,
# selection.py) lists all of them -- each still only reaches its own real
# module's seams, never another module's.
_MIRRORS: dict[str, frozenset[str]] = {
    "create_forge.cli": frozenset({"tests/test_cli.py"}),
    "create_forge.commands._output": frozenset(
        {"tests/commands/test_output.py", "tests/test_cli.py"}
    ),
    "create_forge.commands.doctor": frozenset(
        {"tests/commands/test_doctor.py", "tests/test_subprocess_decoding.py"}
    ),
    "create_forge.commands.catalogue": frozenset({"tests/commands/test_catalogue.py"}),
    "create_forge.commands.config": frozenset(
        {"tests/commands/test_config_command.py"}
    ),
    "create_forge.commands.update": frozenset(
        {
            "tests/commands/test_update_copier_route.py",
            "tests/commands/test_update_engine_route.py",
        }
    ),
    "create_forge.commands.new": frozenset(
        {
            "tests/commands/test_new_copier_route.py",
            "tests/commands/test_new_engine_route.py",
            "tests/commands/test_new_selection.py",
        }
    ),
    "create_forge.commands.selection": frozenset(
        {"tests/commands/test_new_selection.py"}
    ),
}

# `_output.console`/`_output.err` are the designated shared patch points
# (module docstring, `commands/_output.py`) -- any test file may read or
# patch them, regardless of which command it exercises.
_ALWAYS_ALLOWED = frozenset(
    {
        ("create_forge.commands._output", "console"),
        ("create_forge.commands._output", "err"),
    }
)

# (test file, module, attribute) -> reason. A deliberate exception to the
# mirror-file rule above, not a silent gap.
_ALLOWED_CROSS_MODULE_COUPLING: dict[tuple[str, str, str], str] = {
    (
        "tests/test_subprocess_decoding.py",
        "create_forge.commands.doctor",
        "_uv_version",
    ): (
        "CF-23.01's decoding-policy contract (ADR 0055) tests exactly this "
        "helper's own decode behaviour, not doctor's other orchestration."
    ),
    (
        "tests/test_subprocess_decoding.py",
        "create_forge.commands.doctor",
        "_git_config",
    ): (
        "CF-23.01's decoding-policy contract (ADR 0055) tests exactly this "
        "helper's own decode behaviour, not doctor's other orchestration."
    ),
    ("tests/test_sources.py", "create_forge.commands.new", "_confirm_third_party"): (
        "Proves this shared warning's own credential-hiding is real defence "
        "in depth, not only reachable via cli.py's upstream validate_source "
        "gate -- a credential-bearing --template-url is rejected before "
        "_confirm_third_party is ever reached through the real CLI, so this "
        "branch is otherwise untestable end to end."
    ),
    (
        "tests/test_engine_source.py",
        "create_forge.commands.new",
        "_confirm_third_party",
    ): (
        "Proves the --engine-source wording of the same shared warning "
        "renders a source as literal text, without paying for a real "
        "out-of-process provisioning run just to reach it -- "
        "tests/test_e2e_installed_encoding.py is the real, paid-for proof."
    ),
}


def _module_alias_map(tree: ast.AST) -> dict[str, str]:
    """`{local alias -> "create_forge.cli" | "create_forge.commands.X"}` for
    every import in a test file that binds one of these modules by name,
    e.g. `from create_forge.commands import doctor as doctor_module` or
    `from create_forge.cli import app` (which binds no whole-module alias
    and so is not included; only a whole-module bind can be the target of
    `monkeypatch.setattr(alias, "name", ...)`).
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "create_forge.commands":
            for alias in node.names:
                aliases[alias.asname or alias.name] = (
                    f"create_forge.commands.{alias.name}"
                )
        elif isinstance(node, ast.ImportFrom) and node.module == "create_forge":
            for alias in node.names:
                if alias.name == "cli":
                    aliases[alias.asname or alias.name] = "create_forge.cli"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "create_forge.cli":
                    aliases[alias.asname or "cli"] = "create_forge.cli"
    return aliases


def _coupling_sites(path: Path, aliases: dict[str, str]) -> set[tuple[str, str]]:
    """`{(module, attribute)}` this test file reaches via `monkeypatch.
    setattr(alias, "attribute", ...)` or a direct `alias.attribute` access,
    for every `alias` this file bound to a tracked module.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sites: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setattr"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "monkeypatch"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in aliases
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            sites.add((aliases[node.args[0].id], node.args[1].value))
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr.startswith("_")
        ):
            sites.add((aliases[node.value.id], node.attr))
    return sites


def test_private_command_seams_are_reached_only_from_their_own_test_module() -> None:
    violations: list[str] = []
    for test_path in sorted(TESTS_ROOT.rglob("test_*.py")):
        rel = test_path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        aliases = _module_alias_map(tree)
        if not aliases:
            continue
        for module, attr in sorted(_coupling_sites(test_path, aliases)):
            if (module, attr) in _ALWAYS_ALLOWED:
                continue
            mirrors = _MIRRORS.get(module, frozenset())
            if rel in mirrors:
                continue
            if (rel, module, attr) in _ALLOWED_CROSS_MODULE_COUPLING:
                continue
            violations.append(
                f"{rel} reaches {module}.{attr} directly, but is not that "
                f"module's own mirror test file "
                f"({sorted(mirrors) or 'none registered'}) and is not on "
                "the _ALLOWED_CROSS_MODULE_COUPLING allowlist."
            )
    assert not violations, (
        "CF-25.03's coupling rule: move these to their module's mirror "
        "file, drive them through the public CLI or a lower-level module "
        "instead, or add a reasoned _ALLOWED_CROSS_MODULE_COUPLING entry.\n"
        + "\n".join(violations)
    )
