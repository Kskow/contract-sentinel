from contract_sentinel.domain.schema import (
    ContractField,
    ContractSchema,
    UnknownFieldBehaviour,
)
from tests.unit.helpers import create_field


class TestContractField:
    def test_init_stores_all_fields_correctly(self) -> None:
        field = ContractField(
            name="status",
            type="string",
            is_required=True,
            is_nullable=False,
            is_load_only=True,
            fields=None,
            metadata={
                "format": "enum",
                "allowed_values": ["active", "inactive"],
                "load_default": "active",
                "deprecated": True,
            },
            unknown=UnknownFieldBehaviour.IGNORE,
        )

        expected = {
            "name": "status",
            "type": "string",
            "is_required": True,
            "is_nullable": False,
            "is_load_only": True,
            "is_supported": True,
            "metadata": {
                "format": "enum",
                "allowed_values": ["active", "inactive"],
                "load_default": "active",
                "deprecated": True,
            },
            "unknown": "ignore",
        }
        assert field.to_dict() == expected
        assert ContractField.from_dict(expected) == field

    def test_to_dict_omits_optional_keys_when_unset(self) -> None:
        field = create_field("age", "integer", is_required=False)

        assert field.to_dict() == {
            "name": "age",
            "type": "integer",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
        }

    def test_from_dict_defaults_optional_flags_when_absent(self) -> None:
        data = {"name": "age", "type": "integer", "is_required": False, "is_nullable": False}

        field = ContractField.from_dict(data)

        assert field.is_load_only is False
        assert field.is_dump_only is False
        assert field.is_supported is True

    def test_to_dict_serialises_nested_fields_recursively(self) -> None:
        child = create_field("street")
        parent = create_field("address", "object", fields=[child])

        assert parent.to_dict()["fields"] == [child.to_dict()]

    def test_from_dict_round_trip_with_nested_fields(self) -> None:
        child = create_field("street")
        parent = create_field("address", "object", fields=[child])

        assert ContractField.from_dict(parent.to_dict()) == parent


class TestContractSchema:
    def test_round_trip_preserves_equality_with_empty_fields(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            repository="my-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        assert ContractSchema.from_dict(schema.to_dict()) == schema

    def test_round_trip_preserves_equality_with_multiple_fields(self) -> None:
        nested = ContractField(name="street", type="str", is_required=True, is_nullable=False)
        address = ContractField(
            name="address",
            type="object",
            is_required=True,
            is_nullable=False,
            fields=[nested],
            unknown=UnknownFieldBehaviour.ALLOW,
        )
        name_field = ContractField(
            name="name",
            type="str",
            is_required=True,
            is_nullable=False,
            metadata={"load_default": "anonymous"},
        )
        schema = ContractSchema(
            topic="users.registered",
            role="consumer",
            repository="user-service",
            class_name="UserSchema",
            unknown=UnknownFieldBehaviour.IGNORE,
            fields=[name_field, address],
        )

        assert ContractSchema.from_dict(schema.to_dict()) == schema

    def test_to_dict_serialises_unknown_as_string_literal(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            repository="my-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        assert schema.to_dict()["unknown"] == "forbid"

    def test_from_dict_deserialises_unknown_as_enum_member(self) -> None:
        data = {
            "topic": "orders.created",
            "role": "producer",
            "repository": "my-service",
            "class_name": "OrderSchema",
            "unknown": "allow",
            "fields": [],
        }

        assert ContractSchema.from_dict(data).unknown == UnknownFieldBehaviour.ALLOW

    def test_to_store_key_returns_producer_path(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            repository="order-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        assert schema.to_store_key() == "orders.created/producer/order-service/OrderSchema.json"

    def test_to_store_key_returns_consumer_path(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="consumer",
            repository="billing-service",
            class_name="InvoiceSchema",
            unknown=UnknownFieldBehaviour.IGNORE,
            fields=[],
        )

        assert schema.to_store_key() == "orders.created/consumer/billing-service/InvoiceSchema.json"

    def test_to_store_key_handles_topic_containing_slashes(self) -> None:
        schema = ContractSchema(
            topic="orders/created",
            role="producer",
            repository="order-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        key = schema.to_store_key()

        assert key == "orders/created/producer/order-service/OrderSchema.json"

    def test_to_dict_serialises_all_root_fields_correctly(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            repository="my-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        assert schema.to_dict() == {
            "topic": "orders.created",
            "role": "producer",
            "repository": "my-service",
            "class_name": "OrderSchema",
            "unknown": "forbid",
            "fields": [],
        }
