from contract_sentinel.domain.marker import ContractMeta, Role, contract


class TestContract:
    def test_contract_attaches_metadata_correctly(self) -> None:
        topic = "orders.created"
        role = Role.PRODUCER
        version = "1.0.0"

        @contract(topic=topic, role=role, version=version)
        class MySchema:
            pass

        assert MySchema.__contract__ == ContractMeta(topic=topic, role=role, version=version)  # type: ignore[attr-defined]

    def test_contract_does_not_affect_other_attributes(self) -> None:
        topic = "orders.created"
        role = Role.CONSUMER
        version = "2.0.1"

        @contract(topic=topic, role=role, version=version)
        class MySchema:
            name = "OrderSchema"

        assert MySchema.name == "OrderSchema"
        assert hasattr(MySchema, "__contract__")
