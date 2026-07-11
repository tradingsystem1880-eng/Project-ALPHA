"""Global configuration. Override via ALPHA_-prefixed env vars or a .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlphaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"))
    random_seed: int = 7
    # Foundation-model weights cache (env ALPHA_WEIGHTS_DIR). None -> data_dir / "models".
    # Named weights_dir (not model_dir) to stay clear of pydantic's protected model_* namespace.
    weights_dir: Path | None = None

    @property
    def resolved_weights_dir(self) -> Path:
        return self.weights_dir if self.weights_dir is not None else self.data_dir / "models"
