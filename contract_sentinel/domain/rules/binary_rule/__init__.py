"""Binary validation rules — both fields present.

Re-exports every public name so the original import path
``from contract_sentinel.domain.rules.binary_rule import X`` continues to work.
"""

from contract_sentinel.domain.rules.binary_rule.base import BinaryRule
from contract_sentinel.domain.rules.binary_rule.direction_mismatch import DirectionMismatchRule
from contract_sentinel.domain.rules.binary_rule.enum_values_mismatch import EnumValuesMismatchRule
from contract_sentinel.domain.rules.binary_rule.length_constraint import LengthConstraintRule
from contract_sentinel.domain.rules.binary_rule.metadata_mismatch import MetadataMismatchRule
from contract_sentinel.domain.rules.binary_rule.nested_field import NestedFieldRule
from contract_sentinel.domain.rules.binary_rule.nullability_mismatch import NullabilityMismatchRule
from contract_sentinel.domain.rules.binary_rule.range_constraint import RangeConstraintRule
from contract_sentinel.domain.rules.binary_rule.requirement_mismatch import RequirementMismatchRule
from contract_sentinel.domain.rules.binary_rule.type_mismatch import TypeMismatchRule
from contract_sentinel.domain.rules.binary_rule.unknown_field_behaviour import (
    UnknownFieldBehaviourRule,
)

__all__ = [
    "BinaryRule",
    "DirectionMismatchRule",
    "EnumValuesMismatchRule",
    "LengthConstraintRule",
    "MetadataMismatchRule",
    "NestedFieldRule",
    "NullabilityMismatchRule",
    "RangeConstraintRule",
    "RequirementMismatchRule",
    "TypeMismatchRule",
    "UnknownFieldBehaviourRule",
]
