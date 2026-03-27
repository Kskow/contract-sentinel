from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from contract_sentinel.config import Config
from contract_sentinel.domain.fix_suggestions import build_contracts_fix_report
from contract_sentinel.domain.loader import load_marked_classes
from contract_sentinel.domain.report import (
    FixSuggestionsReport,
    ValidationReport,
    ValidationStatus,
)
from contract_sentinel.factory import get_parser, get_store
from contract_sentinel.services.validate import (
    validate_local_contracts as service_validate_local_contracts,
)
from contract_sentinel.services.validate import (
    validate_published_contracts as service_validate_published_contracts,
)


def validate_local_contracts(
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
    how_to_fix: Annotated[
        bool,
        typer.Option("--how-to-fix", help="Show copy-paste fix suggestions for each failing pair."),
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
        return load_marked_classes(scan_path, exclude=config.exclude)

    validation_report = service_validate_local_contracts(store, get_parser, loader, config)

    print_validation_report(validation_report, verbose=verbose)

    if how_to_fix:
        fix_suggestions_report = build_contracts_fix_report(validation_report)
        print_fix_suggestions_report(fix_suggestions_report, local_name=config.name)

    if not dry_run and validation_report.status == ValidationStatus.FAILED:
        raise typer.Exit(code=1)


def validate_published_contracts(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the report but always exit 0."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show all contracts, including passed ones."),
    ] = False,
    how_to_fix: Annotated[
        bool,
        typer.Option("--how-to-fix", help="Show copy-paste fix suggestions for each failing pair."),
    ] = False,
) -> None:
    """Validate all published contracts against each other."""
    config = Config()
    store = get_store(config)
    report = service_validate_published_contracts(store)

    print_validation_report(report, verbose=verbose)

    if how_to_fix:
        fix_suggestions_report = build_contracts_fix_report(report)
        print_fix_suggestions_report(fix_suggestions_report, local_name=None)

    if not dry_run and report.status == ValidationStatus.FAILED:
        raise typer.Exit(code=1)


def print_validation_report(report: ValidationReport, *, verbose: bool = False) -> None:
    """Print a ValidationReport to stdout in a human-readable format."""
    header = f"\nContract Validation — {report.status}\n"
    if report.status == ValidationStatus.FAILED:
        header = typer.style(header, fg=typer.colors.RED)
    typer.echo(header)
    for contract_report in report.contracts:
        if not verbose and contract_report.status == ValidationStatus.PASSED:
            continue

        icon = "✓" if contract_report.status == ValidationStatus.PASSED else "✗"
        contract_line = f"  {icon}  {contract_report.topic}"
        if contract_report.status == ValidationStatus.FAILED:
            contract_line = typer.style(contract_line, fg=typer.colors.RED)

        typer.echo(contract_line)
        for pair in contract_report.pairs:
            if not verbose and not pair.violations:
                continue
            producer = pair.producer_id or "(none)"
            consumer = pair.consumer_id or "(none)"
            typer.echo(f"       {producer} vs {consumer}")
            for violation in pair.violations:
                typer.echo(
                    f"         [{violation.severity}] {violation.rule} @ {violation.field_path}"
                )
                typer.echo(f"         {violation.message}")

    typer.echo("")


def print_fix_suggestions_report(
    fix_report: FixSuggestionsReport, *, local_name: str | None
) -> None:
    """Print a FixSuggestionsReport to stdout. No-op when there are no suggestions."""
    if not fix_report.has_suggestions:
        return

    typer.echo("\nFix Suggestions\n")

    for topic in fix_report.suggestions:
        typer.echo(f"  {topic.topic}")
        for pair in topic.pairs:
            typer.echo(f"\n       {pair.producer_id} vs {pair.consumer_id}\n")

            if local_name is not None and pair.producer_id.startswith(local_name + "/"):
                producer_label = "Fix on your side (Producer) — copy & paste to your agent:"
                consumer_label = "Fix on their side (Consumer) — copy & paste to your agent:"
            elif local_name is not None and pair.consumer_id.startswith(local_name + "/"):
                producer_label = "Fix on their side (Producer) — copy & paste to your agent:"
                consumer_label = "Fix on your side (Consumer) — copy & paste to your agent:"
            else:
                producer_label = "Fix on Producer side — copy & paste to your agent:"
                consumer_label = "Fix on Consumer side — copy & paste to your agent:"

            _print_fix_block(producer_label, pair.producer_suggestions)
            _print_fix_block(consumer_label, pair.consumer_suggestions)

    typer.echo("")


def _print_fix_block(label: str, block: str) -> None:
    typer.echo(f"         {label}\n")
    for line in block.splitlines():
        typer.echo(f"           {line}" if line else "")
    typer.echo("")
