from __future__ import annotations

from unittest.mock import MagicMock, patch

from contract_sentinel.domain.rules.engine import PairViolations, validate_contract
from contract_sentinel.domain.rules.rule import RuleName
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour
from tests.unit.helpers import create_field, create_schema


def _violation(field_path: str = "field") -> Violation:
    return Violation(
        rule=RuleName.TYPE_MISMATCH,
        severity="CRITICAL",
        field_path=field_path,
        producer={},
        consumer={},
        message=f"Field '{field_path}' test violation.",
    )


def _producer(
    fields_list: list[ContractField],
    unknown: UnknownFieldBehaviour = UnknownFieldBehaviour.FORBID,
    repository: str = "producer-repo",
) -> ContractSchema:
    return create_schema(fields_list, role="producer", unknown=unknown, repository=repository)


def _consumer(
    fields_list: list[ContractField],
    unknown: UnknownFieldBehaviour = UnknownFieldBehaviour.FORBID,
    repository: str = "consumer-repo",
) -> ContractSchema:
    return create_schema(fields_list, role="consumer", unknown=unknown, repository=repository)


def _mock_rule(return_value: list[Violation] | None = None) -> MagicMock:
    rule = MagicMock()
    rule.check.return_value = return_value if return_value is not None else []
    return rule


class TestPairViolationsToDict:
    def test_serialises_producer_consumer_ids_and_violations(self) -> None:
        violation = _violation("id")
        pair = PairViolations(
            producer_id="orders-service/OrderSchema",
            consumer_id="checkout-service/OrderConsumerSchema",
            violations=[violation],
        )

        assert pair.to_dict() == {
            "producer_id": "orders-service/OrderSchema",
            "consumer_id": "checkout-service/OrderConsumerSchema",
            "violations": [violation.to_dict()],
        }

    def test_serialises_empty_violations(self) -> None:
        pair = PairViolations(
            producer_id="orders-service/OrderSchema",
            consumer_id="checkout-service/OrderConsumerSchema",
            violations=[],
        )

        assert pair.to_dict() == {
            "producer_id": "orders-service/OrderSchema",
            "consumer_id": "checkout-service/OrderConsumerSchema",
            "violations": [],
        }

    def test_serialises_none_ids_for_lonely_schema(self) -> None:
        pair = PairViolations(
            producer_id="orders-service/OrderSchema",
            consumer_id=None,
            violations=[_violation()],
        )

        assert pair.to_dict() == {
            "producer_id": "orders-service/OrderSchema",
            "consumer_id": None,
            "violations": [_violation().to_dict()],
        }


