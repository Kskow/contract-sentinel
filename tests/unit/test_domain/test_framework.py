from __future__ import annotations

import pytest

from contract_sentinel.domain.errors import UnsupportedFrameworkError
from contract_sentinel.domain.framework import Framework, detect_framework


class TestDetectFramework:
    def test_detect_framework_given_marshmallow_schema_returns_marshmallow(self) -> None:
        class MockSchema:
            __module__ = "marshmallow.schema"

        class MySchema(MockSchema):
            pass

        result = detect_framework(MySchema)

        assert result == Framework.MARSHMALLOW

    def test_detect_framework_given_unsupported_class_raises_unsupported_framework_error(
        self,
    ) -> None:
        class UnsupportedClass:
            pass

        with pytest.raises(UnsupportedFrameworkError) as excinfo:
            detect_framework(UnsupportedClass)

        assert str(excinfo.value) == (
            "Cannot detect schema framework for 'UnsupportedClass'. "
            "Supported frameworks: marshmallow."
        )
