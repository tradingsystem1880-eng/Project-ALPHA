"""Global configuration. Override via ALPHA_-prefixed env vars or a .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlphaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"))
    random_seed: int = 7
