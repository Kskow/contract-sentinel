from __future__ import annotations

from typing import TYPE_CHECKING

from contract_sentinel.domain.errors import (
    MissingDependencyError,
    UnsupportedFrameworkError,
    UnsupportedStorageError,
)
from contract_sentinel.domain.framework import Framework

if TYPE_CHECKING:
    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.adapters.schema_parsers.parser import SchemaParser
    from contract_sentinel.config import Config


def get_parser(framework: Framework, repository: str) -> SchemaParser:
    """Instantiate the parser adapter for the detected schema framework."""
    match framework:
        case Framework.MARSHMALLOW:
            from contract_sentinel.adapters.schema_parsers.marshmallow import Marshmallow3Parser

            try:
                return Marshmallow3Parser(repository=repository)
            except ImportError as exc:
                raise MissingDependencyError(
                    "framework 'marshmallow' requires the marshmallow extra.\n"
                    "Install it with: pip install contract-sentinel[marshmallow]"
                ) from exc
        case _:
            raise UnsupportedFrameworkError(
                f"No adapter registered for framework '{framework}'. "
                f"Supported frameworks: {', '.join(Framework)}."
            )


def get_store(config: Config) -> ContractStore:
    """Instantiate the contract store adapter for the configured storage backend."""
    match config.store:
        case "s3":
            from contract_sentinel.adapters.contract_store import S3ContractStore

            try:
                return S3ContractStore(
                    bucket=config.s3_bucket,
                    path=config.s3_path,
                    region=config.aws_default_region,
                    aws_access_key_id=config.aws_access_key_id,
                    aws_secret_access_key=config.aws_secret_access_key,
                    endpoint_url=config.aws_endpoint_url,
                )
            except ImportError as exc:
                raise MissingDependencyError(
                    "store 's3' requires the s3 extra.\n"
                    "Install it with: pip install contract-sentinel[s3]"
                ) from exc
        case _:
            raise UnsupportedStorageError(
                f"Unrecognised store '{config.store}'. Valid options: 's3'."
            )
