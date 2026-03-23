from __future__ import annotations

import typer

from contract_sentinel.cli.validate import validate_local, validate_published

app = typer.Typer(name="sentinel", help="Contract Sentinel — schema contract validation.")
app.command("validate-local")(validate_local)
app.command("validate-published")(validate_published)
