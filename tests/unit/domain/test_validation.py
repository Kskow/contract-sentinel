from contract_sentinel.domain.contract import ContractField, UnknownFieldBehaviour
from contract_sentinel.domain.validation import (
    MetadataMismatchRule,
    MissingFieldRule,
    NullabilityMismatchRule,
    RequirementMismatchRule,
    TypeMismatchRule,
    UndeclaredFieldRule,
    Violation,
)


class TestViolation:
    def test_to_dict_serialises_all_fields(self) -> None:
        violation = Violation(
            rule="TYPE_MISMATCH",
            severity="CRITICAL",
            field_path="order_id",
            producer={"type": "string"},
            consumer={"type": "integer"},
            message=(
                "Field 'order_id' is a 'string' in Producer but Consumer expects a 'integer'."
            ),
        )

        assert violation.to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "order_id",
            "producer": {"type": "string"},
            "consumer": {"type": "integer"},
            "message": (
                "Field 'order_id' is a 'string' in Producer but Consumer expects a 'integer'."
            ),
        }


class TestTypeMismatchRule:
    def test_returns_violation_when_types_differ(self) -> None:
        producer = ContractField(name="field", type="string", is_required=True, is_nullable=False)
        consumer = ContractField(name="field", type="integer", is_required=True, is_nullable=False)

        violations = TypeMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"type": "string"},
            "consumer": {"type": "integer"},
            "message": "Field 'field' is a 'string' in Producer but Consumer expects a 'integer'.",
        }

    def test_returns_empty_when_types_match(self) -> None:
        field = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        assert TypeMismatchRule().check(field, field) == []


class TestRequirementMismatchRule:
    def test_returns_violation_when_producer_optional_consumer_required_no_default(self) -> None:
        producer = ContractField(name="field", type="string", is_required=False, is_nullable=False)
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        violations = RequirementMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "REQUIREMENT_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"is_required": False},
            "consumer": {"is_required": True},
            "message": "Field 'field' is optional in Producer but required in Consumer.",
        }

    def test_returns_empty_when_both_required(self) -> None:
        field = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        assert RequirementMismatchRule().check(field, field) == []

    def test_returns_empty_when_consumer_has_default(self) -> None:
        producer = ContractField(name="field", type="string", is_required=False, is_nullable=False)
        consumer = ContractField(
            name="field", type="string", is_required=True, is_nullable=False, default="fallback"
        )

        assert RequirementMismatchRule().check(producer, consumer) == []


class TestNullabilityMismatchRule:
    def test_returns_violation_when_producer_allows_none_consumer_does_not(self) -> None:
        producer = ContractField(name="field", type="string", is_required=True, is_nullable=True)
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        violations = NullabilityMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "NULLABILITY_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"is_nullable": True},
            "consumer": {"is_nullable": False},
            "message": "Field 'field' allows null in Producer but Consumer expects a value.",
        }

    def test_returns_empty_when_both_allow_none(self) -> None:
        field = ContractField(name="field", type="string", is_required=True, is_nullable=True)

        assert NullabilityMismatchRule().check(field, field) == []

    def test_returns_empty_when_neither_allows_none(self) -> None:
        field = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        assert NullabilityMismatchRule().check(field, field) == []


class TestMissingFieldRule:
    def test_returns_violation_when_producer_field_absent_and_consumer_required(self) -> None:
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        violations = MissingFieldRule().check(consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "MISSING_FIELD",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"exists": False},
            "consumer": {"is_required": True},
            "message": "Field 'field' is missing in Producer but required in Consumer.",
        }

    def test_returns_empty_when_consumer_has_default(self) -> None:
        consumer = ContractField(
            name="field", type="string", is_required=True, is_nullable=False, default="fallback"
        )

        assert MissingFieldRule().check(consumer) == []


class TestUndeclaredFieldRule:
    def test_returns_violation_when_consumer_forbids_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        violations = UndeclaredFieldRule(UnknownFieldBehaviour.FORBID).check(producer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "UNDECLARED_FIELD",
            "severity": "CRITICAL",
            "field_path": "extra",
            "producer": {"exists": True},
            "consumer": {"exists": False, "unknown": "forbid"},
            "message": (
                "Field 'extra' is sent by Producer but is not declared"
                " in Consumer (unknown=forbid)."
            ),
        }

    def test_returns_empty_when_consumer_ignores_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        assert UndeclaredFieldRule(UnknownFieldBehaviour.IGNORE).check(producer) == []

    def test_returns_empty_when_consumer_allows_unknowns(self) -> None:
        producer = ContractField(name="extra", type="string", is_required=True, is_nullable=False)

        assert UndeclaredFieldRule(UnknownFieldBehaviour.ALLOW).check(producer) == []


class TestMetadataMismatchRule:
    def test_returns_violation_per_mismatched_key(self) -> None:
        producer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601", "timezone": "utc"},
        )
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "rfc2822"},
        )

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"format": "iso8601"},
            "consumer": {"format": "rfc2822"},
            "message": (
                "Field 'field' has mismatched metadata 'format':"
                " Producer has 'iso8601', Consumer expects 'rfc2822'."
            ),
        }

    def test_returns_multiple_violations_for_multiple_mismatches(self) -> None:
        producer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601", "timezone": "utc"},
        )
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "rfc2822", "timezone": "est"},
        )

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "METADATA_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"format": "iso8601"},
            "consumer": {"format": "rfc2822"},
            "message": (
                "Field 'field' has mismatched metadata 'format':"
                " Producer has 'iso8601', Consumer expects 'rfc2822'."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "METADATA_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"timezone": "utc"},
            "consumer": {"timezone": "est"},
            "message": (
                "Field 'field' has mismatched metadata 'timezone':"
                " Producer has 'utc', Consumer expects 'est'."
            ),
        }

    def test_returns_empty_when_metadata_matches(self) -> None:
        field = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601"},
        )

        assert MetadataMismatchRule().check(field, field) == []

    def test_returns_violation_when_producer_metadata_absent_consumer_requires_it(self) -> None:
        producer = ContractField(name="field", type="string", is_required=True, is_nullable=False)
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601"},
        )

        violations = MetadataMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "METADATA_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "field",
            "producer": {"format": None},
            "consumer": {"format": "iso8601"},
            "message": (
                "Field 'field' has mismatched metadata 'format':"
                " Producer has 'None', Consumer expects 'iso8601'."
            ),
        }

    def test_returns_empty_when_consumer_metadata_is_none(self) -> None:
        producer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601"},
        )
        consumer = ContractField(name="field", type="string", is_required=True, is_nullable=False)

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_ignores_producer_keys_not_declared_by_consumer(self) -> None:
        producer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601", "timezone": "utc"},
        )
        consumer = ContractField(
            name="field",
            type="string",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601"},
        )

        assert MetadataMismatchRule().check(producer, consumer) == []
