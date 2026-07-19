"""Provider registry and local system-readiness HTTP projections."""

from __future__ import annotations

from fastapi import APIRouter

from alpha_web import _catalog
from alpha_web.api._common import data_dir
from alpha_web.api.models import ProviderDefinition, SystemStatus

router = APIRouter(prefix="/api", tags=["control-plane"])


@router.get("/providers", response_model=list[ProviderDefinition])
def get_providers() -> list[dict[str, object]]:
    """Configured provider capabilities with credential names/presence, never secret values."""
    return _catalog.providers(data_dir=data_dir())


@router.get("/system", response_model=SystemStatus)
def get_system() -> dict[str, object]:
    """Local readiness only; this endpoint performs no provider network probes."""
    return _catalog.system(data_dir=data_dir())
