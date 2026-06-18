"""Global configuration. Override via ALPHA_-prefixed env vars or a .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlphaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"))
    random_seed: int = 7

    # Paper trading (Phase 4). Defaulted so the public-data sandbox path needs no secrets; API
    # credentials come ONLY from the environment / .env and are never written into any artifact.
    paper_exchange: str = "coinbase"
    paper_venue: str = "SANDBOX"
    paper_symbol: str = "BTC/USDT"
    paper_api_key: str | None = None
    paper_api_secret: str | None = None
    paper_use_testnet: bool = False
