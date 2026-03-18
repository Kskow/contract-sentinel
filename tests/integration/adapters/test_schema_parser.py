from __future__ import annotations

import enum

import marshmallow as ma

from contract_sentinel.adapters.schema_parser import Marshmallow3Parser
from contract_sentinel.domain.participant import Role, contract


class _Color(enum.Enum):
    RED = "red"
    GREEN = "green"


class TestMarshmallow3Parser:
    def test_full_schema_to_dict(self) -> None:
        @contract(topic="orders.created", role=Role.PRODUCER, version="1.0.0")
        class OrderSchema(ma.Schema):
            order_id = ma.fields.String(required=True)
            amount = ma.fields.Integer(required=True)
            is_paid = ma.fields.Boolean(load_default=False)
            notes = ma.fields.String(allow_none=True)

        result = Marshmallow3Parser(repository="order-service").parse(OrderSchema)

        assert result.to_dict() == {
            "topic": "orders.created",
            "role": "producer",
            "version": "1.0.0",
            "repository": "order-service",
            "class_name": "OrderSchema",
            "unknown": "forbid",
            "fields": [
                {"name": "order_id", "type": "string", "is_required": True, "is_nullable": False},
                {"name": "amount", "type": "integer", "is_required": True, "is_nullable": False},
                {
                    "name": "is_paid",
                    "type": "boolean",
                    "is_required": False,
                    "is_nullable": False,
                    "default": False,
                },
                {"name": "notes", "type": "string", "is_required": False, "is_nullable": True},
            ],
        }

    def test_exclude_produces_ignore(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            class Meta:
                unknown = ma.EXCLUDE

            name = ma.fields.String()

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "ignore",
            "fields": [
                {"name": "name", "type": "string", "is_required": False, "is_nullable": False},
            ],
        }

    def test_include_produces_allow(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            class Meta:
                unknown = ma.INCLUDE

            name = ma.fields.String()

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "allow",
            "fields": [
                {"name": "name", "type": "string", "is_required": False, "is_nullable": False},
            ],
        }

    def test_raise_produces_forbid(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class MySchema(ma.Schema):
            class Meta:
                unknown = ma.RAISE

            name = ma.fields.String()

        assert Marshmallow3Parser(repository="svc").parse(MySchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "MySchema",
            "unknown": "forbid",
            "fields": [
                {"name": "name", "type": "string", "is_required": False, "is_nullable": False},
            ],
        }

    def test_unknown_policy_inherited_from_parent(self) -> None:
        class BaseSchema(ma.Schema):
            class Meta:
                unknown = ma.EXCLUDE

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class ChildSchema(BaseSchema):
            name = ma.fields.String()

        assert Marshmallow3Parser(repository="svc").parse(ChildSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "ChildSchema",
            "unknown": "ignore",
            "fields": [
                {"name": "name", "type": "string", "is_required": False, "is_nullable": False},
            ],
        }

    def test_nested_field_to_dict(self) -> None:
        class AddressSchema(ma.Schema):
            street = ma.fields.String(required=True)
            city = ma.fields.String(required=True)

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class PersonSchema(ma.Schema):
            name = ma.fields.String(required=True)
            address = ma.fields.Nested(AddressSchema, required=True)

        assert Marshmallow3Parser(repository="svc").parse(PersonSchema).to_dict() == {
            "topic": "t",
            "role": "producer",
            "version": "1.0.0",
            "repository": "svc",
            "class_name": "PersonSchema",
            "unknown": "forbid",
            "fields": [
                {"name": "name", "type": "string", "is_required": True, "is_nullable": False},
                {
                    "name": "address",
                    "type": "object",
                    "is_required": True,
                    "is_nullable": False,
                    "unknown": "forbid",
                    "fields": [
                        {
                            "name": "street",
                            "type": "string",
                            "is_required": True,
                            "is_nullable": False,
                        },
                        {
                            "name": "city",
                            "type": "string",
                            "is_required": True,
                            "is_nullable": False,
                        },
                    ],
                },
            ],
        }

    def test_pluck_maps_to_object(self) -> None:
        class TagSchema(ma.Schema):
            label = ma.fields.String()

        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class EventSchema(ma.Schema):
            first_tag = ma.fields.Pluck(TagSchema, "label")

        result = Marshmallow3Parser(repository="svc").parse(EventSchema)
        types = {f["name"]: f["type"] for f in result.to_dict()["fields"]}
        assert types == {"first_tag": "object"}

    def test_nested_schema_with_include_unknown_to_dict(self) -> None:
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
                    "unknown": "allow",
                    "fields": [
                        {
                            "name": "label",
                            "type": "string",
                            "is_required": False,
                            "is_nullable": False,
                        },
                    ],
                },
            ],
        }

    def test_all_field_type_mappings(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class AllFieldsSchema(ma.Schema):
            # --- DateTime family (subclasses must appear before DateTime in _type_map) ---
            f_naive_datetime = ma.fields.NaiveDateTime()
            f_aware_datetime = ma.fields.AwareDateTime()
            f_time = ma.fields.Time()
            f_date = ma.fields.Date()
            f_datetime = ma.fields.DateTime()
            # --- Numeric ---
            f_integer = ma.fields.Integer()
            f_float = ma.fields.Float()
            f_decimal = ma.fields.Decimal()  # fallback: "decimal"
            # --- Boolean ---
            f_boolean = ma.fields.Boolean()
            # --- String family (Email/URL/UUID subclass String → "string") ---
            f_string = ma.fields.String()
            f_email = ma.fields.Email()
            f_url = ma.fields.URL()
            f_uuid = ma.fields.UUID()
            # --- Collections ---
            f_list = ma.fields.List(ma.fields.String())
            f_dict = ma.fields.Dict()
            # Soft-deprecated in marshmallow 3 (use Dict); kept to verify the fallback path.
            f_mapping = ma.fields.Mapping()
            # Tuple — fallback: "tuple"
            f_tuple = ma.fields.Tuple(tuple_fields=(ma.fields.String(), ma.fields.Integer()))
            # --- Date / time extras ---
            f_timedelta = ma.fields.TimeDelta()  # fallback: "timedelta"
            # --- IP addresses ---
            f_ip = ma.fields.IP()  # fallback: "ip"
            f_ipv4 = ma.fields.IPv4()  # fallback: "ipv4"
            f_ipv6 = ma.fields.IPv6()  # fallback: "ipv6"
            f_ipinterface = ma.fields.IPInterface()  # fallback: "ipinterface"
            f_ipv4interface = ma.fields.IPv4Interface()  # fallback: "ipv4interface"
            f_ipv6interface = ma.fields.IPv6Interface()  # fallback: "ipv6interface"
            # --- Misc ---
            f_enum = ma.fields.Enum(_Color)  # fallback: "enum"
            f_raw = ma.fields.Raw()  # fallback: "raw"
            f_constant = ma.fields.Constant(42)  # fallback: "constant"

        result = Marshmallow3Parser(repository="svc").parse(AllFieldsSchema)
        field_types = {f["name"]: (f["type"], f.get("format")) for f in result.to_dict()["fields"]}

        assert field_types == {
            # DateTime family — all serialise as ISO strings; subclasses resolved before DateTime
            "f_naive_datetime": ("string", "date-time"),
            "f_aware_datetime": ("string", "date-time"),
            "f_time": ("string", "time"),
            "f_date": ("string", "date"),
            "f_datetime": ("string", "date-time"),
            # Numeric
            "f_integer": ("integer", None),
            "f_float": ("number", None),
            "f_decimal": ("number", None),
            # Boolean
            "f_boolean": ("boolean", None),
            # String family — format distinguishes semantic subtypes
            "f_string": ("string", None),
            "f_email": ("string", "email"),
            "f_url": ("string", "uri"),
            "f_uuid": ("string", "uuid"),
            # Collections
            "f_list": ("array", None),
            "f_dict": ("object", None),
            "f_mapping": ("object", None),
            "f_tuple": ("array", None),
            # Temporal duration — marshmallow dumps timedelta as total_seconds()
            "f_timedelta": ("number", None),
            # IP addresses — format carries the specific flavour
            "f_ip": ("string", "ip"),
            "f_ipv4": ("string", "ipv4"),
            "f_ipv6": ("string", "ipv6"),
            "f_ipinterface": ("string", "ipinterface"),
            "f_ipv4interface": ("string", "ipv4interface"),
            "f_ipv6interface": ("string", "ipv6interface"),
            # Misc
            "f_enum": ("string", "enum"),
            # Unknown fields fall back to ("string", classname.lower())
            "f_raw": ("string", "raw"),
            "f_constant": ("string", "constant"),
        }

    def test_enum_field_captures_allowed_values(self) -> None:
        @contract(topic="t", role=Role.PRODUCER, version="1.0.0")
        class OrderSchema(ma.Schema):
            status = ma.fields.Enum(_Color)

        result = Marshmallow3Parser(repository="svc").parse(OrderSchema)
        field_dict = result.to_dict()["fields"][0]

        assert field_dict["type"] == "string"
        assert field_dict["format"] == "enum"
        assert field_dict["values"] == ["red", "green"]
