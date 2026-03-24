from __future__ import annotations

import dataclasses
import json
import logging
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING

from contract_sentinel.domain.framework import detect_framework
from contract_sentinel.domain.participant import Role
from contract_sentinel.domain.rules.engine import validate_contract
from contract_sentinel.domain.schema import ContractSchema

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.adapters.schema_parser import SchemaParser
    from contract_sentinel.config import Config
    from contract_sentinel.domain.framework import Framework
    from contract_sentinel.domain.rules.engine import PairViolations


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclasses.dataclass
class ContractReport:
    """Validation result for a single topic group, broken down by pair."""

    topic: str
    status: ValidationStatus
    pairs: list[PairViolations]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "status": self.status,
            "pairs": [p.to_dict() for p in self.pairs],
        }


@dataclasses.dataclass
class ContractsValidationReport:
    """Aggregated result across all validated topic pairs."""

    status: ValidationStatus
    reports: list[ContractReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reports": [r.to_dict() for r in self.reports],
        }


def validate_local_contracts(
    store: ContractStore,
    parser: Callable[[Framework, str], SchemaParser],
    loader: Callable[[], list[type]],
    config: Config,
    topics: list[str] | None = None,
) -> ContractsValidationReport:
    """Validate local schemas against their published counterparts on the store."""
    topic_filter: set[str] = set(topics) if topics is not None else set()
    found_topics: set[str] = set()
    contract_reports: list[ContractReport] = []
    for cls in loader():
        local_schema = parser(detect_framework(cls), config.name).parse(cls)
        if topic_filter and local_schema.topic not in topic_filter:
            continue
        found_topics.add(local_schema.topic)
        contract_reports.append(_validate_local_contract(store, local_schema))

    for missing in topic_filter - found_topics:
        logger.warning("Topic '%s' was requested but no local schema was found for it.", missing)

    return _build_report(contract_reports)


def _validate_local_contract(store: ContractStore, local_schema: ContractSchema) -> ContractReport:
    """Validate one local schema against its counterparts from the store."""
    role = Role(local_schema.role)
    opposite_role = Role.CONSUMER if role == Role.PRODUCER else Role.PRODUCER

    counterparts: list[ContractSchema] = []
    for key in store.list_files(f"{local_schema.topic}/"):
        if key.rsplit("/", 3)[1] == opposite_role.value:
            counterparts.append(ContractSchema.from_dict(json.loads(store.get_file(key))))

    pairs = validate_contract([local_schema, *counterparts])

    return ContractReport(
        topic=local_schema.topic,
        status=_derive_status(pairs),
        pairs=pairs,
    )


def validate_published_contracts(
    store: ContractStore,
    topics: list[str] | None = None,
) -> ContractsValidationReport:
    """Validate all contracts already published to the store against each other."""
    topic_filter: set[str] = set(topics) if topics is not None else set()
    by_topic: dict[str, list[ContractSchema]] = defaultdict(list)
    for key in store.list_files(""):
        if topic_filter and key.rsplit("/", 3)[0] not in topic_filter:
            continue
        schema = ContractSchema.from_dict(json.loads(store.get_file(key)))
        by_topic[schema.topic].append(schema)

    for missing in topic_filter - set(by_topic):
        logger.warning("Topic '%s' was requested but no published contract was found.", missing)

    contract_reports: list[ContractReport] = []
    for topic, schemas in by_topic.items():
        contract_reports.append(_validate_published_contract(topic, schemas))

    return _build_report(contract_reports)


def _validate_published_contract(
    topic: str,
    schemas: list[ContractSchema],
) -> ContractReport:
    """Validate all published schemas for one topic against each other."""
    pairs = validate_contract(schemas)

    return ContractReport(
        topic=topic,
        status=_derive_status(pairs),
        pairs=pairs,
    )


def _derive_status(pairs: list[PairViolations]) -> ValidationStatus:
    """FAILED only when at least one CRITICAL violation exists; WARNING-only stays PASSED."""
    for pair in pairs:
        for violation in pair.violations:
            if violation.severity == "CRITICAL":
                return ValidationStatus.FAILED
    return ValidationStatus.PASSED


def _build_report(topic_reports: list[ContractReport]) -> ContractsValidationReport:
    """Roll up a list of ContractReports into a single ContractsValidationReport."""
    global_status = ValidationStatus.PASSED
    for report in topic_reports:
        if report.status == ValidationStatus.FAILED:
            global_status = ValidationStatus.FAILED
            break
    return ContractsValidationReport(status=global_status, reports=topic_reports)
