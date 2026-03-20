from __future__ import annotations

import dataclasses
import json
import logging
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING

from contract_sentinel.domain.framework import detect_framework
from contract_sentinel.domain.participant import Role
from contract_sentinel.domain.rules.engine import validate_group
from contract_sentinel.domain.schema import ContractSchema

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.adapters.schema_parser import SchemaParser
    from contract_sentinel.config import Config
    from contract_sentinel.domain.framework import Framework
    from contract_sentinel.domain.rules.violation import Violation


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclasses.dataclass
class ContractReport:
    """Validation result for a single (topic, version) pair."""

    topic: str
    version: str
    status: ValidationStatus
    violations: list[Violation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "version": self.version,
            "status": self.status,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclasses.dataclass
class ContractsValidationReport:
    """Aggregated result across all validated (topic, version) pairs."""

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
    """Validate one local schema against its version-matched counterparts from the store."""
    role = Role(local_schema.role)
    opposite_role = Role.CONSUMER if role == Role.PRODUCER else Role.PRODUCER

    counterparts: list[ContractSchema] = []
    for key in store.list_files(f"{local_schema.topic}/"):
        if f"/{local_schema.version}/" in key and f"/{opposite_role.value}/" in key:
            counterparts.append(ContractSchema.from_dict(json.loads(store.get_file(key))))

    schemas = [local_schema, *counterparts]
    producers = [schema for schema in schemas if schema.role == Role.PRODUCER.value]
    consumers = [schema for schema in schemas if schema.role == Role.CONSUMER.value]

    violations = validate_group(producers, consumers)

    return ContractReport(
        topic=local_schema.topic,
        version=local_schema.version,
        status=_derive_status(violations),
        violations=violations,
    )


def validate_published_contracts(
    store: ContractStore,
    topics: list[str] | None = None,
) -> ContractsValidationReport:
    """Validate all contracts already published to the store against each other."""
    topic_filter: set[str] = set(topics) if topics is not None else set()
    by_topic_version: dict[tuple[str, str], list[ContractSchema]] = defaultdict(list)
    for key in store.list_files(""):
        if topic_filter and key.split("/")[0] not in topic_filter:
            continue
        schema = ContractSchema.from_dict(json.loads(store.get_file(key)))
        by_topic_version[(schema.topic, schema.version)].append(schema)

    for missing in topic_filter - {topic for topic, _ in by_topic_version}:
        logger.warning("Topic '%s' was requested but no published contract was found.", missing)

    contract_reports: list[ContractReport] = []
    for (topic, version), schemas in by_topic_version.items():
        contract_reports.append(_validate_published_contract(topic, version, schemas))

    return _build_report(contract_reports)


def _validate_published_contract(
    topic: str,
    version: str,
    schemas: list[ContractSchema],
) -> ContractReport:
    """Validate all published schemas for one (topic, version) pair against each other."""
    producers = [schema for schema in schemas if schema.role == Role.PRODUCER.value]
    consumers = [schema for schema in schemas if schema.role == Role.CONSUMER.value]

    violations = validate_group(producers, consumers)

    return ContractReport(
        topic=topic,
        version=version,
        status=_derive_status(violations),
        violations=violations,
    )


def _derive_status(violations: list[Violation]) -> ValidationStatus:
    """FAILED only when at least one CRITICAL violation exists; WARNING-only stays PASSED."""
    return (
        ValidationStatus.FAILED
        if any(v.severity == "CRITICAL" for v in violations)
        else ValidationStatus.PASSED
    )


def _build_report(topic_reports: list[ContractReport]) -> ContractsValidationReport:
    """Roll up a list of ContractReports into a single ContractsValidationReport."""
    global_status = (
        ValidationStatus.FAILED
        if any(report.status == ValidationStatus.FAILED for report in topic_reports)
        else ValidationStatus.PASSED
    )
    return ContractsValidationReport(status=global_status, reports=topic_reports)
