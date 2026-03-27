from contract_sentinel.domain.rules.structure_mismatch import StructureMismatchRule
from tests.unit.helpers import create_field


class TestStructureMismatchRule:
    def test_returns_violation_when_producer_is_open_map_and_consumer_has_fixed_schema_object(
        self,
    ) -> None:
        producer = create_field(name="payload", type="object", fields=None)
        consumer = create_field(name="payload", type="object", fields=[create_field()])

        violations = StructureMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "STRUCTURE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "payload",
            "producer": {"structure": "open_map"},
            "consumer": {"structure": "fixed_schema"},
            "message": (
                "Field 'payload' is an open map in Producer"
                " but Consumer expects a fixed-schema object."
            ),
        }

    def test_returns_violation_when_producer_is_open_map_and_consumer_has_fixed_schema_array(
        self,
    ) -> None:
        producer = create_field(name="items", type="array", fields=None)
        consumer = create_field(name="items", type="array", fields=[create_field()])

        violations = StructureMismatchRule().check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "STRUCTURE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "items",
            "producer": {"structure": "open_map"},
            "consumer": {"structure": "fixed_schema"},
            "message": (
                "Field 'items' is an open map in Producer"
                " but Consumer expects a fixed-schema object."
            ),
        }

    def test_returns_empty_when_producer_has_fixed_schema_and_consumer_is_open_map(self) -> None:
        producer = create_field(name="payload", type="object", fields=[create_field()])
        consumer = create_field(name="payload", type="object", fields=None)

        assert StructureMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_both_have_fixed_schema(self) -> None:
        producer = create_field(name="payload", type="object", fields=[create_field()])
        consumer = create_field(name="payload", type="object", fields=[create_field()])

        assert StructureMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_neither_has_fields(self) -> None:
        producer = create_field(name="payload", type="object", fields=None)
        consumer = create_field(name="payload", type="object", fields=None)

        assert StructureMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_types_differ(self) -> None:
        producer = create_field(name="payload", type="object", fields=None)
        consumer = create_field(name="payload", type="array", fields=[create_field()])

        assert StructureMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_type_is_non_structural(self) -> None:
        producer = create_field(name="payload", type="string", fields=None)
        consumer = create_field(name="payload", type="string", fields=[create_field()])

        assert StructureMismatchRule().check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        consumer = create_field(name="payload", type="object", fields=[create_field()])

        assert StructureMismatchRule().check(None, consumer) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        producer = create_field(name="payload", type="object", fields=None)

        assert StructureMismatchRule().check(producer, None) == []
