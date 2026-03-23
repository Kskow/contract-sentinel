from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from contract_sentinel.cli.main import app
from contract_sentinel.services.publish import FailedPublish, PublishReport


@patch("contract_sentinel.cli.publish.service_publish_contracts")
@patch("contract_sentinel.cli.publish.get_store", new=MagicMock())
@patch("contract_sentinel.cli.publish.get_parser", new=MagicMock())
@patch("contract_sentinel.cli.publish.load_marked_classes", new=MagicMock())
@patch("contract_sentinel.cli.publish.Config", new=MagicMock())
class TestPublishToStore:
    def test_shows_counts_only_by_default_when_nothing_published(
        self, mock_publish_contracts: MagicMock
    ) -> None:
        mock_publish_contracts.return_value = PublishReport(
            published=[], updated=[], unchanged=[], failed=[]
        )
        runner = CliRunner()

        result = runner.invoke(app, ["publish-contracts"])

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 0\n"
            "  Failed:    0\n"
            "\n"
        )

    def test_shows_published_schemas(self, mock_publish_contracts: MagicMock) -> None:
        mock_publish_contracts.return_value = PublishReport(
            published=["orders/1.0.0/producer/svc.json"], updated=[], unchanged=[], failed=[]
        )
        runner = CliRunner()

        result = runner.invoke(app, ["publish-contracts"])

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 1\n"
            "  Updated:   0\n"
            "  Unchanged: 0\n"
            "  Failed:    0\n"
            "\n  Published schemas:\n"
            "    ✓ orders/1.0.0/producer/svc.json\n"
            "\n"
        )

    def test_shows_updated_schemas(self, mock_publish_contracts: MagicMock) -> None:
        mock_publish_contracts.return_value = PublishReport(
            published=[], updated=["orders/1.0.0/producer/svc.json"], unchanged=[], failed=[]
        )
        runner = CliRunner()

        result = runner.invoke(app, ["publish-contracts"])

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   1\n"
            "  Unchanged: 0\n"
            "  Failed:    0\n"
            "\n  Updated schemas:\n"
            "    ↻ orders/1.0.0/producer/svc.json\n"
            "\n"
        )

    def test_shows_failed_schemas(self, mock_publish_contracts: MagicMock) -> None:
        mock_publish_contracts.return_value = PublishReport(
            published=[],
            updated=[],
            unchanged=[],
            failed=[FailedPublish(key="OrderSchema", reason="Invalid field type")],
        )
        runner = CliRunner()

        result = runner.invoke(app, ["publish-contracts"])

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 0\n"
            "  Failed:    1\n"
            "\n  Failed schemas:\n"
            "    ✗ OrderSchema\n"
            "      Reason: Invalid field type\n"
            "\n"
        )

    def test_shows_unchanged_schemas_only_when_verbose(
        self, mock_publish_contracts: MagicMock
    ) -> None:
        mock_publish_contracts.return_value = PublishReport(
            published=[], updated=[], unchanged=["orders/1.0.0/producer/svc.json"], failed=[]
        )
        runner = CliRunner()

        result = runner.invoke(app, ["publish-contracts", "--verbose"])

        assert result.exit_code == 0
        assert result.output == (
            "\nContract Publish Summary\n\n"
            "  Published: 0\n"
            "  Updated:   0\n"
            "  Unchanged: 1\n"
            "  Failed:    0\n"
            "\n  Unchanged schemas (skipped):\n"
            "    - orders/1.0.0/producer/svc.json\n"
            "\n"
        )
