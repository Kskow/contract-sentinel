from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    AWS credentials are read from the standard ``AWS_*`` environment variables.
    All Sentinel-specific settings use the ``SENTINEL_`` prefix.

    ``Settings()`` is constructed *only* inside CLI command handlers — never at
    module import time, so importing any ``contract_sentinel`` module never
    triggers env-var reads or raises on missing variables.
    """

    model_config = SettingsConfigDict(env_prefix="SENTINEL_", extra="ignore")

    # AWS Setup
    AWS_ACCESS_KEY_ID: str = Field(validation_alias="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(validation_alias="AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_REGION: str = Field(default="us-east-1", validation_alias="AWS_DEFAULT_REGION")
    S3_BUCKET: str
    S3_PATH: str = "contract_tests"

    # Repository Setup
    name: str
    framework: str = "marshmallow"
