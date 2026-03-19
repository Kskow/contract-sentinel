from __future__ import annotations

import enum

import marshmallow as ma
import marshmallow.validate as mv
import pytest

from contract_sentinel.adapters.schema_parser import Marshmallow3Parser
from contract_sentinel.domain.participant import Role, contract


class _Color(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class TestMarshmallow3Parser:
    # -------------------------------------------------------------------------
    # 1. Unknown field behaviour
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("ma_unknown", "expected"),
        [
            (ma.RAISE, "forbid"),
            (ma.EXCLUDE, "ignore"),
            (ma.INCLUDE, "allow"),
        ],
    )
    def test_unknown_policy_maps_to_expected_value(self, ma_unknown: str, expected: str) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            class Meta:
                unknown = ma_unknown

            name = ma.fields.String()

        result = Marshmallow3Parser(repository="svc").parse(MySchema)

        assert result.to_dict()["unknown"] == expected

    def test_unknown_policy_inherited_from_parent_schema(self) -> None:
        class BaseSchema(ma.Schema):
            class Meta:
                unknown = ma.EXCLUDE

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class ChildSchema(BaseSchema):
            name = ma.fields.String()

        result = Marshmallow3Parser(repository="svc").parse(ChildSchema)

        assert result.to_dict()["unknown"] == "ignore"

    # -------------------------------------------------------------------------
    # 2. Core field properties
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(("required", "expected"), [(True, True), (False, False)])
    def test_required_flag(self, required: bool, expected: bool) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            name = ma.fields.String(required=required)

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field["is_required"] is expected

    @pytest.mark.parametrize(("allow_none", "expected"), [(True, True), (False, False)])
    def test_nullable_flag(self, allow_none: bool, expected: bool) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            name = ma.fields.String(allow_none=allow_none)

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field["is_nullable"] is expected

    def test_load_only_field_includes_is_load_only_in_output(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            password = ma.fields.String(load_only=True)

        result = Marshmallow3Parser(repository="svc").parse(MySchema)
        field = result.to_dict()["fields"][0]

        assert field == {
            "name": "password",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_load_only": True,
            "is_supported": True,
        }

    def test_dump_only_field_includes_is_dump_only_in_output(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            created_at = ma.fields.String(dump_only=True)

        result = Marshmallow3Parser(repository="svc").parse(MySchema)
        field = result.to_dict()["fields"][0]

        assert field == {
            "name": "created_at",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_dump_only": True,
            "is_supported": True,
        }

    def test_data_key_is_used_as_wire_name(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            order_id = ma.fields.String(data_key="orderId")

        result = Marshmallow3Parser(repository="svc").parse(MySchema)
        field = result.to_dict()["fields"][0]

        assert field["name"] == "orderId"

    # -------------------------------------------------------------------------
    # 3. Defaults
    # -------------------------------------------------------------------------

    def test_load_default_appears_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            is_active = ma.fields.String(load_default="test_value")

        result = Marshmallow3Parser(repository="svc").parse(MySchema)
        field = result.to_dict()["fields"][0]

        assert field["metadata"]["load_default"] == "test_value"

    def test_dump_default_appears_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            status = ma.fields.String(dump_default="test_value")

        result = Marshmallow3Parser(repository="svc").parse(MySchema)
        field = result.to_dict()["fields"][0]

        assert field["metadata"]["dump_default"] == "test_value"

    # -------------------------------------------------------------------------
    # 4. Fields mapping
    # -------------------------------------------------------------------------

    def test_simple_fields_without_format(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class SimpleSchema(ma.Schema):
            f_integer = ma.fields.Integer()
            f_float = ma.fields.Float()
            f_decimal = ma.fields.Decimal()
            f_boolean = ma.fields.Boolean()
            f_timedelta = ma.fields.TimeDelta()
            f_string = ma.fields.String()
            f_raw = ma.fields.Raw()

        assert Marshmallow3Parser(repository="svc").parse(SimpleSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "SimpleSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "f_integer",
                    "type": "integer",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_float",
                    "type": "number",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_decimal",
                    "type": "number",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_boolean",
                    "type": "boolean",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_timedelta",
                    "type": "number",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_string",
                    "type": "string",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
                {
                    "name": "f_raw",
                    "type": "any",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                },
            ],
        }

    def test_simple_fields_with_format(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class FormattedSchema(ma.Schema):
            f_naive_datetime = ma.fields.NaiveDateTime()
            f_aware_datetime = ma.fields.AwareDateTime()
            f_time = ma.fields.Time()
            f_date = ma.fields.Date()
            f_datetime = ma.fields.DateTime()
            f_email = ma.fields.Email()
            f_url = ma.fields.URL()
            f_uuid = ma.fields.UUID()
            f_ipv4 = ma.fields.IPv4()
            f_ipv6 = ma.fields.IPv6()
            f_ip = ma.fields.IP()
            f_ipv4interface = ma.fields.IPv4Interface()
            f_ipv6interface = ma.fields.IPv6Interface()
            f_ipinterface = ma.fields.IPInterface()
            f_enum = ma.fields.Enum(_Color)

        # shared base for all string fields
        _s = {"is_required": False, "is_nullable": False, "is_supported": True}
        assert Marshmallow3Parser(repository="svc").parse(FormattedSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "FormattedSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "f_naive_datetime",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "date-time", "custom_format": "iso"},
                },
                {
                    "name": "f_aware_datetime",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "date-time", "custom_format": "iso"},
                },
                {
                    "name": "f_time",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "time", "custom_format": "iso"},
                },
                {
                    "name": "f_date",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "date", "custom_format": "iso"},
                },
                {
                    "name": "f_datetime",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "date-time", "custom_format": "iso"},
                },
                {"name": "f_email", "type": "string", **_s, "metadata": {"format": "email"}},
                {"name": "f_url", "type": "string", **_s, "metadata": {"format": "uri"}},
                {"name": "f_uuid", "type": "string", **_s, "metadata": {"format": "uuid"}},
                {"name": "f_ipv4", "type": "string", **_s, "metadata": {"format": "ipv4"}},
                {"name": "f_ipv6", "type": "string", **_s, "metadata": {"format": "ipv6"}},
                {"name": "f_ip", "type": "string", **_s, "metadata": {"format": "ip"}},
                {
                    "name": "f_ipv4interface",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "ipv4interface"},
                },
                {
                    "name": "f_ipv6interface",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "ipv6interface"},
                },
                {
                    "name": "f_ipinterface",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "ipinterface"},
                },
                {
                    "name": "f_enum",
                    "type": "string",
                    **_s,
                    "metadata": {"format": "enum", "allowed_values": ["red", "green", "blue"]},
                },
            ],
        }

    def test_unknown_field_type_uses_class_name_as_format(self) -> None:
        class _Unrecognised(ma.fields.Field):
            pass

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            mystery = _Unrecognised()

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "mystery",
                    "type": "string",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": False,
                    "metadata": {"format": "_unrecognised"},
                }
            ],
        }

    def test_constant_field_type_reflects_python_value_type(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            str_const = ma.fields.Constant("active")
            int_const = ma.fields.Constant(42)
            float_const = ma.fields.Constant(3.14)
            bool_const = ma.fields.Constant(True)

        _s = {"is_required": False, "is_nullable": False, "is_supported": True}
        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {"name": "str_const", "type": "string", **_s, "metadata": {"constant": "active"}},
                {"name": "int_const", "type": "integer", **_s, "metadata": {"constant": 42}},
                {"name": "float_const", "type": "number", **_s, "metadata": {"constant": 3.14}},
                {"name": "bool_const", "type": "boolean", **_s, "metadata": {"constant": True}},
            ],
        }

    def test_nested_schema_produces_object_type_with_fields(self) -> None:
        class AddressSchema(ma.Schema):
            street = ma.fields.String(required=True)
            city = ma.fields.String(required=True)

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class PersonSchema(ma.Schema):
            address = ma.fields.Nested(AddressSchema, required=True)

        assert Marshmallow3Parser(repository="svc").parse(PersonSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "PersonSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "address",
                    "type": "object",
                    "is_required": True,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "street",
                            "type": "string",
                            "is_required": True,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                        {
                            "name": "city",
                            "type": "string",
                            "is_required": True,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                }
            ],
        }

    def test_nested_many_produces_array_type_with_fields(self) -> None:
        class TagSchema(ma.Schema):
            label = ma.fields.String(required=True)

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class EventSchema(ma.Schema):
            tags = ma.fields.Nested(TagSchema, many=True)

        assert Marshmallow3Parser(repository="svc").parse(EventSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "EventSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "tags",
                    "type": "array",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "label",
                            "type": "string",
                            "is_required": True,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                }
            ],
        }

    def test_nested_schema_unknown_policy_is_carried_through(self) -> None:
        class TagsSchema(ma.Schema):
            class Meta:
                unknown = ma.INCLUDE

            label = ma.fields.String()

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class EventSchema(ma.Schema):
            tags = ma.fields.Nested(TagsSchema)

        assert Marshmallow3Parser(repository="svc").parse(EventSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "EventSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "tags",
                    "type": "object",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "allow",
                    "fields": [
                        {
                            "name": "label",
                            "type": "string",
                            "is_required": False,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                }
            ],
        }

    def test_nested_only_restricts_fields_to_specified_subset(self) -> None:
        class AddressSchema(ma.Schema):
            street = ma.fields.String()
            city = ma.fields.String()
            postcode = ma.fields.String()

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class PersonSchema(ma.Schema):
            address = ma.fields.Nested(AddressSchema, only=["city"])

        assert Marshmallow3Parser(repository="svc").parse(PersonSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "PersonSchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "address",
                    "type": "object",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "city",
                            "type": "string",
                            "is_required": False,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                }
            ],
        }

    def test_list_of_primitive_produces_array_with_item_type(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            tags = ma.fields.List(ma.fields.String())

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "tags",
                    "type": "array",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "metadata": {"item_type": "string"},
                }
            ],
        }

    def test_list_of_nested_produces_array_with_fields_not_item_type(self) -> None:
        class TagSchema(ma.Schema):
            label = ma.fields.String()

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            tags = ma.fields.List(ma.fields.Nested(TagSchema))

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "tags",
                    "type": "array",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "label",
                            "type": "string",
                            "is_required": False,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                }
            ],
        }

    def test_dict_with_primitive_values_captures_key_and_value_types(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            scores = ma.fields.Dict(keys=ma.fields.String(), values=ma.fields.Integer())

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "scores",
                    "type": "object",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "metadata": {"key_type": "string", "value_type": "integer"},
                }
            ],
        }

    def test_dict_with_nested_values_captures_key_type_and_nested_fields(self) -> None:
        class ItemSchema(ma.Schema):
            count = ma.fields.Integer()

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            inventory = ma.fields.Dict(keys=ma.fields.String(), values=ma.fields.Nested(ItemSchema))

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "inventory",
                    "type": "object",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "count",
                            "type": "integer",
                            "is_required": False,
                            "is_nullable": False,
                            "is_supported": True,
                        },
                    ],
                    "metadata": {"key_type": "string"},
                }
            ],
        }

    def test_tuple_field_marks_is_supported_false(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            coords = ma.fields.Tuple(tuple_fields=(ma.fields.Float(), ma.fields.Float()))

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "coords",
                    "type": "array",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": False,
                }
            ],
        }

    def test_method_field_marks_is_supported_false(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            full_name = ma.fields.Method("get_full_name")

            def get_full_name(self, obj: object) -> str:
                return str(obj)

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "full_name",
                    "type": "string",
                    "is_required": False,
                    "is_nullable": False,
                    "is_dump_only": True,
                    "is_supported": False,
                }
            ],
        }

    def test_function_field_marks_is_supported_false(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            label = ma.fields.Function(lambda obj: str(obj))

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "label",
                    "type": "string",
                    "is_required": False,
                    "is_nullable": False,
                    "is_dump_only": True,
                    "is_supported": False,
                }
            ],
        }

    def test_enum_field_produces_string_type_with_format_and_values(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            color = ma.fields.Enum(_Color)

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {
                    "name": "color",
                    "type": "string",
                    "is_required": False,
                    "is_nullable": False,
                    "is_supported": True,
                    "metadata": {"format": "enum", "allowed_values": ["red", "green", "blue"]},
                }
            ],
        }

    # -------------------------------------------------------------------------
    # 5. Validators
    # -------------------------------------------------------------------------

    def test_length_validator_with_min_and_max_appears_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            username = ma.fields.String(validate=mv.Length(min=1, max=10))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "username",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"length": {"min": 1, "max": 10}},
        }

    def test_length_validator_with_equal_appears_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            pin = ma.fields.String(validate=mv.Length(equal=5))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "pin",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"length": {"equal": 5}},
        }

    def test_range_validator_appears_in_metadata_with_inclusivity_flags(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            score = ma.fields.Integer(validate=mv.Range(min=0, max=100))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "score",
            "type": "integer",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {
                "range": {"min": 0, "min_inclusive": True, "max": 100, "max_inclusive": True}
            },
        }

    def test_regexp_validator_appears_as_pattern_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            code = ma.fields.String(validate=mv.Regexp(r"^\d+$"))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "code",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"pattern": r"^\d+$"},
        }

    def test_one_of_validator_appears_as_allowed_values_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            status = ma.fields.String(validate=mv.OneOf(["active", "inactive"]))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "status",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"allowed_values": ["active", "inactive"]},
        }

    def test_and_validator_extracts_all_inner_constraints(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            code = ma.fields.String(validate=mv.And(mv.Length(min=1), mv.Regexp(r"^\d+$")))

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "code",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"length": {"min": 1}, "pattern": r"^\d+$"},
        }

    def test_datetime_with_iso_format_produces_custom_format_in_metadata(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            created_at = ma.fields.DateTime(format="iso")

        field = Marshmallow3Parser(repository="svc").parse(MySchema).to_dict()["fields"][0]

        assert field == {
            "name": "created_at",
            "type": "string",
            "is_required": False,
            "is_nullable": False,
            "is_supported": True,
            "metadata": {"format": "date-time", "custom_format": "iso"},
        }
