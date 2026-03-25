"""Validation rules for contract comparison.

Re-exports every public name so callers can do
``from contract_sentinel.domain.rules import TypeMismatchRule`` etc.
"""

from contract_sentinel.domain.rules.direction_mismatch import DirectionMismatchRule
from contract_sentinel.domain.rules.metadata_mismatch import MetadataMismatchRule
from contract_sentinel.domain.rules.missing_field import MissingFieldRule
from contract_sentinel.domain.rules.nullability_mismatch import NullabilityMismatchRule
from contract_sentinel.domain.rules.requirement_mismatch import RequirementMismatchRule
from contract_sentinel.domain.rules.rule import Rule
from contract_sentinel.domain.rules.structure_mismatch import StructureMismatchRule
from contract_sentinel.domain.rules.type_mismatch import TypeMismatchRule
from contract_sentinel.domain.rules.undeclared_field import UndeclaredFieldRule
from contract_sentinel.domain.rules.violation import Violation

__all__ = [
    "DirectionMismatchRule",
    "MetadataMismatchRule",
    "MissingFieldRule",
    "NullabilityMismatchRule",
    "RequirementMismatchRule",
    "Rule",
    "StructureMismatchRule",
    "TypeMismatchRule",
    "UndeclaredFieldRule",
    "Violation",
]
