from __future__ import annotations

import typer

from contract_sentinel.cli.publish import publish_contracts
from contract_sentinel.cli.validate import validate_local_contracts, validate_published_contracts

app = typer.Typer(name="sentinel", help="Contract Sentinel — schema contract validation.")
app.command("validate-local-contracts")(validate_local_contracts)
app.command("validate-published-contracts")(validate_published_contracts)
app.command("publish-contracts")(publish_contracts)
