from __future__ import annotations

from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour


def create_violation(
    rule: str,
    severity: str = "CRITICAL",
    field_path: str = "field_name",
    producer: dict | None = None,
    consumer: dict | None = None,
    message: str = "",
) -> Violation:
    return Violation(
        rule=rule,
        severity=severity,
        field_path=field_path,
        producer=producer or {},
        consumer=consumer or {},
        message=message,
    )


def create_field(
    name: str = "field",
    type: str = "string",
    *,
    is_required: bool = True,
    is_nullable: bool = False,
    is_load_only: bool = False,
    is_dump_only: bool = False,
    fields: list[ContractField] | None = None,
    unknown: UnknownFieldBehaviour | None = None,
    metadata: dict | None = None,
) -> ContractField:
    return ContractField(
        name=name,
        type=type,
        is_required=is_required,
        is_nullable=is_nullable,
        is_load_only=is_load_only,
        is_dump_only=is_dump_only,
        fields=fields,
        unknown=unknown,
        metadata=metadata,
    )


def create_schema(
    fields: list[ContractField] | None = None,
    *,
    topic: str = "orders",
    role: str = "producer",
    repository: str = "test-repo",
    class_name: str = "OrderSchema",
    unknown: UnknownFieldBehaviour = UnknownFieldBehaviour.FORBID,
) -> ContractSchema:
    return ContractSchema(
        topic=topic,
        role=role,
        repository=repository,
        class_name=class_name,
        unknown=unknown,
        fields=fields or [],
    )
