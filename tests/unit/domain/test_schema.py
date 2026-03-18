from contract_sentinel.domain.schema import (
    MISSING,
    ContractField,
    ContractSchema,
    UnknownFieldBehaviour,
)


class TestContractField:
    def test_init_stores_all_fields_correctly(self) -> None:
        field = ContractField(
            name="email",
            type="str",
            is_required=True,
            is_nullable=False,
            default="user@example.com",
            unknown=UnknownFieldBehaviour.IGNORE,
        )

        assert field.to_dict() == {
            "name": "email",
            "type": "str",
            "is_required": True,
            "is_nullable": False,
            "default": "user@example.com",
            "unknown": "ignore",
        }

    def test_init_sets_missing_default_when_not_provided(self) -> None:
        field = ContractField(name="age", type="int", is_required=False, is_nullable=False)

        assert field.default is MISSING

    def test_to_dict_omits_default_when_missing(self) -> None:
        field = ContractField(name="age", type="int", is_required=False, is_nullable=False)

        assert "default" not in field.to_dict()

    def test_to_dict_includes_default_null_when_none(self) -> None:
        field = ContractField(
            name="age", type="int", is_required=False, is_nullable=True, default=None
        )

        assert field.to_dict()["default"] is None

    def test_to_dict_serialises_nested_fields_recursively(self) -> None:
        child = ContractField(name="street", type="str", is_required=True, is_nullable=False)
        parent = ContractField(
            name="address",
            type="object",
            is_required=True,
            is_nullable=False,
            fields=[child],
        )

        assert parent.to_dict()["fields"] == [child.to_dict()]

    def test_from_dict_deserialises_nested_fields_recursively(self) -> None:
        child = ContractField(name="street", type="str", is_required=True, is_nullable=False)
        parent = ContractField(
            name="address",
            type="object",
            is_required=True,
            is_nullable=False,
            fields=[child],
        )

        assert ContractField.from_dict(parent.to_dict()).fields == [child]

    def test_round_trip_preserves_equality_without_default(self) -> None:
        field = ContractField(
            name="count",
            type="int",
            is_required=True,
            is_nullable=False,
            unknown=UnknownFieldBehaviour.IGNORE,
        )

        assert ContractField.from_dict(field.to_dict()) == field

    def test_to_dict_includes_metadata_when_present(self) -> None:
        field = ContractField(
            name="created_at",
            type="datetime",
            is_required=True,
            is_nullable=False,
            metadata={"format": "iso8601", "timezone": "utc"},
        )

        assert field.to_dict()["metadata"] == {"format": "iso8601", "timezone": "utc"}

    def test_to_dict_omits_metadata_when_none(self) -> None:
        field = ContractField(name="age", type="int", is_required=True, is_nullable=False)

        assert "metadata" not in field.to_dict()

    def test_round_trip_preserves_metadata(self) -> None:
        field = ContractField(
            name="price",
            type="decimal",
            is_required=True,
            is_nullable=False,
            metadata={"places": 2, "rounding": "ROUND_HALF_UP"},
        )

        assert ContractField.from_dict(field.to_dict()) == field

    def test_round_trip_preserves_equality_with_default_none(self) -> None:
        field = ContractField(
            name="label",
            type="str",
            is_required=False,
            is_nullable=True,
            default=None,
        )

        assert ContractField.from_dict(field.to_dict()) == field


class TestContractSchema:
    def test_round_trip_preserves_equality_with_empty_fields(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            version="1.0.0",
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
            name="name", type="str", is_required=True, is_nullable=False, default="anonymous"
        )
        schema = ContractSchema(
            topic="users.registered",
            role="consumer",
            version="2.1.0",
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
            version="1.0.0",
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
            "version": "1.0.0",
            "repository": "my-service",
            "class_name": "OrderSchema",
            "unknown": "allow",
            "fields": [],
        }

        assert ContractSchema.from_dict(data).unknown == UnknownFieldBehaviour.ALLOW

    def test_to_dict_serialises_all_root_fields_correctly(self) -> None:
        schema = ContractSchema(
            topic="orders.created",
            role="producer",
            version="1.0.0",
            repository="my-service",
            class_name="OrderSchema",
            unknown=UnknownFieldBehaviour.FORBID,
            fields=[],
        )

        assert schema.to_dict() == {
            "topic": "orders.created",
            "role": "producer",
            "version": "1.0.0",
            "repository": "my-service",
            "class_name": "OrderSchema",
            "unknown": "forbid",
            "fields": [],
        }
