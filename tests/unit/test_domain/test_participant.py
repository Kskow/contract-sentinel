from contract_sentinel.domain.participant import ContractMeta, Role, contract


class TestContract:
    def test_contract_attaches_metadata_correctly(self) -> None:
        topic = "orders.created"
        role = Role.PRODUCER

        @contract(topic=topic, role=role)
        class MySchema:
            pass

        assert MySchema.__contract__ == ContractMeta(topic=topic, role=role)  # type: ignore[attr-defined]

    def test_contract_does_not_affect_other_attributes(self) -> None:
        topic = "orders.created"
        role = Role.CONSUMER

        @contract(topic=topic, role=role)
        class MySchema:
            name = "OrderSchema"

        assert MySchema.name == "OrderSchema"
        assert hasattr(MySchema, "__contract__")
