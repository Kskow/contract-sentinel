from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

logger = logging.getLogger(__name__)


def load_marked_classes(path: Path) -> list[type]:
    """Walk *path* recursively and return all classes decorated with ``@contract``.

    Files are imported using a retry loop: each pass attempts all previously
    failed imports. A file that failed because its dependency had not been
    imported yet will succeed on the next pass once that dependency is in
    ``sys.modules``. The loop terminates when a full pass produces no new
    successes — remaining failures are genuinely unresolvable (syntax errors,
    missing packages) and are logged as warnings.

    Non-``.py`` files are silently ignored.
    """
    pending = sorted(path.rglob("*.py"))
    successful_modules: list[ModuleType] = []

    while pending:
        failed: list[Path] = []

        for py_file in pending:
            module = _try_import(py_file, root=path)
            if module is None:
                failed.append(py_file)
            else:
                successful_modules.append(module)

        # No progress made — remaining files are genuinely unresolvable.
        if len(failed) == len(pending):
            for py_file in failed:
                logger.warning("Could not import '%s' after all retries — skipping.", py_file)
            break

        pending = failed

    marked: list[type] = []
    for module in successful_modules:
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if hasattr(obj, "__contract__"):
                marked.append(obj)

    return marked


def _try_import(file: Path, root: Path) -> ModuleType | None:
    """Attempt to import *file* as a module, returning ``None`` silently on any failure.

    The module name is derived from *file*'s path relative to *root* so that
    nested packages produce stable, non-colliding names (e.g. ``schemas.orders``).
    The module is registered in ``sys.modules`` before execution so that
    partially-initialised modules are visible to other files during the same pass.
    """
    relative = file.relative_to(root)
    module_name = ".".join(relative.with_suffix("").parts)

    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)  # loader is always executable here
    except Exception:
        del sys.modules[module_name]
        return None

    return module
