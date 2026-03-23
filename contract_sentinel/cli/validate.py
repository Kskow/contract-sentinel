from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from contract_sentinel.config import Config
from contract_sentinel.domain.loader import load_marked_classes
from contract_sentinel.factory import get_parser, get_store
from contract_sentinel.services.validate import (
    ContractsValidationReport,
    ValidationStatus,
    validate_local_contracts,
    validate_published_contracts,
)


def validate_local(
    path: Annotated[
        Path,
        typer.Option("--path", help="Directory to scan for @contract classes."),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the report but always exit 0."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show all contracts, including passed ones."),
    ] = False,
) -> None:
    """Validate local schemas against their published counterparts."""
    config = Config()
    store = get_store(config)

    scan_path = path.resolve()

    # Insert cwd so that project-relative imports inside schema files resolve correctly.
    cwd_str = str(Path.cwd())
    if cwd_str not in sys.path:
        sys.path.insert(0, cwd_str)

    def loader() -> list[type]:
        return load_marked_classes(scan_path)

    report = validate_local_contracts(store, get_parser, loader, config)

    print_report(report, verbose=verbose)

    if not dry_run and report.status == ValidationStatus.FAILED:
        raise typer.Exit(code=1)


def validate_published(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the report but always exit 0."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show all contracts, including passed ones."),
    ] = False,
) -> None:
    """Validate all published contracts against each other."""
    config = Config()
    store = get_store(config)
    report = validate_published_contracts(store)

    print_report(report, verbose=verbose)

    if not dry_run and report.status == ValidationStatus.FAILED:
        raise typer.Exit(code=1)


def print_report(report: ContractsValidationReport, *, verbose: bool = False) -> None:
    """Print a ContractsValidationReport to stdout in a human-readable format."""
    header = f"\nContract Validation — {report.status}\n"
    if report.status == ValidationStatus.FAILED:
        header = typer.style(header, fg=typer.colors.RED)
    typer.echo(header)
    for contract_report in report.reports:
        if not verbose and contract_report.status == ValidationStatus.PASSED:
            continue

        icon = "✓" if contract_report.status == ValidationStatus.PASSED else "✗"
        contract_line = f"  {icon}  {contract_report.topic}/{contract_report.version}"
        if contract_report.status == ValidationStatus.FAILED:
            contract_line = typer.style(contract_line, fg=typer.colors.RED)

        typer.echo(contract_line)
        for violation in contract_report.violations:
            typer.echo(f"       [{violation.severity}] {violation.rule} @ {violation.field_path}")
            typer.echo(f"       {violation.message}")

    typer.echo("")
