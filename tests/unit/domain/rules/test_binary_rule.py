from contract_sentinel.domain.rules.binary_rule import (
    EnumValuesMismatchRule,
    MetadataMismatchRule,
    NullabilityMismatchRule,
    RequirementMismatchRule,
    TypeMismatchRule,
)
from contract_sentinel.domain.schema import ContractField


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

    def test_returns_violation_when_formats_differ_same_type(self) -> None:
        producer = ContractField(
            name="ip_addr", type="string", format="ipv4", is_required=True, is_nullable=False
        )
        consumer = ContractField(
            name="ip_addr", type="string", format="ipv6", is_required=True, is_nullable=False
        )

        violations = TypeMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "ip_addr",
            "producer": {"type": "string", "format": "ipv4"},
            "consumer": {"type": "string", "format": "ipv6"},
            "message": (
                "Field 'ip_addr' is a 'string (ipv4)' in Producer"
                " but Consumer expects a 'string (ipv6)'."
            ),
        }

    def test_returns_empty_when_type_and_format_both_match(self) -> None:
        field = ContractField(
            name="created_at",
            type="string",
            format="date-time",
            is_required=True,
            is_nullable=False,
        )

        assert TypeMismatchRule().check(field, field) == []

    def test_violation_payload_omits_format_when_none(self) -> None:
        producer = ContractField(name="f", type="string", is_required=True, is_nullable=False)
        consumer = ContractField(name="f", type="integer", is_required=True, is_nullable=False)

        violation = TypeMismatchRule().check(producer, consumer)[0]

        assert "format" not in violation.to_dict()["producer"]
        assert "format" not in violation.to_dict()["consumer"]


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


class TestEnumValuesMismatchRule:
    def _field(self, values: list[str] | None) -> ContractField:
        return ContractField(
            name="status",
            type="string",
            format="enum",
            is_required=True,
            is_nullable=False,
            values=values,
        )

    def test_returns_violation_when_producer_emits_value_consumer_cannot_accept(self) -> None:
        producer = self._field(["active", "inactive", "deleted"])
        consumer = self._field(["active", "inactive"])

        violations = EnumValuesMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "ENUM_VALUES_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "status",
            "producer": {"values": ["active", "inactive", "deleted"]},
            "consumer": {"values": ["active", "inactive"]},
            "message": (
                "Field 'status' producer can emit ['deleted']"
                " but Consumer does not accept those values."
            ),
        }

    def test_returns_empty_when_producer_values_subset_of_consumer(self) -> None:
        producer = self._field(["active", "inactive"])
        consumer = self._field(["active", "inactive", "pending"])

        assert EnumValuesMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_values_are_equal(self) -> None:
        field = self._field(["active", "inactive"])

        assert EnumValuesMismatchRule().check(field, field) == []

    def test_returns_empty_when_producer_values_is_none(self) -> None:
        producer = self._field(None)
        consumer = self._field(["active"])

        assert EnumValuesMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_consumer_values_is_none(self) -> None:
        producer = self._field(["active"])
        consumer = self._field(None)

        assert EnumValuesMismatchRule().check(producer, consumer) == []
