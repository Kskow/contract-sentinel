from contract_sentinel import Role, contract


def test_package_exports_correct_symbols() -> None:
    # GIVEN
    expected_symbols = {"Role", "contract"}

    # WHEN
    actual_symbols = {Role.__name__, contract.__name__}

    # THEN
    assert expected_symbols.issubset(actual_symbols)
