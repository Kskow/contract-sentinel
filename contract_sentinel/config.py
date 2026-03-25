from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import TypedDict

DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    r"(^|/)\.venv/",
    r"(^|/)venv/",
    r"(^|/)__pycache__/",
    r"(^|/)site-packages/",
    r"(^|/)node_modules/",
    r"(^|/)\.git/",
    r"(^|/)\.tox/",
    r"\.egg-info/",
]


def _get_excluded_patterns(user_patterns: list[str]) -> list[str]:
    """Return the full exclusion list: defaults merged with *user_patterns*."""
    return list({*DEFAULT_EXCLUDE_PATTERNS, *user_patterns})


class _SentinelTomlConfig(TypedDict, total=False):
    name: str
    s3_bucket: str
    s3_path: str
    exclude: list[str]


class Config:
    """Application configuration loaded from environment variables and pyproject.toml.

    Precedence — ``[tool.sentinel]`` in ``pyproject.toml`` wins over environment
    variables for ``name``, ``s3_bucket``, ``s3_path``, and ``exclude``.
    AWS credentials are env-var only (they must not appear in version-controlled files).

    Required fields raise ``ValueError`` on construction if absent from both
    sources. Optional fields produce ``None``.

    ``Config()`` is constructed *only* inside CLI command handlers — never at
    module import time, so importing any ``contract_sentinel`` module never
    triggers env-var reads.
    """

    def __init__(self) -> None:
        sentinel_cfg = self._read_sentinel_pyproject()

        # AWS — env vars only
        self.aws_access_key_id: str | None = os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key: str | None = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.aws_default_region: str = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_endpoint_url: str | None = os.environ.get("AWS_ENDPOINT_URL")

        # Storage
        self.s3_bucket: str | None = (
            sentinel_cfg.get("s3_bucket")
            or os.environ.get("SENTINEL_S3_BUCKET")
            or os.environ.get("S3_BUCKET")
        )
        self.s3_path: str = (
            sentinel_cfg.get("s3_path") or os.environ.get("SENTINEL_S3_PATH") or "contract_tests"
        )
        self.store: str = os.environ.get("SENTINEL_STORE", "s3").lower()

        # Project name
        name = sentinel_cfg.get("name") or os.environ.get("SENTINEL_NAME")
        if not name:
            raise ValueError(
                "set 'name' in [tool.sentinel] in pyproject.toml or via the SENTINEL_NAME env var"
            )
        self.name: str = name

        # Loader
        self.exclude: list[str] = _get_excluded_patterns(sentinel_cfg.get("exclude", []))

    @staticmethod
    def _read_sentinel_pyproject() -> _SentinelTomlConfig:
        """Return the ``[tool.sentinel]`` table from pyproject.toml, or ``{}``."""
        pyproject = Path.cwd() / "pyproject.toml"
        if not pyproject.exists():
            return _SentinelTomlConfig()
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        return data.get("tool", {}).get("sentinel", {})
