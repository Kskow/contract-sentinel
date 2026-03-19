from contract_sentinel.domain.rules import (
    MissingFieldRule,
    NestedFieldRule,
    NullabilityMismatchRule,
    RequirementMismatchRule,
    TypeMismatchRule,
)
from contract_sentinel.domain.schema import UnknownFieldBehaviour
from tests.unit.domain.rules.helpers import field


def _make_rules() -> tuple[list, NestedFieldRule]:
    rules: list = [
        TypeMismatchRule(),
        NullabilityMismatchRule(),
        RequirementMismatchRule(),
        MissingFieldRule(),
    ]
    nested = NestedFieldRule(rules)
    rules.append(nested)
    return rules, nested


class TestNestedFieldRule:
    def test_returns_empty_when_neither_field_has_sub_fields(self) -> None:
        _, nested = _make_rules()
        producer = field(type="string")
        consumer = field(type="string")

        assert nested.check(producer, consumer) == []

    def test_returns_empty_when_only_producer_has_sub_fields(self) -> None:
        # Consumer has no sub-fields — nothing to compare against.
        _, nested = _make_rules()
        producer = field(
            type="object",
            fields=[field(name="street", type="string")],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = field(type="object")

        assert nested.check(producer, consumer) == []

    def test_returns_empty_when_sub_fields_match(self) -> None:
        _, nested = _make_rules()
        sub = field(name="street", type="string")
        producer = field(type="object", fields=[sub], unknown=UnknownFieldBehaviour.FORBID)
        consumer = field(type="object", fields=[sub], unknown=UnknownFieldBehaviour.FORBID)

        assert nested.check(producer, consumer) == []

    def test_returns_empty_when_producer_is_none(self) -> None:
        _, nested = _make_rules()
        consumer = field(type="object", fields=[field(name="id", type="integer")])

        assert nested.check(None, consumer) == []

    def test_returns_empty_when_consumer_is_none(self) -> None:
        _, nested = _make_rules()
        producer = field(type="object", fields=[field(name="id", type="integer")])

        assert nested.check(producer, None) == []

    def test_returns_violation_with_prefixed_path_for_type_mismatch(self) -> None:
        _, nested = _make_rules()
        p_street = field(name="street", type="integer")
        c_street = field(name="street", type="string")
        producer = field(
            name="address", type="object", fields=[p_street], unknown=UnknownFieldBehaviour.FORBID
        )
        consumer = field(
            name="address", type="object", fields=[c_street], unknown=UnknownFieldBehaviour.FORBID
        )

        violations = nested.check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "address.street",
            "producer": {"type": "integer"},
            "consumer": {"type": "string"},
            "message": (
                "Field 'address.street' is a 'integer' in Producer but Consumer expects a 'string'."
            ),
        }

    def test_returns_violations_for_multiple_mismatched_sub_fields(self) -> None:
        _, nested = _make_rules()
        producer = field(
            name="payload",
            type="object",
            fields=[
                field(name="amount", type="string"),
                field(name="currency", type="integer"),
            ],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = field(
            name="payload",
            type="object",
            fields=[
                field(name="amount", type="integer"),
                field(name="currency", type="string"),
            ],
            unknown=UnknownFieldBehaviour.FORBID,
        )

        violations = nested.check(producer, consumer)

        assert len(violations) == 2
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "payload.amount",
            "producer": {"type": "string"},
            "consumer": {"type": "integer"},
            "message": (
                "Field 'payload.amount' is a 'string' in Producer but Consumer expects a 'integer'."
            ),
        }
        assert violations[1].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "payload.currency",
            "producer": {"type": "integer"},
            "consumer": {"type": "string"},
            "message": (
                "Field 'payload.currency' is a 'integer' in Producer"
                " but Consumer expects a 'string'."
            ),
        }

    def test_fires_missing_field_for_consumer_sub_field_absent_from_producer(self) -> None:
        # MissingFieldRule runs in the unified loop when p_field is None.
        _, nested = _make_rules()
        producer = field(
            name="data",
            type="object",
            fields=[field(name="id", type="integer")],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = field(
            name="data",
            type="object",
            fields=[
                field(name="id", type="integer"),
                field(name="name", type="string", is_required=True),
            ],
            unknown=UnknownFieldBehaviour.FORBID,
        )

        violations = nested.check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "MISSING_FIELD",
            "severity": "CRITICAL",
            "field_path": "data.name",
            "producer": {"exists": False},
            "consumer": {"is_required": True},
            "message": "Field 'data.name' is missing in Producer but required in Consumer.",
        }

    def test_optional_consumer_sub_field_absent_from_producer_passes(self) -> None:
        # Consumer-only field that is optional (is_required=False) — no violation.
        _, nested = _make_rules()
        producer = field(
            name="data",
            type="object",
            fields=[field(name="id", type="integer")],
            unknown=UnknownFieldBehaviour.IGNORE,
        )
        consumer = field(
            name="data",
            type="object",
            fields=[
                field(name="id", type="integer"),
                field(name="tag", type="string", is_required=False),
            ],
            unknown=UnknownFieldBehaviour.IGNORE,
        )

        assert nested.check(producer, consumer) == []

    def test_recurses_into_deeply_nested_fields(self) -> None:
        # address.location.lat type mismatch should surface with full dot path.
        _, nested = _make_rules()
        lat_p = field(name="lat", type="string")
        lat_c = field(name="lat", type="number")
        location_p = field(
            name="location", type="object", fields=[lat_p], unknown=UnknownFieldBehaviour.FORBID
        )
        location_c = field(
            name="location", type="object", fields=[lat_c], unknown=UnknownFieldBehaviour.FORBID
        )
        producer = field(
            name="address",
            type="object",
            fields=[location_p],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = field(
            name="address",
            type="object",
            fields=[location_c],
            unknown=UnknownFieldBehaviour.FORBID,
        )

        violations = nested.check(producer, consumer)

        assert len(violations) == 1
        assert violations[0].to_dict() == {
            "rule": "TYPE_MISMATCH",
            "severity": "CRITICAL",
            "field_path": "address.location.lat",
            "producer": {"type": "string"},
            "consumer": {"type": "number"},
            "message": (
                "Field 'address.location.lat' is a 'string' in Producer"
                " but Consumer expects a 'number'."
            ),
        }

    def test_skips_recursion_when_top_level_types_differ(self) -> None:
        # TypeMismatchRule handles this; NestedFieldRule should not produce noise on top.
        _, nested = _make_rules()
        producer = field(
            name="data",
            type="object",
            fields=[field(name="id", type="integer")],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = field(name="data", type="array")  # type differs, no sub-fields

        assert nested.check(producer, consumer) == []
