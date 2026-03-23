from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from contract_sentinel.cli.main import app
from contract_sentinel.cli.validate import print_report
from contract_sentinel.domain.rules.engine import PairViolations
from contract_sentinel.domain.rules.violation import Violation
from contract_sentinel.domain.schema import ContractField, ContractSchema, UnknownFieldBehaviour
from contract_sentinel.services.validate import (
    ContractReport,
    ContractsValidationReport,
    ValidationStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

    from contract_sentinel.adapters.contract_store import S3ContractStore


def _producer(field_type: str = "integer") -> ContractSchema:
    return ContractSchema(
        topic="orders",
        role="producer",
        version="1.0.0",
        repository="orders-service",
        class_name="OrderProducerSchema",
        unknown=UnknownFieldBehaviour.FORBID,
        fields=[ContractField(name="id", type=field_type, is_required=True, is_nullable=False)],
    )


def _consumer() -> ContractSchema:
    return ContractSchema(
        topic="orders",
        role="consumer",
        version="1.0.0",
        repository="test-repo",
        class_name="OrderConsumerSchema",
        unknown=UnknownFieldBehaviour.FORBID,
        fields=[ContractField(name="id", type="integer", is_required=True, is_nullable=False)],
    )


def _seed(store: S3ContractStore, *schemas: ContractSchema) -> None:
    """Write one or more ContractSchemas to the store at their canonical keys."""
    for schema in schemas:
        store.put_file(schema.to_store_key(), json.dumps(schema.to_dict()))


# Local consumer marshmallow schema written to a temp file for `sentinel validate-local` tests.
_LOCAL_CONSUMER_SRC = """\
import marshmallow as ma
from contract_sentinel import contract, Role

@contract(topic="orders", role=Role.CONSUMER, version="1.0.0")
class OrderConsumerSchema(ma.Schema):
    id = ma.fields.Integer(required=True)
"""


class TestPrintReport:
    def test_shows_passed_contract_when_verbose(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.PASSED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.PASSED,
                    pairs=[
                        PairViolations(
                            producer_id="orders-service/OrderProducerSchema",
                            consumer_id="test-repo/OrderConsumerSchema",
                            violations=[],
                        )
                    ],
                )
            ],
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report, verbose=True)

        assert buf.getvalue() == (
            "\nContract Validation — PASSED\n"
            "\n"
            "  ✓  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "\n"
        )

    def test_hides_passed_contracts_by_default(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.PASSED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.PASSED,
                    pairs=[],
                )
            ],
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report)

        assert buf.getvalue() == ("\nContract Validation — PASSED\n\n\n")

    def test_shows_failed_contract_with_violation(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.FAILED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.FAILED,
                    pairs=[
                        PairViolations(
                            producer_id="orders-service/OrderProducerSchema",
                            consumer_id="test-repo/OrderConsumerSchema",
                            violations=[
                                Violation(
                                    rule="TYPE_MISMATCH",
                                    severity="CRITICAL",
                                    field_path="id",
                                    producer={"type": "string"},
                                    consumer={"type": "integer"},
                                    message=(
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report)

        assert buf.getvalue() == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )

    def test_shows_all_violations_for_failed_contract(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.FAILED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.FAILED,
                    pairs=[
                        PairViolations(
                            producer_id="orders-service/OrderProducerSchema",
                            consumer_id="test-repo/OrderConsumerSchema",
                            violations=[
                                Violation(
                                    rule="TYPE_MISMATCH",
                                    severity="CRITICAL",
                                    field_path="id",
                                    producer={"type": "string"},
                                    consumer={"type": "integer"},
                                    message=(
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                ),
                                Violation(
                                    rule="NULLABILITY_MISMATCH",
                                    severity="CRITICAL",
                                    field_path="name",
                                    producer={"is_nullable": True},
                                    consumer={"is_nullable": False},
                                    message=(
                                        "Field 'name' is nullable in Producer"
                                        " but Consumer does not allow null."
                                    ),
                                ),
                            ],
                        )
                    ],
                )
            ],
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report)

        assert buf.getvalue() == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "         [CRITICAL] NULLABILITY_MISMATCH @ name\n"
            "         Field 'name' is nullable in Producer but Consumer does not allow null.\n"
            "\n"
        )

    def test_shows_all_topics_when_verbose(self) -> None:
        report = ContractsValidationReport(
            status=ValidationStatus.FAILED,
            reports=[
                ContractReport(
                    topic="orders",
                    version="1.0.0",
                    status=ValidationStatus.PASSED,
                    pairs=[
                        PairViolations(
                            producer_id="orders-service/OrderProducerSchema",
                            consumer_id="test-repo/OrderConsumerSchema",
                            violations=[],
                        )
                    ],
                ),
                ContractReport(
                    topic="payments",
                    version="2.0.0",
                    status=ValidationStatus.FAILED,
                    pairs=[
                        PairViolations(
                            producer_id="payments-service/PaymentProducerSchema",
                            consumer_id="test-repo/PaymentConsumerSchema",
                            violations=[
                                Violation(
                                    rule="TYPE_MISMATCH",
                                    severity="CRITICAL",
                                    field_path="id",
                                    producer={"type": "string"},
                                    consumer={"type": "integer"},
                                    message=(
                                        "Field 'id' is a 'string' in Producer"
                                        " but Consumer expects a 'integer'."
                                    ),
                                )
                            ],
                        )
                    ],
                ),
            ],
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report, verbose=True)

        assert buf.getvalue() == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✓  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "  ✗  payments/2.0.0\n"
            "       payments-service/PaymentProducerSchema vs test-repo/PaymentConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )

    def test_prints_only_header_when_no_contracts(self) -> None:
        report = ContractsValidationReport(status=ValidationStatus.PASSED, reports=[])

        buf = io.StringIO()
        with redirect_stdout(buf):
            print_report(report)

        assert buf.getvalue() == ("\nContract Validation — PASSED\n\n\n")


class TestValidateLocal:
    def test_passes_when_schemas_are_compatible(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer())
        (tmp_path / "consumer.py").write_text(_LOCAL_CONSUMER_SRC)

        result = CliRunner().invoke(app, ["validate-local", "--path", str(tmp_path)], env=cli_env)

        assert result.exit_code == 0
        assert result.output == "\nContract Validation — PASSED\n\n\n"

    def test_verbose_flag_shows_passed_contracts(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer())
        (tmp_path / "consumer.py").write_text(_LOCAL_CONSUMER_SRC)

        result = CliRunner().invoke(
            app, ["validate-local", "--path", str(tmp_path), "--verbose"], env=cli_env
        )

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Validation — PASSED\n"
            "\n"
            "  ✓  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "\n"
        )

    def test_fails_when_schemas_are_incompatible(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(field_type="string"))
        (tmp_path / "consumer.py").write_text(_LOCAL_CONSUMER_SRC)

        result = CliRunner().invoke(app, ["validate-local", "--path", str(tmp_path)], env=cli_env)

        assert result.exit_code == 1
        assert result.output == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )

    def test_dry_run_still_prints_violations_but_exits_zero(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(field_type="string"))
        (tmp_path / "consumer.py").write_text(_LOCAL_CONSUMER_SRC)

        result = CliRunner().invoke(
            app, ["validate-local", "--path", str(tmp_path), "--dry-run"], env=cli_env
        )

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )


