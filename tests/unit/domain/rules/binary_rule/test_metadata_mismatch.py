from contract_sentinel.domain.rules.binary_rule import MetadataMismatchRule
from tests.unit.domain.rules.binary_rule.helpers import field


class TestMetadataMismatchRule:
    def test_returns_violation_per_mismatched_key(self) -> None:
        producer = field(metadata={"format": "iso8601", "timezone": "utc"})
        consumer = field(metadata={"format": "rfc2822"})

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
        producer = field(metadata={"format": "iso8601", "timezone": "utc"})
        consumer = field(metadata={"format": "rfc2822", "timezone": "est"})

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
        f = field(metadata={"format": "iso8601"})

        assert MetadataMismatchRule().check(f, f) == []

    def test_returns_violation_when_producer_metadata_absent_consumer_requires_it(self) -> None:
        producer = field()
        consumer = field(metadata={"format": "iso8601"})

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
        producer = field(metadata={"format": "iso8601"})
        consumer = field()

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_ignores_producer_keys_not_declared_by_consumer(self) -> None:
        producer = field(metadata={"format": "iso8601", "timezone": "utc"})
        consumer = field(metadata={"format": "iso8601"})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_skips_allowed_values_key(self) -> None:
        # allowed_values subset logic belongs to EnumValuesMismatchRule;
        # MetadataMismatchRule must not double-report it.
        producer = field(metadata={"allowed_values": ["a", "b", "c"]})
        consumer = field(metadata={"allowed_values": ["a", "b"]})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_skips_range_key(self) -> None:
        # Directional range logic belongs to RangeConstraintRule.
        producer = field(metadata={"range": {"min": 0, "min_inclusive": True}})
        consumer = field(metadata={"range": {"min": 10, "min_inclusive": True}})

        assert MetadataMismatchRule().check(producer, consumer) == []

    def test_skips_length_key(self) -> None:
        # Directional length logic belongs to LengthConstraintRule.
        producer = field(metadata={"length": {"max": 500}})
        consumer = field(metadata={"length": {"max": 100}})

        assert MetadataMismatchRule().check(producer, consumer) == []
