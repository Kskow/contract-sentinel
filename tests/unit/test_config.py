from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from contract_sentinel.config import DEFAULT_EXCLUDE_PATTERNS, Config

if TYPE_CHECKING:
    from pathlib import Path


@patch.dict(os.environ, {"SENTINEL_NAME": "my-service"}, clear=True)
class TestConfig:
    def test_name_is_read_from_sentinel_name_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.name == "my-service"

    def test_name_from_pyproject_toml_takes_precedence_over_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.sentinel]\nname = "toml-service"\n')
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.name == "toml-service"

    def test_name_raises_when_absent_from_both_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SENTINEL_NAME")

        with pytest.raises(ValueError, match="set 'name' in \\[tool\\.sentinel\\]"):
            Config()

    def test_s3_bucket_is_read_from_s3_bucket_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("S3_BUCKET", "env-bucket")

        config = Config()

        assert config.s3_bucket == "env-bucket"

    def test_s3_bucket_from_pyproject_toml_takes_precedence_over_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.sentinel]\ns3_bucket = "toml-bucket"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("S3_BUCKET", "env-bucket")

        config = Config()

        assert config.s3_bucket == "toml-bucket"

    def test_s3_bucket_is_none_when_absent_from_both_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.s3_bucket is None

    def test_s3_path_defaults_to_contract_tests_when_not_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert config.s3_path == "contract_tests"

    def test_s3_path_is_read_from_sentinel_s3_path_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SENTINEL_S3_PATH", "custom/path")

        config = Config()

        assert config.s3_path == "custom/path"

    def test_s3_path_from_pyproject_toml_takes_precedence_over_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.sentinel]\ns3_path = "toml/path"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SENTINEL_S3_PATH", "env/path")

        config = Config()

        assert config.s3_path == "toml/path"

    def test_exclude_equals_defaults_when_no_pyproject_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert set(config.exclude) == set(DEFAULT_EXCLUDE_PATTERNS)

    def test_exclude_merges_user_patterns_from_pyproject_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.sentinel]\nexclude = ["my_custom_dir/"]\n')
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert set(config.exclude) == set(DEFAULT_EXCLUDE_PATTERNS) | {"my_custom_dir/"}

    def test_exclude_deduplicates_when_user_pattern_matches_a_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.sentinel]\nexclude = ["(^|/)__pycache__/"]\n'
        )
        monkeypatch.chdir(tmp_path)

        config = Config()

        assert set(config.exclude) == set(DEFAULT_EXCLUDE_PATTERNS)