class TestValidatePublished:
    def test_passes_when_schemas_are_compatible(
        self,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(), _consumer())

        result = CliRunner().invoke(app, ["validate-published"], env=cli_env)

        assert result.exit_code == 0
        assert result.output == "\nContract Validation — PASSED\n\n\n"

    def test_verbose_flag_shows_passed_contracts(
        self,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(), _consumer())

        result = CliRunner().invoke(app, ["validate-published", "--verbose"], env=cli_env)

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Validation — PASSED\n"
            "\n"
            "  ✓  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "\n"
        )

    def test_fails_when_schemas_are_incompatible(
        self,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(field_type="string"), _consumer())

        result = CliRunner().invoke(app, ["validate-published"], env=cli_env)

        assert result.exit_code == 1
        assert result.output == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )

    def test_dry_run_still_prints_violations_but_exits_zero(
        self,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        _seed(s3_store, _producer(field_type="string"), _consumer())

        result = CliRunner().invoke(app, ["validate-published", "--dry-run"], env=cli_env)

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Validation — FAILED\n"
            "\n"
            "  ✗  orders/1.0.0\n"
            "       orders-service/OrderProducerSchema vs test-repo/OrderConsumerSchema\n"
            "         [CRITICAL] TYPE_MISMATCH @ id\n"
            "         Field 'id' is a 'string' in Producer but Consumer expects a 'integer'.\n"
            "\n"
        )