class TestValidateContract:
    def test_splits_mixed_list_by_role_before_validating(self) -> None:
        result = validate_contract(
            [
                _producer([create_field(name="id", type="string")]),
                _consumer([create_field(name="id", type="string")]),
            ]
        )

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [],
                }
            ],
        }

    def test_returns_counterpart_violation_when_producer_has_no_consumer(self) -> None:
        rule = _mock_rule()

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_contract([_producer([create_field(name="id", type="string")])])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": None,
                    "violations": [
                        {
                            "rule": "COUNTERPART_MISMATCH",
                            "severity": "WARNING",
                            "field_path": "",
                            "producer": {},
                            "consumer": {},
                            "message": "Topic 'orders' has 1 producer(s) but no matching consumer.",
                        }
                    ],
                }
            ],
        }
        assert rule.check.call_count == 0

    def test_returns_counterpart_violation_when_consumer_has_no_producer(self) -> None:
        rule = _mock_rule()

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_contract([_consumer([create_field(name="id", type="string")])])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": None,
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [
                        {
                            "rule": "COUNTERPART_MISMATCH",
                            "severity": "WARNING",
                            "field_path": "",
                            "producer": {},
                            "consumer": {},
                            "message": "Topic 'orders' has 1 consumer(s) but no matching producer.",
                        }
                    ],
                }
            ],
        }
        assert rule.check.call_count == 0

    def test_runs_pairwise_validation_for_every_producer_consumer_combination(self) -> None:
        p1 = _producer([create_field(name="id", type="string")], repository="p1-repo")
        c1 = _consumer([create_field(name="id", type="string")], repository="c1-repo")
        c2 = _consumer([create_field(name="id", type="string")], repository="c2-repo")

        rule = _mock_rule()
        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_contract([p1, c1, c2])

        assert rule.check.call_count == 2

    def test_every_rule_is_called_for_a_matched_field(self) -> None:
        rule_a = _mock_rule()
        rule_b = _mock_rule()
        p_field = create_field(name="id", type="string")
        c_field = create_field(name="id", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule_a, rule_b]):
            validate_contract([_producer([p_field]), _consumer([c_field])])

        rule_a.check.assert_called_once_with(p_field, c_field)
        rule_b.check.assert_called_once_with(p_field, c_field)

    def test_every_rule_is_called_for_each_field_independently(self) -> None:
        rule = _mock_rule()
        p_id = create_field(name="id", type="string")
        p_name = create_field(name="name", type="string")
        c_id = create_field(name="id", type="string")
        c_name = create_field(name="name", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_contract([_producer([p_id, p_name]), _consumer([c_id, c_name])])

        assert rule.check.call_count == 2
        rule.check.assert_any_call(p_id, c_id)
        rule.check.assert_any_call(p_name, c_name)

    def test_consumer_only_field_passes_none_as_producer(self) -> None:
        rule = _mock_rule()
        c_field = create_field(name="extra", type="string", is_required=False)

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_contract([_producer([]), _consumer([c_field])])

        rule.check.assert_called_once_with(None, c_field)

    def test_producer_only_field_passes_none_as_consumer(self) -> None:
        rule = _mock_rule()
        p_field = create_field(name="extra", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_contract(
                [_producer([p_field]), _consumer([], unknown=UnknownFieldBehaviour.IGNORE)]
            )

        rule.check.assert_called_once_with(p_field, None)

    def test_violations_from_rules_are_collected_and_returned(self) -> None:
        violation = _violation("id")
        rule = _mock_rule(return_value=[violation])

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_contract(
                [
                    _producer([create_field(name="id", type="string")]),
                    _consumer([create_field(name="id", type="string")]),
                ]
            )

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [violation.to_dict()],
                }
            ],
        }

    def test_violations_from_multiple_fields_are_aggregated(self) -> None:
        v1 = _violation("id")
        v2 = _violation("name")
        rule = _mock_rule()
        rule.check.side_effect = [[v1], [v2]]

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_contract(
                [
                    _producer([create_field(name="id", type="string"), create_field(name="name")]),
                    _consumer([create_field(name="id", type="string"), create_field(name="name")]),
                ]
            )

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [v1.to_dict(), v2.to_dict()],
                }
            ],
        }

    def test_violation_path_is_prefixed_at_depth_1(self) -> None:
        producer = _producer(
            [
                create_field(
                    name="address",
                    type="object",
                    fields=[create_field(name="lat", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _consumer(
            [
                create_field(
                    name="address",
                    type="object",
                    fields=[create_field(name="lat", type="number")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )

        result = validate_contract([producer, consumer])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [
                        {
                            "rule": "TYPE_MISMATCH",
                            "severity": "CRITICAL",
                            "field_path": "address.lat",
                            "producer": {"type": "string"},
                            "consumer": {"type": "number"},
                            "message": (
                                "Field 'address.lat' is a 'string' in Producer"
                                " but Consumer expects a 'number'."
                            ),
                        }
                    ],
                }
            ],
        }

    def test_violation_path_is_prefixed_at_depth_2(self) -> None:
        producer = _producer(
            [
                create_field(
                    name="address",
                    type="object",
                    fields=[
                        create_field(
                            name="location",
                            type="object",
                            fields=[create_field(name="lat", type="string")],
                            unknown=UnknownFieldBehaviour.FORBID,
                        )
                    ],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _consumer(
            [
                create_field(
                    name="address",
                    type="object",
                    fields=[
                        create_field(
                            name="location",
                            type="object",
                            fields=[create_field(name="lat", type="number")],
                            unknown=UnknownFieldBehaviour.FORBID,
                        )
                    ],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )

        result = validate_contract([producer, consumer])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [
                        {
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
                    ],
                }
            ],
        }

    def test_skips_recursion_when_field_types_differ(self) -> None:
        producer = _producer(
            [
                create_field(
                    name="data",
                    type="object",
                    fields=[create_field(name="id", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _consumer([create_field(name="data", type="array")])

        result = validate_contract([producer, consumer])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [
                        {
                            "rule": "TYPE_MISMATCH",
                            "severity": "CRITICAL",
                            "field_path": "data",
                            "producer": {"type": "object"},
                            "consumer": {"type": "array"},
                            "message": (
                                "Field 'data' is a 'object' in Producer"
                                " but Consumer expects a 'array'."
                            ),
                        }
                    ],
                }
            ],
        }

    def test_skips_recursion_when_one_side_has_no_sub_fields(self) -> None:
        producer = _producer(
            [
                create_field(
                    name="data",
                    type="object",
                    fields=[create_field(name="id", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _consumer([create_field(name="data", type="object")])

        result = validate_contract([producer, consumer])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [],
                }
            ],
        }

    def test_fires_when_producer_only_field_and_consumer_forbids_unknowns(self) -> None:
        producer = _producer(
            [create_field(name="internal_id", type="string")],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = _consumer([], unknown=UnknownFieldBehaviour.FORBID)

        result = validate_contract([producer, consumer])

        assert result.to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [
                        {
                            "rule": "UNDECLARED_FIELD",
                            "severity": "CRITICAL",
                            "field_path": "internal_id",
                            "producer": {"exists": True},
                            "consumer": {"exists": False, "unknown": "forbid"},
                            "message": (
                                "Field 'internal_id' is sent by Producer but is not declared"
                                " in Consumer (unknown=forbid)."
                            ),
                        }
                    ],
                }
            ],
        }

    def test_silent_when_consumer_ignores_unknowns(self) -> None:
        result = validate_contract(
            [
                _producer([create_field(name="internal_id", type="string")]),
                _consumer([], unknown=UnknownFieldBehaviour.IGNORE),
            ]
        )

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [],
                }
            ],
        }

    def test_silent_when_consumer_allows_unknowns(self) -> None:
        result = validate_contract(
            [
                _producer([create_field(name="internal_id", type="string")]),
                _consumer([], unknown=UnknownFieldBehaviour.ALLOW),
            ]
        )

        assert result.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [
                {
                    "producer_id": "producer-repo/OrderSchema",
                    "consumer_id": "consumer-repo/OrderSchema",
                    "violations": [],
                }
            ],
        }
