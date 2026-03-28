from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from contract_sentinel.domain.framework import detect_framework
from contract_sentinel.domain.participant import Role
from contract_sentinel.domain.report import ValidationReport
from contract_sentinel.domain.rules.engine import validate_contract
from contract_sentinel.domain.schema import ContractSchema

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from contract_sentinel.adapters.contract_store import ContractStore
    from contract_sentinel.adapters.schema_parsers.parser import SchemaParser
    from contract_sentinel.config import Config
    from contract_sentinel.domain.framework import Framework
    from contract_sentinel.domain.report import ContractReport


def validate_local_contracts(
    store: ContractStore,
    parser: Callable[[Framework, str], SchemaParser],
    loader: Callable[[], list[type]],
    config: Config,
    topics: list[str] | None = None,
) -> ValidationReport:
    """Validate local schemas against their published counterparts on the store."""
    topic_filter: set[str] = set(topics) if topics is not None else set()
    found_topics: set[str] = set()
    contracts: list[ContractReport] = []

    for cls in loader():
        local_schema = parser(detect_framework(cls), config.name).parse(cls)
        if topic_filter and local_schema.topic not in topic_filter:
            continue
        found_topics.add(local_schema.topic)
        contracts.append(_validate_local_contract(store, local_schema))

    for missing in topic_filter - found_topics:
        logger.warning("Topic '%s' was requested but no local schema was found for it.", missing)

    return ValidationReport(contracts=contracts)


def _validate_local_contract(store: ContractStore, local_schema: ContractSchema) -> ContractReport:
    """Validate one local schema against its counterparts from the store."""
    role = Role(local_schema.role)
    opposite_role = Role.CONSUMER if role == Role.PRODUCER else Role.PRODUCER

    counterparts: list[ContractSchema] = []
    for key in store.list_files(f"{local_schema.topic}/"):
        if key.rsplit("/", 3)[1] == opposite_role.value:
            counterparts.append(ContractSchema.from_dict(json.loads(store.get_file(key))))

    return validate_contract([local_schema, *counterparts])


def validate_published_contracts(
    store: ContractStore,
    topics: list[str] | None = None,
) -> ValidationReport:
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

    return ValidationReport(contracts=[validate_contract(schemas) for schemas in by_topic.values()])
