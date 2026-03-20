from __future__ import annotations

from unittest.mock import MagicMock, patch

from contract_sentinel.domain.rules.engine import validate_group, validate_pair
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour
from tests.unit.test_domain.test_rules.helpers import field


def _violation(field_path: str = "field") -> Violation:
    return Violation(
        rule="TEST_RULE",
        severity="CRITICAL",
        field_path=field_path,
        producer={},
        consumer={},
        message=f"Field '{field_path}' test violation.",
    )


def _schema(
    fields_list: list[ContractField],
    unknown: UnknownFieldBehaviour = UnknownFieldBehaviour.FORBID,
) -> ContractSchema:
    return ContractSchema(
        topic="orders",
        role="producer",
        version="1.0.0",
        repository="test-repo",
        class_name="OrderSchema",
        unknown=unknown,
        fields=fields_list,
    )


def _mock_rule(return_value: list[Violation] | None = None) -> MagicMock:
    rule = MagicMock()
    rule.check.return_value = return_value if return_value is not None else []
    return rule


class TestValidatePair:
    def test_every_rule_is_called_for_a_matched_field(self) -> None:
        rule_a = _mock_rule()
        rule_b = _mock_rule()
        p_field = field(name="id", type="string")
        c_field = field(name="id", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule_a, rule_b]):
            validate_pair(_schema([p_field]), _schema([c_field]))

        rule_a.check.assert_called_once_with(p_field, c_field)
        rule_b.check.assert_called_once_with(p_field, c_field)

    def test_every_rule_is_called_for_each_field_independently(self) -> None:
        rule = _mock_rule()
        p_id = field(name="id", type="string")
        p_name = field(name="name", type="string")
        c_id = field(name="id", type="string")
        c_name = field(name="name", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_pair(_schema([p_id, p_name]), _schema([c_id, c_name]))

        assert rule.check.call_count == 2
        rule.check.assert_any_call(p_id, c_id)
        rule.check.assert_any_call(p_name, c_name)

    def test_consumer_only_field_passes_none_as_producer(self) -> None:
        rule = _mock_rule()
        c_field = field(name="extra", type="string", is_required=False)

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_pair(_schema([]), _schema([c_field]))

        rule.check.assert_called_once_with(None, c_field)

    def test_producer_only_field_passes_none_as_consumer(self) -> None:
        rule = _mock_rule()
        p_field = field(name="extra", type="string")

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            # Consumer IGNORE keeps the undeclared pass silent so it doesn't pollute assertions.
            # Producer unknown is irrelevant — only consumer.unknown governs the undeclared pass.
            validate_pair(
                _schema([p_field]),
                _schema([], unknown=UnknownFieldBehaviour.IGNORE),
            )

        rule.check.assert_called_once_with(p_field, None)

    def test_violations_from_rules_are_collected_and_returned(self) -> None:
        violation = _violation("id")
        rule = _mock_rule(return_value=[violation])

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_pair(
                _schema([field(name="id", type="string")]),
                _schema([field(name="id", type="string")]),
            )

        assert result == [violation]

    def test_violations_from_multiple_fields_are_aggregated(self) -> None:
        v1 = _violation("id")
        v2 = _violation("name")
        rule = _mock_rule()
        rule.check.side_effect = [[v1], [v2]]

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            result = validate_pair(
                _schema([field(name="id", type="string"), field(name="name", type="string")]),
                _schema([field(name="id", type="string"), field(name="name", type="string")]),
            )

        assert result == [v1, v2]

    def test_violation_path_is_prefixed_at_depth_1(self) -> None:
        # TypeMismatchRule fires on address.lat (string vs number).
        producer = _schema(
            [
                field(
                    name="address",
                    type="object",
                    fields=[field(name="lat", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _schema(
            [
                field(
                    name="address",
                    type="object",
                    fields=[field(name="lat", type="number")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )

        violations = validate_pair(producer, consumer)

        assert len(violations) == 1
        assert violations[0].field_path == "address.lat"
        assert "'address.lat'" in violations[0].message

    def test_violation_path_is_prefixed_at_depth_2(self) -> None:
        # TypeMismatchRule fires on address.location.lat (string vs number).
        producer = _schema(
            [
                field(
                    name="address",
                    type="object",
                    fields=[
                        field(
                            name="location",
                            type="object",
                            fields=[field(name="lat", type="string")],
                            unknown=UnknownFieldBehaviour.FORBID,
                        )
                    ],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _schema(
            [
                field(
                    name="address",
                    type="object",
                    fields=[
                        field(
                            name="location",
                            type="object",
                            fields=[field(name="lat", type="number")],
                            unknown=UnknownFieldBehaviour.FORBID,
                        )
                    ],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )

        violations = validate_pair(producer, consumer)

        assert len(violations) == 1
        assert violations[0].field_path == "address.location.lat"
        assert "'address.location.lat'" in violations[0].message

    def test_skips_recursion_when_field_types_differ(self) -> None:
        # Producer is "object", consumer is "array" — types differ, no nested pass.
        producer = _schema(
            [
                field(
                    name="data",
                    type="object",
                    fields=[field(name="id", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _schema([field(name="data", type="array")])

        violations = validate_pair(producer, consumer)

        # TypeMismatchRule fires on "data" itself — no dot-separated paths.
        assert all(v.field_path == "data" for v in violations)

    def test_skips_recursion_when_one_side_has_no_sub_fields(self) -> None:
        producer = _schema(
            [
                field(
                    name="data",
                    type="object",
                    fields=[field(name="id", type="string")],
                    unknown=UnknownFieldBehaviour.FORBID,
                )
            ]
        )
        consumer = _schema([field(name="data", type="object")])  # no sub-fields

        violations = validate_pair(producer, consumer)

        assert not any("." in v.field_path for v in violations)

    def test_fires_when_producer_only_field_and_consumer_forbids_unknowns(self) -> None:
        producer = _schema(
            [field(name="internal_id", type="string")],
            unknown=UnknownFieldBehaviour.FORBID,
        )
        consumer = _schema([], unknown=UnknownFieldBehaviour.FORBID)

        violations = validate_pair(producer, consumer)

        assert len(violations) == 1
        assert violations[0].rule == "UNDECLARED_FIELD"
        assert violations[0].field_path == "internal_id"

    def test_silent_when_consumer_ignores_unknowns(self) -> None:
        # Producer unknown is irrelevant — only consumer.unknown governs the undeclared pass.
        producer = _schema([field(name="internal_id", type="string")])
        consumer = _schema([], unknown=UnknownFieldBehaviour.IGNORE)

        assert validate_pair(producer, consumer) == []

    def test_silent_when_consumer_allows_unknowns(self) -> None:
        # Producer unknown is irrelevant — only consumer.unknown governs the undeclared pass.
        producer = _schema([field(name="internal_id", type="string")])
        consumer = _schema([], unknown=UnknownFieldBehaviour.ALLOW)

        assert validate_pair(producer, consumer) == []


class TestValidateGroup:
    def test_returns_counterpart_violations_and_skips_pairwise_on_lonely_producer(self) -> None:
        producer = _schema([field(name="id", type="string")])
        rule = _mock_rule()

        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            violations = validate_group([producer], [])

        assert len(violations) == 1
        assert violations[0].rule == "COUNTERPART_MISMATCH"
        # pairwise rule was never called
        assert rule.check.call_count == 0

    def test_runs_pairwise_validation_for_every_producer_consumer_combination(self) -> None:
        p1 = _schema([field(name="id", type="string")])
        p1.repository = "p1-repo"
        c1 = _schema([field(name="id", type="string")])
        c1.role = "consumer"
        c1.repository = "c1-repo"
        c2 = _schema([field(name="id", type="string")])
        c2.role = "consumer"
        c2.repository = "c2-repo"

        rule = _mock_rule()
        with patch("contract_sentinel.domain.rules.engine.PAIR_RULES", [rule]):
            validate_group([p1], [c1, c2])

        # p1 vs c1, p1 vs c2
        assert rule.check.call_count == 2
