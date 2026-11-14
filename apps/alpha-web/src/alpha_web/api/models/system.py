"""System status and command definitions."""

from __future__ import annotations

from ._base import StrictModel
from .data_sources import KronosCacheStatus


class SystemDataDirectory(StrictModel):
    path: str
    exists: bool
    readable: bool
    writable: bool
    free_bytes: int


class SystemCounts(StrictModel):
    symbols: int
    snapshots: int


class NautilusStatus(StrictModel):
    pinned_version: str
    installed_version: str | None
    matches_pin: bool


class SystemStatus(StrictModel):
    data_dir: SystemDataDirectory
    counts: SystemCounts
    nautilus: NautilusStatus
    kronos_cache: KronosCacheStatus
    paper_enabled: bool
    ibkr_paper_enabled: bool


class CommandOption(StrictModel):
    name: str
    flag: str | None
    type: str
    default: str | int | float | bool | list[str] | None
    required: bool
    multiple: bool
    help: str
    choices: list[str] | None


class CommandArgument(StrictModel):
    name: str
    type: str
    required: bool
    nargs: int


class CommandDefinition(StrictModel):
    id: str
    run_type: str | None
    args: list[CommandArgument]
    options: list[CommandOption]
