from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from enum import StrEnum
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


class OperationKind(StrEnum):
    PUBLISH = "publish"
    PRUNE = "prune"


@dataclasses.dataclass
class FailedOperation:
    """A publish or prune operation that failed, with the key and reason."""

    operation: OperationKind
    key: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"operation": self.operation, "key": self.key, "reason": self.reason}


@dataclasses.dataclass
class PublishReport:
    """Summary of a publish_contracts run.

    published — keys of contracts written for the first time (key did not exist yet).
    updated   — keys of contracts rewritten because their content hash changed.
    unchanged — keys of contracts whose content was identical; no write was made.
    pruned    — keys deleted from the store because they belong to this repository
                but were not found in the current local scan (renamed / removed class).
    failed    — operations (publish or prune) that raised an exception.  Parse
                failures abort the write phase entirely; write/prune failures are
                collected per-key and the run continues.
    """

    published: list[str]
    updated: list[str]
    unchanged: list[str]
    pruned: list[str]
    failed: list[FailedOperation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "pruned": self.pruned,
            "failed": [f.to_dict() for f in self.failed],
        }


def publish_contracts(
    store: ContractStore,
    parser: Callable[[Framework, str], SchemaParser],
    loader: Callable[[], list[type]],
    config: Config,
) -> PublishReport:
    """Publish local schemas to the store in three distinct phases.

    Phase 1 — Parse: every class is parsed before anything is written.
    If any class fails (unsupported framework, missing extra, broken schema),
    all errors are collected and the function returns immediately without
    touching the store.  This prevents a partial publish.

    Phase 2 — Write: only reached when all classes parsed successfully.
    Each contract is compared against its stored hash; the store is written
    only when the key is new or the content has changed.  S3 errors here are
    caught per-key and collected in the report — the write phase is best-effort
    because S3 offers no multi-object atomicity.

    Phase 3 — Prune: only reached when both Phase 1 and Phase 2 had zero
    failures, meaning the local scan is trusted as complete.  Any store key
    that (a) belongs to this repository and (b) was not produced by the
    current scan is deleted — it represents a class that was renamed or
    removed.  Pruning is scoped strictly to ``{repository}_*.json`` filenames
    so it never touches contracts owned by other repositories.
    """
    contracts, failures = _parse_all(loader, parser, config)
    if failures:
        for f in failures:
            logger.warning("Parse failed for %s: %s", f.key, f.reason)
        return PublishReport(published=[], updated=[], unchanged=[], pruned=[], failed=failures)

    report = _write_all(store, contracts)

    if not report.failed:
        pruned, prune_failures = _prune_stale(store, report, config.name)
        report.pruned = pruned
        report.failed.extend(prune_failures)

    return report


def _parse_all(
    loader: Callable[[], list[type]],
    parser: Callable[[Framework, str], SchemaParser],
    config: Config,
) -> tuple[list[ContractSchema], list[FailedOperation]]:
    """Parse every discovered class; collect all errors rather than failing fast."""
    contracts: list[ContractSchema] = []
    failures: list[FailedOperation] = []
    for cls in loader():
        try:
            contracts.append(parser(detect_framework(cls), config.name).parse(cls))
        except Exception as exc:
            failures.append(
                FailedOperation(operation=OperationKind.PUBLISH, key=cls.__name__, reason=str(exc))
            )
    return contracts, failures


def _write_all(
    store: ContractStore,
    contracts: list[ContractSchema],
) -> PublishReport:
    """Write contracts to the store; catch S3 errors per-key."""
    published: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    failed: list[FailedOperation] = []

    for schema in contracts:
        key = schema.to_store_key()
        try:
            content = json.dumps(schema.to_dict(), sort_keys=True)
            local_hash = _sha256(content)

            if not store.file_exists(key):
                store.put_file(key, content)
                logger.info("Published new contract: %s", key)
                published.append(key)
            elif _sha256(store.get_file(key)) != local_hash:
                store.put_file(key, content)
                logger.info("Updated contract (hash changed): %s", key)
                updated.append(key)
            else:
                logger.info("No change, skipping: %s", key)
                unchanged.append(key)
        except Exception as exc:
            logger.warning("Failed to write %s: %s", key, exc)
            failed.append(
                FailedOperation(operation=OperationKind.PUBLISH, key=key, reason=str(exc))
            )

    return PublishReport(
        published=published, updated=updated, unchanged=unchanged, pruned=[], failed=failed
    )


def _prune_stale(
    store: ContractStore,
    report: PublishReport,
    repository: str,
) -> tuple[list[str], list[FailedOperation]]:
    """Delete store keys that belong to this repository but are absent from the current scan."""
    current_keys: set[str] = set(report.published + report.updated + report.unchanged)

    pruned: list[str] = []
    failures: list[FailedOperation] = []
    for key in store.list_files(""):
        parts = key.rsplit("/", 3)
        if len(parts) == 4 and parts[2] == repository and key not in current_keys:
            try:
                store.delete_file(key)
                logger.info("Pruned stale contract: %s", key)
                pruned.append(key)
            except Exception as exc:
                logger.warning("Failed to prune %s: %s", key, exc)
                failures.append(
                    FailedOperation(operation=OperationKind.PRUNE, key=key, reason=str(exc))
                )

    return pruned, failures


def _sha256(content: str) -> str:
    """Return the hex-encoded SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
