"""Command orchestration behind `cli.py`'s thin Typer layer (ADR 0060).

`cli.py` keeps the Typer `app`/`config_app` objects, `main()`, and one thin,
argument-shape-validating wrapper per command; the actual orchestration --
what each command does once its inputs are known -- lives in one module per
command here. Modules under this package never import `create_forge.cli`,
and never import `forge_template`/`copier` except lazily inside their own
functions (ADR 0013, ADR 0014, extended by ADR 0060 decision 3).
"""
