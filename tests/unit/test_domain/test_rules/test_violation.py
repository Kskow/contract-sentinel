from contract_sentinel.domain.rules.violation import Violation


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
