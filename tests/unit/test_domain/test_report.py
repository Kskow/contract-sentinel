from __future__ import annotations

from contract_sentinel.domain.fix_suggestions import PairFixSuggestion
from contract_sentinel.domain.report import (
    ContractReport,
    ContractsValidationReport,
    FixSuggestionsReport,
    TopicFixSuggestions,
    ValidationStatus,
)
from contract_sentinel.domain.rules.engine import PairViolations
from tests.unit.helpers import create_violation

_CRITICAL_VIOLATION = create_violation(
    "TYPE_MISMATCH",
    field_path="id",
    producer={"type": "string"},
    consumer={"type": "integer"},
    message="Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.",
)
_WARNING_VIOLATION = create_violation(
    "COUNTERPART_MISMATCH",
    severity="WARNING",
    field_path="",
    message="Topic 'orders' has 1 producer(s) but no matching consumer.",
)


class TestValidationStatus:
    def test_contract_report_status_is_passed_when_no_pairs(self) -> None:
        report = ContractReport(topic="orders", pairs=[])

        assert report.status == ValidationStatus.PASSED

    def test_contract_report_status_is_passed_when_violations_are_warnings_only(self) -> None:
        pair = PairViolations(
            producer_id="svc/Schema",
            consumer_id=None,
            violations=[_WARNING_VIOLATION],
        )

        assert ContractReport(topic="orders", pairs=[pair]).status == ValidationStatus.PASSED

    def test_contract_report_status_is_failed_when_any_violation_is_critical(self) -> None:
        pair = PairViolations(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-b/OrderConsumer",
            violations=[_CRITICAL_VIOLATION],
        )

        assert ContractReport(topic="orders", pairs=[pair]).status == ValidationStatus.FAILED

    def test_contracts_validation_report_status_is_passed_when_all_reports_pass(self) -> None:
        report = ContractsValidationReport(reports=[ContractReport(topic="orders", pairs=[])])

        assert report.status == ValidationStatus.PASSED

    def test_contracts_validation_report_status_is_failed_when_any_report_fails(self) -> None:
        failing_pair = PairViolations(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-b/OrderConsumer",
            violations=[_CRITICAL_VIOLATION],
        )
        report = ContractsValidationReport(
            reports=[
                ContractReport(topic="orders", pairs=[]),
                ContractReport(topic="payments", pairs=[failing_pair]),
            ]
        )

        assert report.status == ValidationStatus.FAILED

    def test_contracts_validation_report_status_is_passed_when_empty(self) -> None:
        assert ContractsValidationReport(reports=[]).status == ValidationStatus.PASSED


class TestContractReportToDict:
    def test_serialises_empty_pairs(self) -> None:
        report = ContractReport(topic="orders", pairs=[])

        assert report.to_dict() == {
            "topic": "orders",
            "status": "PASSED",
            "pairs": [],
        }

    def test_serialises_pairs_with_violations(self) -> None:
        pair = PairViolations(
            producer_id="orders-service/OrderSchema",
            consumer_id="checkout-service/OrderSchema",
            violations=[_CRITICAL_VIOLATION],
        )

        assert ContractReport(topic="orders", pairs=[pair]).to_dict() == {
            "topic": "orders",
            "status": "FAILED",
            "pairs": [
                {
                    "producer_id": "orders-service/OrderSchema",
                    "consumer_id": "checkout-service/OrderSchema",
                    "violations": [
                        {
                            "rule": "TYPE_MISMATCH",
                            "severity": "CRITICAL",
                            "field_path": "id",
                            "producer": {"type": "string"},
                            "consumer": {"type": "integer"},
                            "message": (
                                "Field 'id' is a 'string' in Producer"
                                " but Consumer expects a 'integer'."
                            ),
                        }
                    ],
                }
            ],
        }


class TestFixSuggestionsReport:
    def test_has_suggestions_is_false_when_no_topics(self) -> None:
        assert FixSuggestionsReport(suggestions_by_topic=[]).has_suggestions is False

    def test_has_suggestions_is_true_when_at_least_one_topic_is_present(self) -> None:
        pair = PairFixSuggestion(
            producer_id="svc-a/OrderSchema",
            consumer_id="svc-b/OrderConsumer",
            producer_suggestions="In `OrderSchema`, make the following changes...\n\n1. Fix it.",
            consumer_suggestions="In `OrderConsumer`, make the following changes...\n\n1. Fix it.",
        )
        report = FixSuggestionsReport(
            suggestions_by_topic=[TopicFixSuggestions(topic="orders", pairs=[pair])]
        )

        assert report.has_suggestions is True


class TestContractsValidationReportToDict:
    def test_serialises_empty_reports(self) -> None:
        assert ContractsValidationReport(reports=[]).to_dict() == {
            "status": "PASSED",
            "reports": [],
        }

    def test_serialises_nested_reports_and_pairs(self) -> None:
        pair = PairViolations(
            producer_id="orders-service/OrderSchema",
            consumer_id="checkout-service/OrderSchema",
            violations=[_CRITICAL_VIOLATION],
        )

        assert ContractsValidationReport(
            reports=[ContractReport(topic="orders", pairs=[pair])]
        ).to_dict() == {
            "status": "FAILED",
            "reports": [
                {
                    "topic": "orders",
                    "status": "FAILED",
                    "pairs": [
                        {
                            "producer_id": "orders-service/OrderSchema",
                            "consumer_id": "checkout-service/OrderSchema",
                            "violations": [
                                {
                                    "rule": "TYPE_MISMATCH",
                                    "severity": "CRITICAL",
                                    "field_path": "id",
                                    "producer": {"type": "string"},
                                    "consumer": {"type": "integer"},
                                    "message": (
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
        }
