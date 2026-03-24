from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from contract_sentinel.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    from contract_sentinel.adapters.contract_store import S3ContractStore


_PRODUCER_SRC = """\
import marshmallow as ma
from contract_sentinel import contract, Role

@contract(topic="orders", role=Role.PRODUCER)
class OrderSchema(ma.Schema):
    id = ma.fields.Integer(required=True)
"""


_PRODUCER_SRC_UPDATED = """\
import marshmallow as ma
from contract_sentinel import contract, Role

@contract(topic="orders", role=Role.PRODUCER)
class OrderSchema(ma.Schema):
    id = ma.fields.Integer(required=True)
    name = ma.fields.String()
"""


_BROKEN_SCHEMA_SRC = """\
from contract_sentinel import contract, Role

@contract(topic="orders", role=Role.PRODUCER)
class BrokenSchema:
    pass
"""


class TestPublishContracts:
    def test_publishes_new_schemas_on_first_run(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        (tmp_path / "schema.py").write_text(_PRODUCER_SRC)

        result = CliRunner().invoke(
            app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env
        )

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 1\n"
            "  Updated:   0\n"
            "  Unchanged: 0\n"
            "  Failed:    0\n"
            "\n  Published schemas:\n"
            "    ✓ orders/producer/test-repo_OrderSchema.json\n"
            "\n"
        )

        assert s3_store.file_exists("orders/producer/test-repo_OrderSchema.json")

    def test_second_run_is_idempotent(
        self,
        tmp_path: Path,
        cli_env: dict[str, str],
    ) -> None:
        (tmp_path / "schema.py").write_text(_PRODUCER_SRC)
        runner = CliRunner()
        runner.invoke(app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env)

        result = runner.invoke(app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env)

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 1\n"
            "  Failed:    0\n"
            "\n"
        )

    def test_updates_schema_when_content_changes(
        self,
        tmp_path: Path,
        cli_env: dict[str, str],
    ) -> None:
        schema_file = tmp_path / "schema.py"
        schema_file.write_text(_PRODUCER_SRC)
        runner = CliRunner()
        runner.invoke(app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env)

        schema_file.write_text(_PRODUCER_SRC_UPDATED)
        result = runner.invoke(app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env)

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   1\n"
            "  Unchanged: 0\n"
            "  Failed:    0\n"
            "\n  Updated schemas:\n"
            "    ↻ orders/producer/test-repo_OrderSchema.json\n"
            "\n"
        )

    def test_parse_failure_is_reported_and_nothing_is_written(
        self,
        tmp_path: Path,
        s3_store: S3ContractStore,
        cli_env: dict[str, str],
    ) -> None:
        (tmp_path / "schema.py").write_text(_BROKEN_SCHEMA_SRC)

        result = CliRunner().invoke(
            app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env
        )

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 0\n"
            "  Failed:    1\n"
            "\n  Failed schemas:\n"
            "    ✗ BrokenSchema\n"
            "      Reason: Cannot detect schema framework for 'BrokenSchema'."
            " Supported frameworks: marshmallow.\n"
            "\n"
        )

        assert not s3_store.file_exists("orders/1.0.0/producer/test-repo_BrokenSchema.json")

    def test_verbose_flag_reveals_unchanged_schemas(
        self,
        tmp_path: Path,
        cli_env: dict[str, str],
    ) -> None:
        (tmp_path / "schema.py").write_text(_PRODUCER_SRC)
        runner = CliRunner()

        runner.invoke(app, ["publish-contracts", "--path", str(tmp_path)], env=cli_env)

        result = runner.invoke(
            app, ["publish-contracts", "--path", str(tmp_path), "--verbose"], env=cli_env
        )

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 1\n"
            "  Failed:    0\n"
            "\n  Unchanged schemas (skipped):\n"
            "    - orders/producer/test-repo_OrderSchema.json\n"
            "\n"
        )
