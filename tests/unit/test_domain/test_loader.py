from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from contract_sentinel.domain.loader import load_marked_classes


class TestLoadMarkedClasses:
    def test_returns_class_decorated_with_contract(self, tmp_path: Path) -> None:
        (tmp_path / "schemas.py").write_text(
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.PRODUCER)\n"
            "class OrderSchema:\n"
            "    pass\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "OrderSchema"

    def test_excludes_unmarked_classes(self, tmp_path: Path) -> None:
        (tmp_path / "schemas.py").write_text(
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.PRODUCER)\n"
            "class MarkedSchema:\n"
            "    pass\n"
            "\n"
            "class UnmarkedSchema:\n"
            "    pass\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "MarkedSchema"

    def test_ignores_non_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_text("not python")
        (tmp_path / "config.json").write_text("{}")

        result = load_marked_classes(tmp_path)

        assert result == []

    def test_returns_empty_list_for_empty_directory(self, tmp_path: Path) -> None:
        result = load_marked_classes(tmp_path)

        assert result == []

    def test_discovers_classes_in_nested_subdirectories(self, tmp_path: Path) -> None:
        subdir = tmp_path / "events"
        subdir.mkdir()
        (subdir / "orders.py").write_text(
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.CONSUMER)\n"
            "class OrderConsumerSchema:\n"
            "    pass\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "OrderConsumerSchema"

    def test_skips_file_with_syntax_error_and_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "bad.py").write_text("this is not: valid ::: python !!!")
        (tmp_path / "good.py").write_text(
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='payments', role=Role.PRODUCER)\n"
            "class PaymentSchema:\n"
            "    pass\n"
        )

        with caplog.at_level(logging.WARNING, logger="contract_sentinel.domain.loader"):
            result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "PaymentSchema"
        assert (
            "contract_sentinel.domain.loader",
            logging.WARNING,
            f"Could not import '{tmp_path / 'bad.py'}' after all retries — skipping.",
        ) in caplog.record_tuples

    def test_cross_file_import_resolves_when_dependency_is_alphabetically_first(
        self, tmp_path: Path
    ) -> None:
        # a_base.py succeeds on the first pass — b_orders.py then resolves immediately
        # on the same pass since a_base is already in sys.modules.
        (tmp_path / "a_base.py").write_text("class BaseSchema:\n    field: str = 'base'\n")
        (tmp_path / "b_orders.py").write_text(
            "from a_base import BaseSchema\n"
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.PRODUCER)\n"
            "class OrderSchema(BaseSchema):\n"
            "    pass\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "OrderSchema"

    def test_marked_class_with_nested_field_type_from_later_module_is_discovered_via_retry(
        self, tmp_path: Path
    ) -> None:
        # b_orders.py sorts before c_address.py — it fails on the first pass since
        # c_address is not yet in sys.modules. The retry loop picks it up on the
        # second pass after c_address.py succeeds.
        (tmp_path / "b_orders.py").write_text(
            "from c_address import AddressField\n"
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.PRODUCER)\n"
            "class OrderSchema:\n"
            "    address = AddressField\n"
        )
        (tmp_path / "c_address.py").write_text(
            "class AddressField:\n    street: str\n    city: str\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "OrderSchema"

    def test_marked_class_with_nested_field_type_from_another_module_is_discovered(
        self, tmp_path: Path
    ) -> None:
        # a_address.py is processed first — AddressField is registered in sys.modules
        # so that the import in b_orders.py succeeds and OrderSchema is not skipped.
        (tmp_path / "a_address.py").write_text(
            "class AddressField:\n    street: str\n    city: str\n"
        )
        (tmp_path / "b_orders.py").write_text(
            "from a_address import AddressField\n"
            "from contract_sentinel.domain.participant import Role, contract\n"
            "\n"
            "@contract(topic='orders', role=Role.PRODUCER)\n"
            "class OrderSchema:\n"
            "    address = AddressField\n"
        )

        result = load_marked_classes(tmp_path)

        assert len(result) == 1
        assert result[0].__name__ == "OrderSchema"
