from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from typing import TYPE_CHECKING

from contract_sentinel.domain.framework import detect_framework

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.adapters.schema_parser import SchemaParser
    from contract_sentinel.config import Config
    from contract_sentinel.domain.framework import Framework
    from contract_sentinel.domain.schema import ContractSchema


@dataclasses.dataclass
class FailedPublish:
    """A contract that could not be published, with the reason why."""

    key: str  # S3 key, or class name if failure occurred before parsing
    reason: str  # str(exception)

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "reason": self.reason}


@dataclasses.dataclass
class PublishReport:
    """Summary of a publish_contracts run.

    published — contracts written for the first time (key did not exist yet).
    updated   — contracts rewritten because their content hash changed.
    unchanged   — contracts whose content was identical; no write was made.
    failed    — contracts that could not be parsed; no writes were made at all
                when this list is non-empty (parse phase aborted the write phase).
    """

    published: int
    updated: int
    unchanged: int
    failed: list[FailedPublish]

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "failed": [f.to_dict() for f in self.failed],
        }


def publish_contracts(
    store: ContractStore,
    parser: Callable[[Framework, str], SchemaParser],
    loader: Callable[[], list[type]],
    config: Config,
) -> PublishReport:
    """Publish local schemas to the store in two distinct phases.

    Phase 1 — Parse: every class is parsed before anything is written.
    If any class fails (unsupported framework, missing extra, broken schema),
    all errors are collected and the function returns immediately without
    touching the store.  This prevents a partial publish where some schemas
    are at the new version while others remain stale.

    Phase 2 — Write: only reached when all classes parsed successfully.
    Each contract is compared against its stored hash; the store is written
    only when the key is new or the content has changed.  S3 errors here are
    caught per-key and collected in the report — the write phase is best-effort
    because S3 offers no multi-object atomicity.
    """
    contracts, failures = _parse_all(loader, parser, config)
    if failures:
        for f in failures:
            logger.warning("Parse failed for %s: %s", f.key, f.reason)
        return PublishReport(published=0, updated=0, unchanged=0, failed=failures)

    return _write_all(store, contracts)


# -- Phase 1 ------------------------------------------------------------------


def _parse_all(
    loader: Callable[[], list[type]],
    parser: Callable[[Framework, str], SchemaParser],
    config: Config,
) -> tuple[list[ContractSchema], list[FailedPublish]]:
    """Parse every discovered class; collect all errors rather than failing fast."""
    contracts: list[ContractSchema] = []
    failures: list[FailedPublish] = []
    for cls in loader():
        try:
            contracts.append(parser(detect_framework(cls), config.name).parse(cls))
        except Exception as exc:
            failures.append(FailedPublish(key=cls.__name__, reason=str(exc)))
    return contracts, failures


# -- Phase 2 ------------------------------------------------------------------


def _write_all(
    store: ContractStore,
    contracts: list[ContractSchema],
) -> PublishReport:
    """Write contracts to the store; catch S3 errors per-key."""
    published = 0
    updated = 0
    unchanged = 0
    failed: list[FailedPublish] = []

    for schema in contracts:
        key = schema.to_store_key()
        try:
            content = json.dumps(schema.to_dict(), sort_keys=True)
            local_hash = _sha256(content)

            if not store.file_exists(key):
                store.put_file(key, content)
                logger.info("Published new contract: %s", key)
                published += 1
            elif _sha256(store.get_file(key)) != local_hash:
                store.put_file(key, content)
                logger.info("Updated contract (hash changed): %s", key)
                updated += 1
            else:
                logger.info("No change, skipping: %s", key)
                unchanged += 1
        except Exception as exc:
            logger.warning("Failed to write %s: %s", key, exc)
            failed.append(FailedPublish(key=key, reason=str(exc)))

    return PublishReport(published=published, updated=updated, unchanged=unchanged, failed=failed)


def _sha256(content: str) -> str:
    """Return the hex-encoded SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
