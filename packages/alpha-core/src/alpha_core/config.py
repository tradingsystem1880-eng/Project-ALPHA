"""Global configuration. Override via ALPHA_-prefixed env vars or a .env file."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlphaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALPHA_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("data"))
    random_seed: int = 7

    # Kronos forecasting (alpha_forecast). "main" revisions are recorded verbatim in every
    # manifest; pin to HF commit hashes via env for byte-stable provenance. Device defaults
    # to cpu because torch sampling is only reproducible there — mps/cuda are opt-in and
    # flagged best-effort in manifests. The pretrain cutoff is Kronos's UNDISCLOSED training
    # data boundary, conservatively assumed = the paper's submission date; bars at or before
    # it were plausibly seen in pretraining (leakage warn + manifest flag, spec ADR-0009).
    forecast_model: str = "NeoQuasar/Kronos-small"
    forecast_model_revision: str = "main"
    forecast_tokenizer: str = "NeoQuasar/Kronos-Tokenizer-base"
    forecast_tokenizer_revision: str = "main"
    forecast_device: str = "cpu"
    forecast_context: int = 400
    forecast_pretrain_cutoff: date = date(2025, 8, 2)
    # Machine-local weight loading. hub_cache points HF resolution at a local cache dir
    # (unset the var to disable — an empty string parses to Path(".")); local_only forbids
    # any hub network call and fails loud when weights are missing. Both are execution
    # details: they never enter run ids, manifests, or signal-cache keys — weight identity
    # is pinned by (model id, revision hash) alone. See docs/adr/0010.
    forecast_hub_cache: Path | None = None
    forecast_local_only: bool = False
