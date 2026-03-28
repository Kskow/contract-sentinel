from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_sentinel.domain.rules.rule import RuleName


@dataclasses.dataclass
class Violation:
    rule: RuleName
    severity: str
    field_path: str
    producer: dict[str, Any]
    consumer: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "field_path": self.field_path,
            "producer": self.producer,
            "consumer": self.consumer,
            "message": self.message,
        }
