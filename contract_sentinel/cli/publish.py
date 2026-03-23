from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from contract_sentinel.config import Config
from contract_sentinel.domain.loader import load_marked_classes
from contract_sentinel.factory import get_parser, get_store
from contract_sentinel.services.publish import PublishReport, publish_contracts


def publish_to_store(
    path: Annotated[
        Path,
        typer.Option("--path", help="Directory to scan for @contract classes."),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show all schemas, including unchanged ones."),
    ] = False,
) -> None:
    """Publish local schemas to the contract store."""
    config = Config()
    store = get_store(config)

    scan_path = path.resolve()

    # Insert cwd so that project-relative imports inside schema files resolve correctly.
    cwd_str = str(Path.cwd())
    if cwd_str not in sys.path:
        sys.path.insert(0, cwd_str)

    def loader() -> list[type]:
        return load_marked_classes(scan_path)

    report = publish_contracts(store, get_parser, loader, config)

    _print_publish_report(report, verbose=verbose)


def _print_publish_report(report: PublishReport, *, verbose: bool = False) -> None:
    """Print a PublishReport to stdout in a human-readable format."""
    header = "\nContract Publish Summary\n"
    header = typer.style(header, fg=typer.colors.CYAN)
    typer.echo(header)

    typer.echo(f"  Published: {len(report.published)}")
    typer.echo(f"  Updated:   {len(report.updated)}")
    typer.echo(f"  Unchanged: {len(report.unchanged)}")
    typer.echo(f"  Failed:    {len(report.failed)}")

    if report.published:
        typer.echo(typer.style("\n  Published schemas:", fg=typer.colors.GREEN))
        for key in report.published:
            typer.echo(f"    ✓ {key}")

    if report.updated:
        typer.echo(typer.style("\n  Updated schemas:", fg=typer.colors.YELLOW))
        for key in report.updated:
            typer.echo(f"    ↻ {key}")

    if report.failed:
        typer.echo(typer.style("\n  Failed schemas:", fg=typer.colors.RED))
        for failure in report.failed:
            typer.echo(f"    ✗ {failure.key}")
            typer.echo(f"      Reason: {failure.reason}")

    if verbose and report.unchanged:
        typer.echo(typer.style("\n  Unchanged schemas (skipped):", fg=typer.colors.BRIGHT_BLACK))
        for key in report.unchanged:
            typer.echo(f"    - {key}")

    typer.echo("")
