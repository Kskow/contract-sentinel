from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def clean_sys_modules() -> Generator[None, None, None]:
    """Remove any modules registered in sys.modules during the test.

    The loader registers dynamically-imported modules in sys.modules for
    cross-file import resolution. Without cleanup, leftover entries (e.g.
    ``schemas``) would leak between tests sharing the same derived module name.

    Apply to any test class that exercises dynamic imports::

        @pytest.mark.usefixtures("clean_sys_modules")
        class TestMyLoader:
            ...
    """
    before = set(sys.modules.keys())
    yield
    for key in set(sys.modules.keys()) - before:
        del sys.modules[key]
